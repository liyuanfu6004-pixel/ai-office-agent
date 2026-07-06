"""字段映射对话框模块。

用户导入 Excel 后，表头不固定，必须由用户确认每一列对应哪个业务字段。
本对话框展示所有识别到的表头，让用户为以下业务字段各选择一列：

- 项目名称（必填）
- 项目编码（必填）
- 年份（可选）
- 项目类型（可选）
- 状态（可选）

v0.6.0 起：总体项目表只映射这 5 个字段；区县数量 / 点位数量 / 完成率
不由总体表提供，已从映射中删除。项目类型可选——为空时项目只显示在
"全部项目"页。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# v1.1.1：matcher 导入（try/except 兼容不同运行上下文）
try:
    from ....core.matcher import match_field as _match_field
except ImportError:
    from ai_office_agent.core.matcher import match_field as _match_field

# 业务字段键（与 projects_repository / import_worker 约定的 dict 键一致）
FIELDS: list[dict] = [
    {"key": "project_name", "label": "项目名称列", "required": True},
    {"key": "project_code", "label": "项目编码列", "required": True},
    {"key": "year", "label": "年份列（可选）", "required": False},
    {"key": "project_type", "label": "项目类型列（可选）", "required": False},
    {"key": "status", "label": "状态列（可选）", "required": False},
]

# 每个字段用于模糊匹配表头的关键词（小写子串匹配）
_FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "project_name": ("项目名称", "项目名", "名称", "工程名称"),
    "project_code": ("项目编码", "项目编号", "编码", "编号", "代码"),
    "year": ("年份", "年度", "年"),
    "project_type": ("项目类型", "类型"),
    "status": ("状态", "项目状态", "进展"),
}

# 表示"未选择/该字段无对应列"的占位文本
_NO_MAPPING = "（无）"

# 预览表格最多展示前 N 行数据
_PREVIEW_ROWS = 8


class FieldMappingDialog(QDialog):
    """字段映射对话框。

    Args:
        headers: 识别到的 Excel 表头列表。
        data_rows: 数据行字典列表（用于预览）。
        project_type: 保留参数（向后兼容），当前导入已改为按"项目类型列"
            自动分流，不再依赖固定类型；可为 None。
        parent: 父控件。
    """

    # 测试钩子：置 True 后，对话框显示时自动延迟"确定"。
    # 生产环境保持 False，留给自动化测试使用。
    auto_accept_for_test: bool = False

    def __init__(
        self,
        headers: list[str],
        data_rows: list[dict],
        project_type: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("确认字段映射")
        self.setMinimumSize(680, 560)

        self._headers = list(headers)
        self._data_rows = data_rows
        self._project_type = project_type
        self._combos: dict[str, QComboBox] = {}

        self._build_ui()
        self._auto_guess()

    @staticmethod
    def guess_mapping(headers: list[str]) -> dict[str, str | None]:
        """不在实例化对话框的场景下，按关键词预选映射。

        供自动化测试或"无交互导入"使用：无需弹窗即可拿到智能预选映射。

        v1.1.1 升级：走 matcher.match_field（RapidFuzz 引擎）。
        """
        mapping: dict[str, str | None] = {}
        for field in FIELDS:
            key = field["key"]
            picked = None
            for kw in _FIELD_KEYWORDS.get(key, ()):
                for h in headers:
                    if _match_field(h, kw).is_match:
                        picked = h
                        break
                if picked:
                    break
            mapping[key] = picked
        return mapping

    # ------------------------------------------------------------------ 构建

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        tip = QLabel(
            "已自动识别表头。请为以下业务字段选择对应的 Excel 列。\n"
            "项目名称、项目编码必填；其余可选。\n"
            "项目类型列有值则自动分类，为空则项目只显示在「全部项目」。\n"
            "完成后点击「确定」开始导入。"
        )
        tip.setStyleSheet("color: #444;")
        layout.addWidget(tip)

        # ---- 表单：每个字段一下拉 ----
        form_wrap = QWidget(self)
        form_layout = QFormLayout(form_wrap)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        for field in FIELDS:
            combo = QComboBox(form_wrap)
            combo.addItem(_NO_MAPPING)  # 第 0 项：未选
            for h in self._headers:
                combo.addItem(h)
            # 必选字段加红色星号
            label_text = (f"{field['label']} *" if field["required"] else field["label"])
            form_layout.addRow(label_text, combo)
            combo.currentIndexChanged.connect(self._refresh_preview)
            self._combos[field["key"]] = combo

        layout.addWidget(form_wrap)

        # ---- 预览表格 ----
        layout.addWidget(QLabel("预览（按当前映射解析）："))
        self.preview_table = QTableWidget(self)
        self.preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_table, 1)

        # ---- 按钮 ----
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ 智能预选

    def _auto_guess(self) -> None:
        """按关键词模糊匹配，为每个字段预选一个表头列。

        v1.1.1 升级：走 matcher.match_field（RapidFuzz 引擎）。
        """
        for field in FIELDS:
            combo = self._combos[field["key"]]
            key = field["key"]
            keywords = _FIELD_KEYWORDS.get(key, ())
            picked = 0  # 默认"（无）"
            # 优先精确包含；其次更宽松的部分匹配
            for kw in keywords:
                for idx, h in enumerate(self._headers):
                    if _match_field(h, kw).is_match:
                        picked = idx + 1  # +1 跳过第 0 项占位
                        break
                if picked:
                    break
            combo.setCurrentIndex(picked)

        self._refresh_preview()

    # ------------------------------------------------------------------ 预览

    def _refresh_preview(self) -> None:
        """按当前映射，重绘预览表格前若干行。"""
        field_to_header = self.get_mapping()
        # 预览列：按 FIELDS 顺序
        self.preview_table.setColumnCount(len(FIELDS))
        self.preview_table.setHorizontalHeaderLabels(
            [f["label"] for f in FIELDS]
        )

        rows_to_show = self._data_rows[:_PREVIEW_ROWS]
        self.preview_table.setRowCount(len(rows_to_show))
        for r, row_dict in enumerate(rows_to_show):
            for c, field in enumerate(FIELDS):
                header = field_to_header.get(field["key"])
                # status 字段允许无映射 → 显示空
                value = row_dict.get(header) if header else None
                text = "" if value is None else str(value).strip()
                self.preview_table.setItem(r, c, QTableWidgetItem(text))

        self.preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    # ------------------------------------------------------------------ 结果

    def get_mapping(self) -> dict[str, str | None]:
        """返回 {字段键: 表头名}；未选择的字段值为 None。"""
        mapping: dict[str, str | None] = {}
        for field in FIELDS:
            combo = self._combos[field["key"]]
            text = combo.currentText()
            mapping[field["key"]] = None if text == _NO_MAPPING else text
        return mapping

    # ------------------------------------------------------------------ 校验

    def _on_accept(self) -> None:
        """确认前校验必选字段是否均已选择。"""
        mapping = self.get_mapping()
        missing = [
            f["label"]
            for f in FIELDS
            if f["required"] and not mapping.get(f["key"])
        ]
        if missing:
            QMessageBox.warning(
                self,
                "字段未选全",
                "以下必选字段未选择对应列：\n" + "、".join(missing),
            )
            return
        self.accept()

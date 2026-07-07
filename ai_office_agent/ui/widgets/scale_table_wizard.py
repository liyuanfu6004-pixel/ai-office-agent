"""规模表导入向导 — v1.2.1 优化（动态字段手动添加 + 字段映射优化）。

四步导入流程：
  1. Sheet 选择 —— 自动评估各 Sheet 可能性，如有多个候选由用户选择
  2. 字段映射 —— 自动推荐字段，允许用户修正
  3. 动态字段选择 —— v1.2.1 改为手动添加（默认仅保留区县+点位名称）
  4. 导入预览 —— 展示前 10 条，确认后导入

v1.2.1 变更：
- 动态字段默认不导入，用户点击「＋ 添加字段」手动选择
- 左侧自定义列名，右侧选择规模表中的列
- 允许增加/删除/修改

约束：
- 禁止写死字段名称（所有字段名来自关键词匹配）
- 所有用户修正均保存到 Project Profile
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from ...core import project_profile_repository
from ...core.database import Database
from ...core.scale_table_engine import (
    build_field_candidates,
    build_point_records_with_stats,
    build_preview_rows,
    classify_dynamic_fields,
    detect_best_sheet,
    should_concatenate,
)
from ...utils.logger import setup_logger

logger = setup_logger()

_PREVIEW_ROWS = 10
_NO_MAPPING = "（无）"


class ScaleTableWizard(QDialog):
    """规模表导入多步向导（v1.2.1 优化）。"""

    import_requested = Signal(dict)

    def __init__(
        self,
        sheet_candidates: list[dict],
        project_type: str | None = None,
        project_id: int | None = None,
        db_path: str = "data/ai_office_agent.db",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("规模表导入向导（v1.2.1）")
        self.setMinimumSize(860, 650)

        self._candidates = sheet_candidates
        self._project_type = project_type
        self._project_id = project_id
        self._db_path = db_path

        self._selected_sheet_idx: int = 0
        self._selected_headers: list[str] = []
        self._selected_data_rows: list[dict] = []

        self._mapping: dict[str, str | None] = {
            "point_name": None,
            "county": None,
            "start_point": None,
            "end_point": None,
        }
        self._use_concatenation: bool = should_concatenate(project_type)
        # v1.2.1：动态字段初始为空，用户手动添加
        self._dynamic_fields: list[dict] = []
        # 候选动态字段列表（全部非固定字段）
        self._dynamic_candidates: list[dict] = []

        self._build_ui()
        self._try_load_profile()

    # ==================================================================
    # UI 构建
    # ==================================================================

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(0)

        self._step_stack = QStackedWidget(self)
        self._step0 = self._build_step_sheet()
        self._step1 = self._build_step_mapping()
        self._step2 = self._build_step_dynamic()     # v1.2.1：动态字段手动选择
        self._step3 = self._build_step_preview()

        self._step_stack.addWidget(self._step0)
        self._step_stack.addWidget(self._step1)
        self._step_stack.addWidget(self._step2)
        self._step_stack.addWidget(self._step3)

        main_layout.addWidget(self._step_stack, 1)

        # 底部导航栏
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self._back_btn = QPushButton("上一步")
        self._next_btn = QPushButton("下一步")
        self._cancel_btn = QPushButton("取消")

        nav.addWidget(self._cancel_btn)
        nav.addStretch()
        nav.addWidget(self._back_btn)
        nav.addWidget(self._next_btn)

        self._back_btn.clicked.connect(self._prev_step)
        self._next_btn.clicked.connect(self._next_step)
        self._cancel_btn.clicked.connect(self.reject)

        main_layout.addLayout(nav)

        self._update_nav()
        self._populate_sheet_list()

    # ---- Step 0: Sheet 选择 ----

    def _build_step_sheet(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        title = QLabel("第 1 步：选择工作表")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel(
            "已自动分析文件中的全部 Sheet（v1.2.1 优化评分策略：\n"
            "综合考虑 Sheet 名称、表格结构和字段关键词）。\n"
            "请选择要作为规模表导入的工作表。"
        )
        hint.setStyleSheet("color: #555;")
        layout.addWidget(hint)

        self._sheet_table = QTableWidget(w)
        self._sheet_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sheet_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._sheet_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sheet_table.setColumnCount(4)
        self._sheet_table.setHorizontalHeaderLabels(["选择", "工作表名", "评分", "说明"])
        self._sheet_table.horizontalHeader().setStretchLastSection(True)
        self._sheet_table.verticalHeader().setVisible(False)
        self._sheet_table.setAlternatingRowColors(True)
        layout.addWidget(self._sheet_table, 1)

        return w

    def _populate_sheet_list(self) -> None:
        self._sheet_table.setRowCount(len(self._candidates))
        for i, c in enumerate(self._candidates):
            chosen_item = QTableWidgetItem("✓" if i == 0 else "")
            chosen_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._sheet_table.setItem(i, 0, chosen_item)

            self._sheet_table.setItem(i, 1, QTableWidgetItem(c["sheet_name"]))
            score_item = QTableWidgetItem(f"{c['score']:.3f}")
            if c["score"] >= 0.7:
                score_item.setForeground(Qt.GlobalColor.darkGreen)
            elif c["score"] >= 0.4:
                score_item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                score_item.setForeground(Qt.GlobalColor.red)
            self._sheet_table.setItem(i, 2, score_item)
            self._sheet_table.setItem(i, 3, QTableWidgetItem(c.get("reason", "")))

        self._sheet_table.itemClicked.connect(self._on_sheet_row_clicked)

    def _on_sheet_row_clicked(self, item: QTableWidgetItem) -> None:
        idx = item.row()
        self._selected_sheet_idx = idx
        for r in range(self._sheet_table.rowCount()):
            self._sheet_table.item(r, 0).setText("✓" if r == idx else "")

    # ---- Step 1: 字段映射 ----

    def _build_step_mapping(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        title = QLabel("第 2 步：字段映射")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel("已自动识别字段映射。如有错误请手动修正。")
        hint.setStyleSheet("color: #555;")
        layout.addWidget(hint)

        form_wrap = QWidget(w)
        form = QFormLayout(form_wrap)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._point_name_combo = QComboBox(form_wrap)
        self._point_name_combo.setMinimumWidth(280)
        self._county_combo = QComboBox(form_wrap)
        self._start_combo = QComboBox(form_wrap)
        self._end_combo = QComboBox(form_wrap)

        form.addRow("点位名称列 *：", self._point_name_combo)
        form.addRow("区县列：", self._county_combo)
        form.addRow("起点列：", self._start_combo)
        form.addRow("终点列：", self._end_combo)

        layout.addWidget(form_wrap)

        # 点位生成规则
        self._rule_concat = QCheckBox("使用「起点 - 终点」拼接作为点位名称", w)
        self._rule_concat.setChecked(self._use_concatenation)
        self._rule_concat.toggled.connect(lambda checked: setattr(self, '_use_concatenation', checked))
        layout.addWidget(self._rule_concat)

        self._rule_hint = QLabel("")
        self._rule_hint.setStyleSheet("color: #666; font-size: 12px;")
        self._update_rule_hint()
        layout.addWidget(self._rule_hint)

        layout.addStretch()
        return w

    def _update_rule_hint(self) -> None:
        ptype = self._project_type or "未分类"
        default = "起点+终点拼接" if should_concatenate(self._project_type) else "单字段"
        self._rule_hint.setText(
            f"项目类型：{ptype} —— 默认推荐「{default}」"
        )

    def _populate_mapping_step(self) -> None:
        if not self._selected_headers:
            return

        candidates = build_field_candidates(self._selected_headers)

        def fill_combo(combo: QComboBox, candidates_list: list[str], best: str | None) -> None:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(_NO_MAPPING)
            for h in self._selected_headers:
                combo.addItem(h)
            if best and best in self._selected_headers:
                combo.setCurrentText(best)
            combo.blockSignals(False)

        fill_combo(self._point_name_combo, candidates.point_name_candidates, candidates.point_name)
        fill_combo(self._county_combo, candidates.county_candidates, candidates.county)
        fill_combo(self._start_combo, candidates.start_point_candidates, candidates.start_point)
        fill_combo(self._end_combo, candidates.end_point_candidates, candidates.end_point)

        # 生成动态字段候选（全部非固定字段）
        initial_mapping = self._read_mapping_from_step()
        occupied = set(v for v in initial_mapping.values() if v is not None)
        self._dynamic_candidates = classify_dynamic_fields(self._selected_headers, occupied)
        self._dynamic_fields = []  # 初始为空

    def _read_mapping_from_step(self) -> dict[str, str | None]:
        def val(combo: QComboBox) -> str | None:
            t = combo.currentText()
            return None if t == _NO_MAPPING else t
        return {
            "point_name": val(self._point_name_combo),
            "county": val(self._county_combo),
            "start_point": val(self._start_combo),
            "end_point": val(self._end_combo),
        }

    # ---- Step 2: 动态字段手动添加（v1.2.1 新增） ----

    def _build_step_dynamic(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        title = QLabel("第 3 步：动态字段选择")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel(
            "默认仅导入区县和点位名称。\n"
            "如需导入规模表中的其他列（如长度/芯数/经度/纬度…），请点击「＋ 添加字段」。\n"
            "左侧输入自定义列名（用于详情页展示），右侧选择规模表中对应的列。"
        )
        hint.setStyleSheet("color: #555;")
        layout.addWidget(hint)

        # 当前已选动态字段表格
        self._dyn_table = QTableWidget(w)
        self._dyn_table.setColumnCount(3)
        self._dyn_table.setHorizontalHeaderLabels(["自定义列名", "规模表列", "操作"])
        self._dyn_table.horizontalHeader().setStretchLastSection(False)
        self._dyn_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._dyn_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._dyn_table.setColumnWidth(2, 60)
        self._dyn_table.verticalHeader().setVisible(False)
        self._dyn_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self._dyn_table, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        self._add_field_btn = QPushButton("＋ 添加字段")
        self._add_field_btn.setDefault(True)
        self._add_field_btn.clicked.connect(self._add_dynamic_field)
        btn_row.addWidget(self._add_field_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return w

    def _add_dynamic_field(self) -> None:
        """添加一行动态字段（v1.2.1-patch：修复 QLineEdit 文字绘制区域被压缩）。

        根因：QLineEdit 放入 QTableWidget cellWidget 后，垂直 sizePolicy 为 Preferred，
        Qt 布局计算给 QLineEdit 的高度仅约 21px（字体 13px + 少量）。
        但全局 QSS `padding: 7px 10px` 在渲染时按 7px 上下绘制 padding，
        导致文字实际绘制区域 = 21 - 14(padding) - 2(border) = 5px，
        13px 字体被压扁到 5px 区域 → 文字绘制区域异常。

        修复：setMinimumHeight(32) 强制 QLineEdit 高度 ≥ 字体+padding+border，
        让文字有完整绘制空间。
        """
        row = self._dyn_table.rowCount()
        self._dyn_table.setRowCount(row + 1)

        # 行高 42px：容器 margin(4*2) + QLineEdit 32px + 余量 2px
        self._dyn_table.setRowHeight(row, 42)

        # 1. 自定义列名输入框
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("请输入自定义列名")
        name_edit.setMinimumWidth(100)
        # 关键：强制最小高度，防止 QSS padding 把文字压扁
        name_edit.setMinimumHeight(32)

        # 2. 容器包裹输入框
        name_container = QWidget()
        name_layout = QHBoxLayout(name_container)
        name_layout.addWidget(name_edit)
        name_layout.setContentsMargins(6, 4, 6, 4)
        name_container.setLayout(name_layout)

        # 3. 将包裹后的容器填入表格第 0 列
        self._dyn_table.setCellWidget(row, 0, name_container)

        # 规模表列选择
        col_combo = QComboBox()
        col_combo.addItem("请选择...")
        for dc in self._dynamic_candidates:
            col_combo.addItem(dc["label"], dc["name"])
        col_combo.setMinimumHeight(32)  # 同样防止压缩

        col_container = QWidget()
        col_layout = QHBoxLayout(col_container)
        col_layout.addWidget(col_combo)
        col_layout.setContentsMargins(6, 4, 6, 4)
        col_container.setLayout(col_layout)

        self._dyn_table.setCellWidget(row, 1, col_container)

        # 自动填充已知概念（仍引用原始 name_edit，容器持有其所有权）
        col_combo.currentIndexChanged.connect(
            lambda idx, r=row, cb=col_combo, ne=name_edit: self._on_dyn_col_changed(r, cb, ne)
        )

        # 删除按钮
        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(40)
        del_btn.clicked.connect(lambda: self._remove_dynamic_field(row))
        self._dyn_table.setCellWidget(row, 2, del_btn)

    def _on_dyn_col_changed(self, row: int, combo: QComboBox, name_edit: QLineEdit) -> None:
        """当规模表列选择变化时，自动填充自定义列名为已知概念标签。"""
        idx = combo.currentIndex()
        if idx <= 0:
            return
        if not name_edit.text().strip():
            # 自动填充：使用 combo 显示的文本作为默认列名
            name_edit.setText(combo.currentText())

    def _remove_dynamic_field(self, row: int) -> None:
        """删除指定行的动态字段。"""
        self._dyn_table.removeRow(row)

    def _read_dynamic_fields_from_ui(self) -> list[dict]:
        """从 UI 读取当前已选的动态字段（v1.2.1-patch：适配容器包裹结构）。"""
        result: list[dict] = []
        for row in range(self._dyn_table.rowCount()):
            cell_widget = self._dyn_table.cellWidget(row, 0)
            col_cell_widget = self._dyn_table.cellWidget(row, 1)
            if not cell_widget or not col_cell_widget:
                continue

            # v1.2.1-patch：cellWidget 返回容器 QWidget，需从布局中取实际控件
            name_widget = self._unwrap_container(cell_widget)
            col_widget = self._unwrap_container(col_cell_widget)
            if not name_widget or not col_widget:
                continue

            custom_name = name_widget.text().strip() if hasattr(name_widget, 'text') else ""
            combo_idx = col_widget.currentIndex() if hasattr(col_widget, 'currentIndex') else 0

            if not custom_name or combo_idx <= 0:
                continue

            original_name = col_widget.currentData()

            result.append({
                "name": original_name,
                "label": custom_name,
                "type": "user_selected",
                "selected": True,
            })
        return result

    @staticmethod
    def _unwrap_container(container: QWidget) -> QWidget | None:
        """从容器 QWidget 中取出第一个子控件（QLineEdit / QComboBox）。

        如果传入的不是容器（直接是目标控件本身），则直接返回。
        """
        layout = container.layout()
        if layout is not None and layout.count() > 0:
            item = layout.itemAt(0)
            if item is not None:
                return item.widget()
        return container

    # ---- Step 3: 导入预览 ----

    def _build_step_preview(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        title = QLabel("第 4 步：导入预览")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel("")
        info.setObjectName("PreviewInfo")
        info.setStyleSheet("color: #555;")
        self._preview_info = info
        layout.addWidget(info)

        self._preview_table = QTableWidget(w)
        self._preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.verticalHeader().setVisible(False)
        self._preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._preview_table, 1)

        hint2 = QLabel("确认无误后点击「导入」开始写入数据库。")
        hint2.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(hint2)
        return w

    def _refresh_preview(self) -> None:
        current_mapping = self._read_mapping_from_step()
        all_rows = self._selected_data_rows
        dyn_fields = self._dynamic_fields

        rows = build_preview_rows(
            all_rows, current_mapping, dyn_fields,
            self._use_concatenation, _PREVIEW_ROWS,
        )

        preview_headers = ["区县", "点位名称"]
        preview_headers += [df["label"] for df in dyn_fields]

        self._preview_table.setColumnCount(len(preview_headers))
        self._preview_table.setHorizontalHeaderLabels(preview_headers)
        self._preview_table.setRowCount(len(rows))

        for r, item in enumerate(rows):
            self._preview_table.setItem(r, 0, QTableWidgetItem(item.get("county", "")))
            self._preview_table.setItem(r, 1, QTableWidgetItem(item.get("point_name", "")))
            for i, df in enumerate(dyn_fields):
                self._preview_table.setItem(
                    r, 2 + i,
                    QTableWidgetItem(str(item.get(df["name"], "")))
                )

        stats = build_point_records_with_stats(
            all_rows, current_mapping, dyn_fields, self._use_concatenation,
        )
        duplicate_hint = (
            f"　预计导入 {len(stats.records)} 个唯一点位，重复 {stats.skipped_duplicates} 行将跳过"
            if stats.skipped_duplicates else "　导入时将按点位/任务名称自动去重"
        )
        self._preview_info.setText(
            f"Sheet：{self._candidates[self._selected_sheet_idx]['sheet_name']}　"
            f"字段映射：{self._describe_mapping(current_mapping)}　"
            f"生成规则：{'起点+终点' if self._use_concatenation else '单字段'}　"
            f"动态字段：{len(dyn_fields)} 个　"
            f"预览前 {len(rows)} 条（共 {len(all_rows)} 条）"
            f"{duplicate_hint}"
        )

        if preview_headers:
            self._preview_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch
            )

    def _describe_mapping(self, m: dict) -> str:
        def v(key: str, label: str) -> str:
            val = m.get(key)
            return f"{label}={val}" if val else ""
        parts = [v(k, n) for k, n in [
            ("point_name", "点位"), ("county", "区县"),
            ("start_point", "起点"), ("end_point", "终点"),
        ] if m.get(k)]
        return "　".join(parts) if parts else "未设置"

    # ==================================================================
    # 导航
    # ==================================================================

    def _update_nav(self) -> None:
        step = self._step_stack.currentIndex()
        self._back_btn.setEnabled(step > 0)
        if step == 3:
            self._next_btn.setText("导入")
            self._next_btn.setEnabled(True)
        else:
            self._next_btn.setText("下一步")
            self._next_btn.setEnabled(True)

    def _prev_step(self) -> None:
        cur = self._step_stack.currentIndex()
        if cur > 0:
            self._step_stack.setCurrentIndex(cur - 1)
            self._update_nav()

    def _next_step(self) -> None:
        cur = self._step_stack.currentIndex()
        if cur == 0:
            # Sheet 选择 → 字段映射
            self._selected_headers = self._candidates[self._selected_sheet_idx]["headers"]
            self._selected_data_rows = self._candidates[self._selected_sheet_idx]["data_rows"]
            self._populate_mapping_step()
            self._step_stack.setCurrentIndex(1)
            self._update_nav()
        elif cur == 1:
            # 字段映射 → 动态字段
            current_mapping = self._read_mapping_from_step()
            if not current_mapping.get("point_name"):
                QMessageBox.warning(self, "字段未选择", "点位名称列为必选字段，请选择一个列映射。")
                return

            # 刷新动态字段候选（排除已选固定字段）
            occupied = set(v for v in current_mapping.values() if v is not None)
            self._dynamic_candidates = classify_dynamic_fields(self._selected_headers, occupied)

            # 清空并重建动态字段表格
            self._dyn_table.setRowCount(0)

            self._step_stack.setCurrentIndex(2)
            self._update_nav()
        elif cur == 2:
            # 动态字段 → 预览
            # 保存当前动态字段选择
            self._dynamic_fields = self._read_dynamic_fields_from_ui()
            self._refresh_preview()
            self._step_stack.setCurrentIndex(3)
            self._update_nav()
        elif cur == 3:
            # 预览 → 确认导入
            self._do_import()

    def _do_import(self) -> None:
        """校验并确认导入（v1.2.1-patch：延迟关闭防止生命周期冲突闪退）。"""
        current_mapping = self._read_mapping_from_step()
        if not current_mapping.get("point_name"):
            QMessageBox.warning(self, "错误", "点位名称列为必选字段。")
            return

        self._mapping = current_mapping
        # 确保使用最新的动态字段
        if not self._dynamic_fields:
            self._dynamic_fields = self._read_dynamic_fields_from_ui()

        # 保存 Project Profile
        if self._project_id is not None:
            try:
                conn = Database.open_db_connection(self._db_path)
                try:
                    project_profile_repository.init_project_profiles_table(conn)
                    project_profile_repository.upsert_profile(
                        conn, self._project_id,
                        {
                            "sheet_name": self._candidates[self._selected_sheet_idx]["sheet_name"],
                            "point_name_field": current_mapping["point_name"],
                            "county_field": current_mapping["county"],
                            "start_point_field": current_mapping["start_point"],
                            "end_point_field": current_mapping["end_point"],
                            "use_concatenation": self._use_concatenation,
                            "dynamic_fields": self._dynamic_fields,
                        },
                    )
                    logger.info("规模表配置已保存：project_id=%s", self._project_id)
                except Exception as exc:
                    logger.warning("保存项目配置失败：%s", exc)
                finally:
                    conn.close()
            except Exception as exc:
                logger.warning("保存项目配置时数据库打开失败：%s", exc)

        # v1.2.1-patch：延迟 100ms 关闭向导，避免在按钮点击回调链中同步销毁
        # 对话框导致 Qt 底层生命周期冲突 → segfault → 主窗口连带闪退
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self.accept)

    def _try_load_profile(self) -> None:
        """尝试加载已保存的 Project Profile。"""
        if self._project_id is None:
            return
        try:
            conn = Database.open_db_connection(self._db_path)
        except Exception:
            return
        try:
            project_profile_repository.init_project_profiles_table(conn)
            profile = project_profile_repository.fetch_profile(conn, self._project_id)
        except Exception:
            return
        finally:
            conn.close()

        if profile is None:
            return

        saved_sheet = profile.get("sheet_name")
        if saved_sheet:
            for i, c in enumerate(self._candidates):
                if c["sheet_name"] == saved_sheet:
                    self._selected_sheet_idx = i
                    self._selected_headers = c["headers"]
                    self._selected_data_rows = c["data_rows"]
                    for r in range(self._sheet_table.rowCount()):
                        self._sheet_table.item(r, 0).setText("✓" if r == i else "")
                    break

        self._mapping = {
            "point_name": profile.get("point_name_field"),
            "county": profile.get("county_field"),
            "start_point": profile.get("start_point_field"),
            "end_point": profile.get("end_point_field"),
        }
        self._use_concatenation = profile.get("use_concatenation", False)
        self._dynamic_fields = profile.get("dynamic_fields", [])

        logger.info("已加载项目配置：project_id=%s, sheet=%s",
                     self._project_id, saved_sheet)

    # ==================================================================
    # 获取最终结果
    # ==================================================================

    def get_result(self) -> dict:
        """获取向导确认后的最终配置。"""
        return {
            "sheet_name": self._candidates[self._selected_sheet_idx]["sheet_name"],
            "mapping": self._mapping,
            "dynamic_fields": self._dynamic_fields,
            "use_concatenation": self._use_concatenation,
            "selected_data_rows": self._selected_data_rows,
        }

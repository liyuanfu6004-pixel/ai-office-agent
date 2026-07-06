"""项目详情页面模块（v1.1.0 规模表智能识别引擎 + 动态列展示）。

**双层布局结构**（主 QVBoxLayout 嵌套中间 QHBoxLayout）：

1. 顶部工具栏（Fixed）：「返回项目列表」+「导入项目明细表」按钮
2. **中间区域（QHBoxLayout 横向并排）**：
   - 左：项目概览卡（60%，stretch=3）—— 项目名称/编码/类型/年份/状态
   - 右：项目整体资料面板（40%，stretch=2）—— PDF/Word/Excel/其他资料/
     点位文件夹以外的文件夹
   - 两侧均使用 vertical=Preferred——QHBoxLayout 自动将两侧拉齐同高
3. 筛选栏（Fixed）：区县下拉 + 点位名称搜索 + 图纸状态 + 预算状态
4. 点位列表（Expanding，stretch=1）：占剩余全部纵向空间
   - 固定 5 列：序号 / 区县 / 点位名称 / 图纸状态 / 预算状态
   - 动态列：规模表动态字段（v1.1.0 从 point_dictionary.dynamic_data 加载）

v1.1.0 规模表智能识别引擎变化：
- **导入向导**：「导入项目明细表」→ ScaleTableWizard 四步向导
  （Sheet选择→字段映射→生成规则→预览）替代旧版关键词粗匹配
- **Project Profile**：用户修正的字段映射保存到 project_profiles 表，
  下次导入同项目时直接复用
- **动态列展示**：规模表动态字段从 point_dictionary.dynamic_data JSON
  加载，自动追加为点位列表的列
- **智能字段识别**：不写死字段名，全部关键词匹配 + 用户可修正

v1.0.0 沙盒模式保留：
- 沙盒文件扫描：在 D:\\AI-Office-Agent-Test\\ 中按项目名称匹配文件夹
- 真实状态计算：图纸状态 = 图纸文件夹存在 *.dwg；预算状态 = 预算文件夹有文件
- 安全约束：仅扫描 TEST_ROOT_PATH，禁止访问其他路径

v0.9.4 关键修复：
- 中间区域概览/资料高度一致（QHBoxLayout + Preferred 自动同高）
- 系统界面纵向可自由缩放（删除 resizeEvent 半页强制，点表 stretch=1 自然分配）

图纸/预算状态判定规则（严格，按需求）：
- 图纸状态 = 仅判断 CAD 文件：图纸文件夹存在 *.dwg →「有」；否则 →「无」
- 预算状态：预算文件夹存在且有文件 →「有」；否则 →「无」

详情页不属于导航树，由内容区注册并切换显示；「返回」按钮回到全部项目列表。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ....config import AppConfig
from ....core import project_profile_repository, projects_repository
from ....core.database import Database
from ....core.scale_table_engine import (
    build_point_records,
    detect_best_sheet,
    read_all_sheets,
)
from ....core.scanner import (  # v1.2.3: 保留 TEST_ROOT_PATH 导入
    TEST_ROOT_PATH,
)
from ....data_import import excel_reader
from ....data_import.scale_import_worker import ScaleImportWorker
from ....utils.logger import setup_logger
from ..scale_table_wizard import ScaleTableWizard
from .base_page import BasePage

logger = setup_logger()

# Excel 文件过滤
_EXCEL_FILTER = "Excel 文件 (*.xlsx)"

# ====================================================================
# 图纸 / 预算状态判定规则（纯函数，严格按需求）
# ====================================================================

# 状态取值
_DRAWING_HAS = "有"
_DRAWING_NONE = "无"
_BUDGET_HAS = "有"
_BUDGET_NONE = "无"


def judge_drawing_status(has_cad: bool, has_pdf: bool) -> str:
    """图纸状态判定（仅判断 CAD 文件）。

    规则：
    - 存在 CAD 文件 →「有」
    - 仅 PDF 无 CAD →「无」
    - PDF 不参与判断

    Args:
        has_cad: 是否存在 CAD 文件。
        has_pdf: 是否存在 PDF 文件（不参与判定，仅为参数完整）。

    Returns:
        「有」或「无」。
    """
    if has_cad:
        return _DRAWING_HAS
    return _DRAWING_NONE


def judge_budget_status(has_budget_folder: bool) -> str:
    """预算状态判定。

    规则：预算文件夹存在 →「有」；否则 →「无」。

    Args:
        has_budget_folder: 预算文件夹是否存在。

    Returns:
        「有」或「无」。
    """
    return _BUDGET_HAS if has_budget_folder else _BUDGET_NONE


# ====================================================================
# 点位列表表格（固定 5 列 + 动态列机制）
# ====================================================================

# 固定列定义：（列标题, 列宽）。前 5 列顺序与内容不可改。
_POINT_FIXED_COLUMNS: list[tuple[str, int]] = [
    ("序号", 56),
    ("区县", 110),
    ("点位名称", 220),
    ("图纸状态", 100),
    ("预算状态", 100),
]

# 固定列索引常量
_COL_SEQ = 0
_COL_COUNTY = 1
_COL_NAME = 2
_COL_DRAWING = 3
_COL_BUDGET = 4

# 筛选占位项
_FILTER_ALL = "全部"


class PointListTable(QTableWidget):
    """点位列表表格：固定 5 列 + 动态列。

    动态列通过 set_dynamic_columns 设置（来自规模表/明细表用户映射字段），
    追加在固定 5 列之后。本版无数据源，渲染为空。

    本版不接入规模表、不解析文件；固定列的图纸/预算状态由
    judge_drawing_status / judge_budget_status 在有数据时计算。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dynamic_columns: list[str] = []
        self._setup_common()
        self._apply_columns()

    def _setup_common(self) -> None:
        """通用表格属性：整行单选、只读、交替行底色、表头可排序、隐藏左侧行号。"""
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)

        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.setStretchLastSection(True)

    def _apply_columns(self) -> None:
        """按固定列 + 动态列设置表头与列宽。"""
        titles = [c[0] for c in _POINT_FIXED_COLUMNS] + list(self._dynamic_columns)
        widths = [c[1] for c in _POINT_FIXED_COLUMNS] + [120] * len(self._dynamic_columns)
        self.setColumnCount(len(titles))
        self.setHorizontalHeaderLabels(titles)
        for col, w in enumerate(widths):
            self.setColumnWidth(col, w)
        self.setRowCount(0)

    def set_dynamic_columns(self, columns: list[str]) -> None:
        """设置动态列（规模表/明细表用户映射字段），追加在固定列之后。"""
        self._dynamic_columns = list(columns)
        self._apply_columns()

    def load_points(self, points: list[dict], dynamic_values: list[dict] | None = None) -> None:
        """渲染点位行。

        Args:
            points: 每项含 county / name / has_cad / has_pdf / has_budget_folder。
            dynamic_values: 与 points 等长的动态列取值字典（键为动态列名），
                本版调用方无数据，可省略。
        """
        self.setSortingEnabled(False)
        self.setRowCount(len(points))
        for row, p in enumerate(points):
            self._fill_row(row, p, dynamic_values)
        self.setSortingEnabled(True)

    def _fill_row(self, row: int, p: dict, dynamic_values: list[dict] | None) -> None:
        """填充一行：固定 5 列 + 动态列。"""
        seq = row + 1
        county = str(p.get("county") or "")
        name = str(p.get("name") or "")
        drawing = judge_drawing_status(bool(p.get("has_cad")), bool(p.get("has_pdf")))
        budget = judge_budget_status(bool(p.get("has_budget_folder")))

        self._set_cell(row, _COL_SEQ, str(seq), align=True)
        self._set_cell(row, _COL_COUNTY, county)
        self._set_cell(row, _COL_NAME, name)
        self._set_cell(row, _COL_DRAWING, drawing, align=True)
        self._set_cell(row, _COL_BUDGET, budget, align=True)

        # 动态列：从 dynamic_values 取对应列的值
        if dynamic_values and row < len(dynamic_values):
            dv = dynamic_values[row]
            for i, col_name in enumerate(self._dynamic_columns):
                self._set_cell(
                    row, len(_POINT_FIXED_COLUMNS) + i,
                    str(dv.get(col_name, "")),
                )

    def _set_cell(self, row: int, col: int, text: str, align: bool = False) -> None:
        item = QTableWidgetItem(text)
        if align:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, col, item)


# ====================================================================
# 项目整体资料面板（点位文件夹以外的文件夹级文件分类）
# ====================================================================

# 资料分类（点位文件夹以外的项目级文件夹文件）
_DOC_CATEGORIES: list[str] = [
    "PDF",
    "Word",
    "Excel",
    "其他资料",
    "点位文件夹以外的文件夹",
]


class ProjectDocumentsPanel(QFrame):
    """项目整体资料面板。

    展示项目文件夹级文件（非点位文件夹内）的分类。本版不解析文件，
    仅展示分类标签占位，为后续接入文件整理预留结构。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DocumentsPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(6)

        title = QLabel("项目整体资料", self)
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        hint = QLabel("项目文件夹级文件（点位文件夹以外）", self)
        hint.setObjectName("PanelHint")
        layout.addWidget(hint)

        # 各分类占位（紧凑单行）
        for cat in _DOC_CATEGORIES:
            row = QHBoxLayout()
            row.setSpacing(8)
            name_label = QLabel(cat, self)
            name_label.setMinimumWidth(150)
            count_label = QLabel("—", self)  # 无数据占位
            count_label.setObjectName("DocCount")
            row.addWidget(name_label)
            row.addStretch()
            row.addWidget(count_label)
            layout.addLayout(row)

        layout.addStretch()


# ====================================================================
# 筛选栏
# ====================================================================


class PointFilterBar(QWidget):
    """点位列表筛选栏：区县 + 点位名称搜索 + 图纸状态 + 预算状态。

    支持组合条件。通过 filter_changed 信号通知外部重新筛选。
    """

    # 任一筛选项变化时发出
    filter_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 区县筛选
        layout.addWidget(QLabel("区县：", self))
        self.county_combo = QComboBox(self)
        self.county_combo.setMinimumWidth(120)
        self.county_combo.addItem(_FILTER_ALL)
        layout.addWidget(self.county_combo)

        # 点位名称搜索
        layout.addWidget(QLabel("点位名称：", self))
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("搜索点位名称 ...")
        self.name_edit.setClearButtonEnabled(True)
        layout.addWidget(self.name_edit, 1)

        # 图纸状态筛选
        layout.addWidget(QLabel("图纸状态：", self))
        self.drawing_combo = QComboBox(self)
        self.drawing_combo.addItem(_FILTER_ALL)
        self.drawing_combo.addItems([_DRAWING_HAS, _DRAWING_NONE])
        layout.addWidget(self.drawing_combo)

        # 预算状态筛选
        layout.addWidget(QLabel("预算状态：", self))
        self.budget_combo = QComboBox(self)
        self.budget_combo.addItem(_FILTER_ALL)
        self.budget_combo.addItems([_BUDGET_HAS, _BUDGET_NONE])
        layout.addWidget(self.budget_combo)

        # 信号
        self.county_combo.currentIndexChanged.connect(self.filter_changed.emit)
        self.drawing_combo.currentIndexChanged.connect(self.filter_changed.emit)
        self.budget_combo.currentIndexChanged.connect(self.filter_changed.emit)
        self.name_edit.textChanged.connect(self.filter_changed.emit)

    def set_counties(self, counties: list[str]) -> None:
        """刷新区县下拉选项（保留「全部」）。"""
        cur = self.county_combo.currentText()
        self.county_combo.blockSignals(True)
        self.county_combo.clear()
        self.county_combo.addItem(_FILTER_ALL)
        self.county_combo.addItems(counties)
        idx = self.county_combo.findText(cur) if cur else 0
        self.county_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.county_combo.blockSignals(False)

    def filters(self) -> dict:
        """返回当前筛选条件。"""
        def combo_val(c: QComboBox) -> str | None:
            t = c.currentText()
            return None if t == _FILTER_ALL else t
        return {
            "county": combo_val(self.county_combo),
            "name": self.name_edit.text().strip().lower(),
            "drawing": combo_val(self.drawing_combo),
            "budget": combo_val(self.budget_combo),
        }


# ====================================================================
# 项目详情页
# ====================================================================


class ProjectDetailPage(BasePage):
    """项目详情页面（v0.8.0 UI 重构，无树结构）。

    Args:
        config: 应用配置，用于访问数据库。
        parent: 父控件。
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title="项目详情", subtitle="项目概览与点位结构浏览", parent=parent)
        self._config = config or AppConfig()
        self._project_id: int | None = None

        self._setup_header_bar()
        self._setup_middle_area()        # 中间区域：QHBoxLayout 横向并排 概览(60%) / 资料(40%)
        self._setup_filter_and_points()  # 筛选栏 + 点位列表(stretch=1, 占剩余≥50%)
        self._clear_overview()

    # ------------------------------------------------------------------ 尺寸：释放纵向缩放

    def resizeEvent(self, event) -> None:
        """窗口尺寸变化时确保点位列表不锁死最小高度。

        v0.9.4：移除此前 setMinimumHeight(half) 的半页强制——它导致窗口纵向只能
        拉大不能缩小。改为 setMinimumHeight(0) 让 stretch=1 自然分配剩余空间，
        窗口可自由缩放。
        """
        super().resizeEvent(event)
        if hasattr(self, "point_table"):
            self.point_table.setMinimumHeight(0)

    # ------------------------------------------------------------------ 顶部工具栏

    def _setup_header_bar(self) -> None:
        """页头右侧放「返回项目列表」+「导入项目明细表」按钮。"""
        bar = QWidget(self)
        bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.import_detail_btn = QPushButton("导入项目明细表", bar)
        self.import_detail_btn.setDefault(True)
        self.back_btn = QPushButton("返回项目列表", bar)
        layout.addStretch()
        layout.addWidget(self.import_detail_btn)
        layout.addWidget(self.back_btn)

        self.content_layout.addWidget(bar)
        # 绑定导入按钮
        self.import_detail_btn.clicked.connect(self._on_import_detail_clicked)

    # ------------------------------------------------------------------ 中间区域（QHBoxLayout 横向并排）

    def _setup_middle_area(self) -> None:
        """中间区域：QHBoxLayout 横向并排「项目概览(60%)」+「项目整体资料(40%)」。

        v0.9.4：概览与资料均用 vertical=Preferred——QHBoxLayout 自动将两侧拉齐到
        同高，修复此前右侧资料面板（150px）小于左侧概览（241px）的高度不一致问题。
        宽度比例 60/40（stretch 3:2）。中间区域整体 vertical=Preferred，高度跟随
        内容紧凑，把纵向空间让给底部点位列表。
        """
        middle = QWidget(self)
        middle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        middle_layout = QHBoxLayout(middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(12)

        # 左：项目概览卡（60%）
        overview_card = QFrame(middle)
        overview_card.setObjectName("OverviewCard")
        overview_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        ov_layout = QVBoxLayout(overview_card)
        ov_layout.setContentsMargins(16, 12, 16, 12)
        ov_layout.setSpacing(8)

        ov_title = QLabel("项目概览", overview_card)
        ov_title.setObjectName("PanelTitle")
        ov_layout.addWidget(ov_title)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self.name_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.year_edit = QLineEdit()
        self.status_edit = QLineEdit()
        for w in (self.name_edit, self.code_edit, self.type_edit,
                  self.year_edit, self.status_edit):
            w.setReadOnly(True)
            w.setMinimumHeight(24)  # 防止被压缩导致文字截断
        form.addRow("项目名称：", self.name_edit)
        form.addRow("项目编码：", self.code_edit)
        form.addRow("项目类型：", self.type_edit)
        form.addRow("年份：", self.year_edit)
        form.addRow("状态：", self.status_edit)
        ov_layout.addLayout(form)

        # 右：项目整体资料面板（40%）
        self.documents_panel = ProjectDocumentsPanel(middle)
        self.documents_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # 横向并排，比例 3:2 = 60%:40%
        middle_layout.addWidget(overview_card, 3)
        middle_layout.addWidget(self.documents_panel, 2)

        self.content_layout.addWidget(middle)

    # ------------------------------------------------------------------ 筛选栏 + 点位列表

    def _setup_filter_and_points(self) -> None:
        """筛选栏（固定高度）+ 点位列表（Expanding，占剩余全部纵向空间）。"""
        self.filter_bar = PointFilterBar(self)
        self.filter_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.filter_bar.filter_changed.connect(self._apply_filter)
        self.content_layout.addWidget(self.filter_bar)

        self.point_table = PointListTable(self)
        # 核心区域：纵向 Expanding，stretch=1，占剩余全部 vertical space
        self.point_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.content_layout.addWidget(self.point_table, 1)

    # ------------------------------------------------------------------ 数据载入

    def load_project(self, project_id: int) -> bool:
        """按 id 载入项目并刷新概览与点位列表。

        v1.0.0：点位列表从 point_dictionary 表加载（标准点位字典），
        不再渲染为空表。

        Returns:
            True 表示载入成功；False 表示项目不存在。
        """
        conn = Database.open_db_connection(self._config.database.path)
        try:
            projects_repository.init_projects_table(conn)
            projects_repository.init_point_dictionary_table(conn)
            row = projects_repository.fetch_project_by_id(conn, project_id)
        finally:
            conn.close()

        if row is None:
            logger.warning("项目详情：id=%s 不存在", project_id)
            self._project_id = None
            self._clear_overview()
            return False

        self._project_id = int(row["id"])
        self._render_overview(row)
        # v1.0.0：从 point_dictionary 表加载点位
        self._load_points_from_db()
        logger.info("打开项目详情：id=%s", project_id)
        return True

    def _load_points_from_db(self) -> None:
        """从 point_dictionary 表加载点位，使用缓存扫描结果更新状态。

        v1.4 修复：不再触发沙盒扫描。改为从 scan_result 表读取缓存状态。
        打开项目 0 卡顿。
        """
        if self._project_id is None:
            self.point_table.setRowCount(0)
            return

        conn = Database.open_db_connection(self._config.database.path)
        try:
            points = projects_repository.fetch_points_with_status(
                conn, self._project_id
            )
            # 获取项目名称
            proj_row = projects_repository.fetch_project_by_id(conn, self._project_id)
            project_name = proj_row["project_name"] if proj_row else None
        finally:
            conn.close()

        # v1.1.0：从 point_dictionary.dynamic_data 提取动态列
        dynamic_columns = self._extract_dynamic_columns(points)
        self.point_table.set_dynamic_columns(dynamic_columns)

        # v1.4：从 scan_result 表加载缓存状态（不触发扫描）
        drawing_status_map: dict[str, str] = {}
        budget_status_map: dict[str, str] = {}
        try:
            from ....core.scan_controller import load_scan_results_from_db
            conn = Database.open_db_connection(self._config.database.path)
            try:
                cached_items = load_scan_results_from_db(conn, self._project_id)
                if cached_items:
                    for item in cached_items:
                        pname = item.standard_point_name
                        drawing_status_map[pname] = item.cad_status
                        budget_status_map[pname] = item.budget_status
            finally:
                conn.close()
        except Exception:
            pass  # 缓存不存在时使用默认"无"状态

        # 转为 PointListTable.load_points 所需格式（v1.2.3：区县归一化 + 过滤）
        from ....core.region_profile import get_profile
        profile = get_profile()

        formatted: list[dict] = []
        dynamic_values: list[dict] = []
        active_counties: set[str] = set()
        for p in points:
            pname = p["standard_point_name"]
            # 区县归一化
            raw_county = p.get("county", "")
            county = profile.normalize(raw_county) or raw_county
            # 非负责区县跳过
            if raw_county and not profile.is_active(raw_county):
                continue

            drawing = drawing_status_map.get(pname, p["drawing_status"])
            budget = budget_status_map.get(pname, p["budget_status"])
            formatted.append({
                "county": county,
                "name": pname,
                "has_cad": drawing == "有",
                "has_pdf": False,
                "has_budget_folder": budget == "有",
            })
            active_counties.add(county)
            # v1.1.0：动态字段值
            dd = p.get("dynamic_data") or {}
            row_dynamic = {}
            for col_name in dynamic_columns:
                row_dynamic[col_name] = dd.get(col_name, "")
            dynamic_values.append(row_dynamic)

        self.point_table.load_points(formatted, dynamic_values)

        # 区县下拉同步（仅活跃区县）
        self.filter_bar.set_counties(sorted(active_counties))

        logger.info(
            "点位列表加载完成（v1.4 缓存）：项目 id=%s，%d 个点位（动态列=%d）",
            self._project_id, len(points), len(dynamic_columns),
        )

    @staticmethod
    def _extract_dynamic_columns(points: list[dict]) -> list[str]:
        """从点位字典的 dynamic_data 中提取全部动态字段名（去重，保持首见顺序）。

        v1.1.0 引入：规模表动态字段自动作为点位列表的额外列展示。
        """
        seen: set[str] = set()
        result: list[str] = []
        for p in points:
            dd = p.get("dynamic_data")
            if not dd or not isinstance(dd, dict):
                continue
            for key in dd:
                if key not in seen:
                    seen.add(key)
                    result.append(key)
        return result

    def _try_match_from_sandbox(
        self, project_name: str, points: list[dict]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """v1.2.3：使用 FileIndex 全局匹配，不依赖目录结构假设。

        Returns:
            (drawing_status_map, budget_status_map): 键为 standard_point_name。
        """
        drawing_map: dict[str, str] = {}
        budget_map: dict[str, str] = {}

        try:
            from ....core.scanner import TEST_ROOT_PATH, scan_with_file_index, match_points_from_index
            from ....core.matcher import match_folder

            projects = scan_with_file_index(str(TEST_ROOT_PATH))

            matched_project = None
            for proj in projects:
                result = match_folder(project_name, proj.name)
                if result.is_match:
                    matched_project = proj
                    break

            if matched_project is None:
                logger.debug("沙盒中未找到匹配的项目文件夹：%s", project_name)
                return drawing_map, budget_map

            logger.info(
                "v1.2.3 沙盒匹配到项目：%s（FileIndex: %d 文件, %d 目录）",
                matched_project.path,
                len(matched_project.file_index.files) if matched_project.file_index else 0,
                len(matched_project.file_index.dirs) if matched_project.file_index else 0,
            )

            point_dict = [
                {"id": p["id"], "standard_point_name": p["standard_point_name"],
                 "county": p.get("county", "")}
                for p in points
            ]
            matches, _unmatched, conflict_files = match_points_from_index(
                matched_project, point_dict
            )

            for m in matches:
                if m.is_matched and m.point_name:
                    drawing_map[m.point_name] = m.drawing_status
                    budget_map[m.point_name] = m.budget_status

            logger.info(
                "v1.2.3 沙盒状态计算完成：%d 个点位有图纸状态，%d 个有预算状态",
                len(drawing_map), len(budget_map),
            )

        except Exception as exc:
            logger.debug("v1.2.3 FileIndex 扫描失败，使用默认状态：%s", exc)

        return drawing_map, budget_map

    def _render_overview(self, row) -> None:
        """把单行项目记录填入概览表单（只读）。

        v0.9.0：页头标题不再显示项目名称+编码（概览卡内已有，避免重复），
        固定为 BasePage 的静态「项目详情」标题。
        """
        name = row["project_name"] or ""
        code = row["project_code"] or ""
        ptype = row["project_type"] or "未分类"
        year = row["year"]
        year_text = str(year) if year is not None else ""
        status = row["status"] or ""

        self.name_edit.setText(name)
        self.code_edit.setText(code)
        self.type_edit.setText(ptype)
        self.year_edit.setText(year_text)
        self.status_edit.setText(status)

    def _clear_overview(self) -> None:
        """无数据时清空概览与点位列表。"""
        for w in (self.name_edit, self.code_edit, self.type_edit,
                  self.year_edit, self.status_edit):
            w.clear()
        self.point_table.setRowCount(0)
        self.filter_bar.set_counties([])

    # ------------------------------------------------------------------ 筛选

    def _apply_filter(self) -> None:
        """组合筛选点位列表行。

        v1.0.0 启用筛选：区县精确匹配 + 名称子串（忽略大小写）
        + 图纸状态/预算状态精确匹配。
        """
        filters = self.filter_bar.filters()
        for row in range(self.point_table.rowCount()):
            county_item = self.point_table.item(row, _COL_COUNTY)
            name_item = self.point_table.item(row, _COL_NAME)
            drawing_item = self.point_table.item(row, _COL_DRAWING)
            budget_item = self.point_table.item(row, _COL_BUDGET)

            county = county_item.text() if county_item else ""
            name = name_item.text().lower() if name_item else ""
            drawing = drawing_item.text() if drawing_item else ""
            budget = budget_item.text() if budget_item else ""

            visible = True
            if filters["county"] and county != filters["county"]:
                visible = False
            if filters["name"] and filters["name"] not in name:
                visible = False
            if filters["drawing"] and drawing != filters["drawing"]:
                visible = False
            if filters["budget"] and budget != filters["budget"]:
                visible = False
            self.point_table.setRowHidden(row, not visible)

    # ------------------------------------------------------------------ 导入项目规模表（v1.1.0 智能识别引擎）

    def _on_import_detail_clicked(self) -> None:
        """「导入项目明细表」v1.1.0 规模表智能识别引擎。

        流程：
        1. 选择 .xlsx → 读取全部 Sheet
        2. 自动分析 Sheet 候选（评分排序）
        3. 打开 ScaleTableWizard 四步向导
        4. 用户确认后后台线程导入（写入 point_dictionary + project_profiles）
        5. 刷新点位列表
        """
        if self._project_id is None:
            QMessageBox.warning(self, "提示", "请先从项目列表打开一个项目。")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "选择项目规模表", "", _EXCEL_FILTER,
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            QMessageBox.warning(self, "文件类型错误", "仅支持 .xlsx 格式的 Excel 文件。")
            return

        # Step 1: 读取全部 Sheet
        try:
            all_sheets = read_all_sheets(path)
        except Exception as exc:
            logger.exception("规模表读取失败")
            QMessageBox.critical(self, "读取失败", f"读取 Excel 失败：\n{exc}")
            return

        if not all_sheets:
            QMessageBox.information(self, "提示", "Excel 文件中无任何工作表。")
            return

        # Step 2: 自动分析 Sheet 候选
        candidates = detect_best_sheet(all_sheets)
        if not candidates:
            QMessageBox.information(self, "提示", "未识别到任何可导入的工作表。")
            return

        # Step 3: 获取项目数据
        conn = Database.open_db_connection(self._config.database.path)
        try:
            row = projects_repository.fetch_project_by_id(conn, self._project_id)
            project_type = row["project_type"] if row else None
        finally:
            conn.close()

        # Step 4: 打开向导
        wizard = ScaleTableWizard(
            sheet_candidates=candidates,
            project_type=project_type,
            project_id=self._project_id,
            db_path=self._config.database.path,
            parent=self,
        )
        if not wizard.exec():
            return  # 用户取消

        result = wizard.get_result()
        data_rows = result["selected_data_rows"]
        mapping = result["mapping"]
        dynamic_fields = result["dynamic_fields"]
        use_concatenation = result["use_concatenation"]
        sheet_name = result["sheet_name"]

        if not data_rows:
            QMessageBox.information(self, "提示", "选择的工作表无数据行。")
            return

        # Step 5: 后台导入
        self._run_scale_import(
            data_rows, mapping, dynamic_fields, use_concatenation, sheet_name,
        )

    def _run_scale_import(
        self,
        data_rows: list[dict],
        mapping: dict,
        dynamic_fields: list[dict],
        use_concatenation: bool,
        sheet_name: str,
    ) -> None:
        """在后台线程执行规模表导入（v1.2.1 BugFix：线程安全信号槽，防止闪退）。

        关键修复：worker 信号必须连接到 QObject 实例方法（ProjectDetailPage 的方法），
        并显式指定 QueuedConnection。这样信号会在主线程事件循环中执行，而不是
        在 worker 线程直接调用（后者会违反 Qt 线程亲和性，操作主线程 GUI 控件
        导致 access violation 闪退）。

        之前的实现用 Python 闭包作为 slot，闭包没有 QObject 亲和性，QueuedConnection
        无法生效，slot 在 worker 线程直接执行 → QProgressDialog 在 worker 线程被
        操作 → access violation。
        """
        progress = QProgressDialog("正在导入规模表 ...", "取消", 0, 100, self)
        progress.setWindowTitle("导入中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        self._scale_worker = ScaleImportWorker(data_rows, self._config)
        self._scale_thread = QThread(self)
        self._import_cancelled = False
        self._import_error: str | None = None
        # 保存进度对话框引用，供实例方法槽访问
        self._import_progress = progress
        # 缓存插入数，供 on_succeeded 使用
        self._import_inserted: int | None = None

        self._scale_worker.moveToThread(self._scale_thread)
        self._scale_worker.set_params(
            self._project_id, mapping, dynamic_fields,
            use_concatenation, sheet_name,
        )

        # 信号连接到实例方法（QObject，亲和性在主线程）+ QueuedConnection
        # 确保 slot 在主线程事件循环执行，不在 worker 线程直接调用
        self._scale_worker.progress.connect(
            self._on_import_progress, Qt.ConnectionType.QueuedConnection
        )
        self._scale_worker.succeeded.connect(
            self._on_import_succeeded, Qt.ConnectionType.QueuedConnection
        )
        self._scale_worker.failed.connect(
            self._on_import_failed, Qt.ConnectionType.QueuedConnection
        )

        # 线程结束 → 安全清理（不阻塞、不 terminate）
        self._scale_thread.finished.connect(self._on_import_thread_finished)

        self._scale_thread.started.connect(self._scale_worker.start_import.emit)
        self._scale_thread.start()

        # 取消时安全退出
        progress.canceled.connect(self._on_import_cancel)

    # ------------------------------------------------------------------
    # 导入回调（必须是实例方法，确保 QObject 亲和性在主线程）
    # ------------------------------------------------------------------

    @Slot(int, str)
    def _on_import_progress(self, val: int, msg: str) -> None:
        """进度更新槽（主线程执行）。"""
        try:
            if not self._import_cancelled and hasattr(self, '_import_progress'):
                progress = self._import_progress
                if progress is not None:
                    progress.setLabelText(msg)
                    # 防止重复值触发递归 repaint
                    if progress.value() != val:
                        progress.setValue(val)
        except Exception:
            pass

    @Slot(int, int)
    def _on_import_succeeded(self, inserted: int, _skipped: int) -> None:
        """导入成功槽（主线程执行）。"""
        self._import_inserted = inserted
        try:
            if hasattr(self, '_import_progress') and self._import_progress is not None:
                self._import_progress.close()
        except Exception:
            pass
        # 先刷新 UI，再通知线程退出（不阻塞主线程）
        try:
            self._load_points_from_db()
        except Exception as exc:
            logger.exception("导入后刷新点表失败")
            QMessageBox.warning(self, "警告", f"导入完成但刷新失败：{exc}")
            self._request_thread_quit()
            return
        QMessageBox.information(
            self, "导入完成",
            f"已导入 {inserted} 条点位到点位字典。\n"
            f"（字段配置已保存，下次导入同项目将自动使用）",
        )
        self._request_thread_quit()

    @Slot(str)
    def _on_import_failed(self, err: str) -> None:
        """导入失败槽（主线程执行）。"""
        self._import_error = err
        try:
            if hasattr(self, '_import_progress') and self._import_progress is not None:
                self._import_progress.close()
        except Exception:
            pass
        logger.error("规模表导入失败：%s", err)
        QMessageBox.critical(
            self, "导入失败",
            f"导入过程中发生错误：\n{err}\n\n程序窗口保留，请检查数据后重试。",
        )
        self._request_thread_quit()

    @Slot()
    def _on_import_cancel(self) -> None:
        """用户取消导入槽（主线程执行）。"""
        self._import_cancelled = True
        self._request_thread_quit()

    def _request_thread_quit(self) -> None:
        """请求后台线程退出（非阻塞，线程结束后由 finished 信号触发清理）。"""
        try:
            if hasattr(self, '_scale_thread') and self._scale_thread is not None:
                if self._scale_thread.isRunning():
                    self._scale_thread.quit()
        except Exception as exc:
            logger.warning("请求线程退出时出错：%s", exc)

    def _on_import_thread_finished(self) -> None:
        """线程安全退出后的清理（由 QThread.finished 信号触发）。

        注意：此时工作线程已停止事件循环，deleteLater() 无法投递到已停止
        的线程。直接清除引用让 Python GC 回收即可。
        """
        logger.debug("导入线程已安全退出，开始清理资源")
        try:
            if hasattr(self, '_scale_worker') and self._scale_worker is not None:
                try:
                    self._scale_worker.progress.disconnect()
                    self._scale_worker.succeeded.disconnect()
                    self._scale_worker.failed.disconnect()
                except Exception:
                    pass
                self._scale_worker = None
        except Exception as exc:
            logger.warning("清理 worker 引用时出错：%s", exc)

        try:
            if hasattr(self, '_scale_thread') and self._scale_thread is not None:
                try:
                    self._scale_thread.deleteLater()
                except Exception:
                    pass
                self._scale_thread = None
        except Exception as exc:
            logger.warning("清理 thread 时出错：%s", exc)

        # 清理进度对话框引用
        try:
            if hasattr(self, '_import_progress'):
                self._import_progress = None
        except Exception:
            pass

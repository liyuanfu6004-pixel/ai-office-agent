"""项目管理页面模块。

v0.6.0 架构调整后的页面设计：

1. **ProjectAllPage（全部项目页）—— 唯一总入口**
   - 全系统**唯一**含「导入总体项目表」「新增项目」「刷新」「搜索」的页面
   - 展示全部项目；project_type 列支持下拉修改归属类别
   - 修改类别后自动刷新（项目即时从本视图与对应分类视图中联动）
   - 「区县数量 / 点位数量 / 完成率」三列由系统统计，导入总体表阶段显示 0
   - 与导航「项目管理 / 全部项目」绑定，是默认页

2. **ProjectCategoryPage（分类展示页，7 个）**
   - 社区 / 集客 / 接入段 / 设备 / 管道 / 城域网 / 机房配套
   - **纯展示**：仅刷新 + 搜索；无导入、无新增、无编辑
   - 仅显示本类别的项目

业务逻辑全部模块化：Excel 读取见 data_import.excel_reader，导入后台线程见
data_import.import_worker，数据库访问见 core.projects_repository，类别分流见
core.project_categories，字段映射见 ui.widgets.field_mapping_dialog。
本文件只做编排与 UI。
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ....config import AppConfig
from ....core import project_categories, projects_repository
from ....core.database import Database
from ....data_import.import_worker import ImportWorker
from ....utils.logger import setup_logger
from ..field_mapping_dialog import FieldMappingDialog
from .base_page import BasePage

# 全部项目页表格列定义：（列标题, 是否数值列）——v1.2.3 删除区县数量
_COLUMNS: list[tuple[str, bool]] = [
    ("项目名称", False),
    ("项目编码", False),
    ("项目类型", False),
    ("年份", True),
    ("点位数量", True),
    ("完成率", True),
    ("状态", False),
    ("最后更新时间", False),
]

# 各列默认宽度（像素）
_COLUMN_WIDTHS: list[int] = [240, 140, 90, 70, 90, 90, 90, 160]

# 列号常量
_COL_PROJECT_TYPE = 2
_COL_YEAR = 3
_COL_SITE = 4
_COL_RATE = 5

# 未统计/未提供的占位显示
_PLACEHOLDER = "--"

logger = setup_logger()

_PROGRESS_MIN = 0
_PROGRESS_MAX = 100
_EXCEL_FILTER = "Excel 文件 (*.xlsx)"

# 项目详情数据结构（仅预留，不实现）。
# 双击项目进入详情后，固定为：项目 → 区县(多个) → 点位(多个) →
# CAD / PDF / 预算 / 照片 / 审批单 / 方案表。
# 这里用常量声明，供后续版本据此建表，本版不开发。
DETAIL_TREE: dict = {
    "项目": {
        "项目整体资料": None,           # 项目级资料
        "区县": {                       # 区县可多个
            "点位": {                   # 点位可多个
                "CAD": None,
                "PDF": None,
                "预算": None,
                "照片": None,
                "审批单": None,
                "方案表": None,
            }
        }
    }
}


def _fetch_project_stats(conn) -> dict[int, tuple[int, int]]:
    """v1.2.3：从缓存 ScanResultSummary 读取统计（统一数据源）。

    优先使用扫描结果缓存的 total_points 和 completion_rate。
    若某项目尚未扫描，回退从 point_dictionary 读取点位数，完成率 = 0。

    Returns:
        {project_id: (site_count, completion_rate)}.
    """
    from ....core.scan_result import get_cached_summary

    result: dict[int, tuple[int, int]] = {}

    # 1. 优先从缓存读取
    cur = conn.execute("SELECT id FROM projects")
    all_ids = [row["id"] for row in cur.fetchall()]
    uncached_ids: list[int] = []

    for pid in all_ids:
        s = get_cached_summary(pid)
        if s is not None:
            result[pid] = (s.total_points, s.completion_rate)
        else:
            uncached_ids.append(pid)

    # 2. 未缓存的项目：从 point_dictionary 取点位数，完成率 = 0
    if uncached_ids:
        placeholders = ",".join("?" for _ in uncached_ids)
        cur2 = conn.execute(
            f"SELECT project_id, COUNT(*) AS n FROM point_dictionary "
            f"WHERE project_id IN ({placeholders}) GROUP BY project_id",
            uncached_ids,
        )
        for row in cur2.fetchall():
            pid = row["project_id"]
            if pid not in result:
                result[pid] = (row["n"], 0)
        # 完全没有点位的项目
        for pid in uncached_ids:
            if pid not in result:
                result[pid] = (0, 0)

    return result


class NumericItem(QTableWidgetItem):
    """数值型表格单元。

    覆盖 __lt__ 使排序按数值比较。数值存实例属性 `_sortable_value`，
    不依赖 EditRole/DisplayRole（setText 会污染角色文本）。
    不调用 super().__lt__()，防 PySide6 递归 → 段错误。
    """

    def set_numeric_value(self, value) -> None:
        self._sortable_value = value

    def __lt__(self, other: object) -> bool:
        if isinstance(other, NumericItem) and hasattr(self, "_sortable_value"):
            try:
                return float(self._sortable_value) < float(other._sortable_value)
            except (TypeError, ValueError):
                pass
        try:
            return self.text() < other.text()
        except Exception:
            return False


# ====================================================================
# 全部项目页（全局唯一总入口）
# ====================================================================


class ProjectAllPage(BasePage):
    """全部项目页：全局唯一导入口与新增入口，展示全部项目。

    Args:
        config: 应用配置。
        parent: 父控件。
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="全部项目", subtitle="总体项目表导入与项目总览", parent=parent
        )
        self._config = config or AppConfig()

        self._import_thread: QThread | None = None
        self._import_worker: ImportWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._pending_data_rows: list[dict] = []
        self._pending_path: str | None = None
        # 受控刷新标志：编辑回写触发的渲染期间屏蔽 itemChanged
        self._suppress_change = False
        # 进入项目详情的回调，由内容区域注入（参数：项目 id）
        self._open_detail_handler = None

        self._setup_toolbar()
        self._setup_table()
        self._connect_signals()

        self.refresh_data()

    # ------------------------------------------------------------------ 工具栏

    def _setup_toolbar(self) -> None:
        """构建顶部工具栏：导入总体项目表 + 新增项目 + 刷新 + 搜索框。"""
        toolbar = QWidget(self)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.import_btn = QPushButton("导入总体项目表", toolbar)
        self.add_btn = QPushButton("新增项目", toolbar)
        self.add_btn.setDefault(True)
        self.refresh_btn = QPushButton("刷新", toolbar)

        self.search_edit = QLineEdit(toolbar)
        self.search_edit.setPlaceholderText("搜索项目名称 / 编码 ...")
        self.search_edit.setClearButtonEnabled(True)

        layout.addWidget(self.import_btn)
        layout.addWidget(self.add_btn)
        layout.addWidget(self.refresh_btn)
        layout.addStretch()
        layout.addWidget(self.search_edit, 1)

        self.content_layout.addWidget(toolbar)

    # ------------------------------------------------------------------ 表格

    def _setup_table(self) -> None:
        """构建项目总览表格。

        project_type 列用 QComboBox 下拉选择（委托实现）；其余列只读。
        双击项目行预留进入详情（本版仅打印日志）。
        """
        self.table = QTableWidget(self)
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setStretchLastSection(True)
        for col, width in enumerate(_COLUMN_WIDTHS):
            self.table.setColumnWidth(col, width)

        self.table.setRowCount(0)
        self.table.doubleClicked.connect(self._on_item_double_clicked)
        self.table.itemChanged.connect(self._on_item_changed)

        self.content_layout.addWidget(self.table)

    # ------------------------------------------------------------------ 信号

    def _connect_signals(self) -> None:
        self.import_btn.clicked.connect(self._on_import_clicked)
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.search_edit.textChanged.connect(self._on_search_changed)

    # ------------------------------------------------------------------ 数据加载

    def refresh_data(self) -> None:
        """从数据库读取全部项目并刷新表格（v1.2.3：动态计算点位数+完成率）。"""
        conn = Database.open_db_connection(self._config.database.path)
        try:
            projects_repository.init_projects_table(conn)
            projects_repository.init_point_dictionary_table(conn)
            rows = projects_repository.fetch_all_projects(conn)
            # v1.2.3: 动态统计每个项目的站点数和完成率
            stats = _fetch_project_stats(conn)
        finally:
            conn.close()
        self._render_rows(rows, stats)
        logger.info("刷新全部项目：%d 条", len(rows))

    def _render_rows(self, rows: list, stats: dict[int, tuple[int, int]] | None = None) -> None:
        """把数据库行渲染到表格（v1.2.3：使用动态统计）。"""
        if stats is None:
            stats = {}
        self._suppress_change = True
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            self._fill_row_from_db(row_idx, r, stats.get(int(r["id"]), (0, 0)))
        self.table.setSortingEnabled(True)
        self._suppress_change = False

    def _fill_row_from_db(self, row: int, r, stats: tuple[int, int] = (0, 0)) -> None:
        """根据一行数据库记录填充表格行（v1.2.3：去区县列，动态点位+完成率）。

        project_type 列：用下拉框（"未分类"+7 类），可编辑归属；
        其余列只读。用 UserRole 存项目 id 供回写。
        """
        name = r["project_name"] or ""
        code = r["project_code"] or ""
        year = r["year"]
        ptype = r["project_type"]  # 可能为 None
        status = r["status"] or ""
        updated = (r["updated_at"] or "").replace("T", " ")

        site_count, rate = stats

        self._set_text_cell(row, 0, name)
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, int(r["id"]))
        self._set_text_cell(row, 1, code)
        self._set_text_cell(row, 6, status)
        self._set_text_cell(row, 7, updated)

        combo = QComboBox()
        combo.addItem("未分类", None)
        for cat in project_categories.CATEGORIES:
            combo.addItem(cat, cat)
        if ptype in project_categories.CATEGORIES:
            combo.setCurrentIndex(project_categories.CATEGORIES.index(ptype) + 1)
        else:
            combo.setCurrentIndex(0)
        combo.setProperty("project_id", int(r["id"]))
        combo.currentIndexChanged.connect(self._on_type_combo_changed)
        self.table.setCellWidget(row, _COL_PROJECT_TYPE, combo)

        # 数值列
        self._set_numeric_cell(row, _COL_YEAR, year if year is not None else 0,
                               str(year) if year is not None else _PLACEHOLDER)
        self._set_numeric_cell(row, _COL_SITE, site_count, str(site_count))
        self._set_numeric_cell(row, _COL_RATE, rate, f"{rate}%")

    def _set_text_cell(self, row: int, col: int, text: str) -> None:
        """设置只读文本单元。"""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _set_numeric_cell(self, row: int, col: int, value, display: str) -> None:
        """设置数值列单元（保留传入显示文本）。"""
        item = NumericItem()
        item.set_numeric_value(value)
        item.setText(display)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _set_stat_cell(self, row: int, col: int, value) -> None:
        """统计列显示：0 显示 '--'，否则显示数值（完成率附 %）。

        导入总体项目表阶段这些字段为 0，统一显示 '--'；
        导入规模表后由系统统计填入实际值并显示。
        """
        v = value if isinstance(value, int) else (int(value) if value else 0)
        if col == _COL_RATE:
            display = f"{v}%" if v > 0 else _PLACEHOLDER
        else:
            display = str(v) if v > 0 else _PLACEHOLDER
        self._set_numeric_cell(row, col, v, display)

    # ------------------------------------------------------------------ 类型下拉回写

    def _on_type_combo_changed(self, _index: int) -> None:
        """project_type 下拉变化：回写数据库并联动刷新。

        修改后项目归属变更：全部项目视图仍可见（行还在），但下拉值已变；
        各分类页下一次 refresh 即按新类别读取。
        """
        if self._suppress_change:
            return
        combo = self.table.focusWidget() if isinstance(self.table.focusWidget(), QComboBox) else None
        # 通过 sender 取可靠些
        combo = self.sender()
        if not isinstance(combo, QComboBox):
            return
        project_id = combo.property("project_id")
        if project_id is None:
            return
        new_type = combo.currentData()  # None 或类别名

        conn = Database.open_db_connection(self._config.database.path)
        try:
            projects_repository.update_project_type(conn, int(project_id), new_type)
        finally:
            conn.close()

        label = new_type if new_type else "未分类"
        logger.info("项目 id=%s 改为[%s]", project_id, label)
        # 联动刷新分类页
        self._refresh_category_pages()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """表格项文本变化兜底（project_type 用下拉，不走文本编辑）。"""
        # 当前仅 project_type 可改，且经下拉处理；此回调留作扩展
        return

    # ------------------------------------------------------------------ 导入流程

    def _on_import_clicked(self) -> None:
        """「导入总体项目表」：选 Excel → 后台读取 → 映射对话框 → 后台写库。"""
        if self._import_thread is not None:
            QMessageBox.information(self, "提示", "当前已有导入任务在进行中，请稍候。")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "选择总体项目表", "", _EXCEL_FILTER,
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            QMessageBox.warning(self, "文件类型错误", "仅支持 .xlsx 格式的 Excel 文件。")
            return

        self._start_load_phase(path)

    def _start_load_phase(self, path: str) -> None:
        """启动后台线程读取 Excel。"""
        self._progress_dialog = QProgressDialog(
            "正在读取 Excel，请稍候 ...", "取消", _PROGRESS_MIN, _PROGRESS_MAX, self
        )
        self._progress_dialog.setWindowTitle("导入总体项目表")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setAutoReset(False)
        self._progress_dialog.setValue(_PROGRESS_MIN)
        self._progress_dialog.canceled.connect(self._on_progress_canceled)

        self._import_thread = QThread(self)
        self._import_worker = ImportWorker(path=path, config=self._config)
        self._import_worker.moveToThread(self._import_thread)

        self._import_worker.progress.connect(
            self._on_import_progress, Qt.ConnectionType.QueuedConnection
        )
        self._import_worker.loaded.connect(
            self._on_loaded, Qt.ConnectionType.QueuedConnection
        )
        self._import_worker.failed.connect(
            self._on_import_failed, Qt.ConnectionType.QueuedConnection
        )
        self._import_thread.started.connect(self._import_worker.start_load)
        self._import_thread.start()

    def _on_loaded(self, headers, data_rows) -> None:
        """读取完成：关对话框，弹映射对话框。"""
        if self._import_worker is not None:
            self._pending_path = self._import_worker._path
        self._pending_data_rows = data_rows

        self._close_progress_quietly()
        self._teardown_thread()

        dialog = FieldMappingDialog(
            headers=list(headers), data_rows=data_rows, parent=self,
        )
        if FieldMappingDialog.auto_accept_for_test:
            mapping = dialog.get_mapping()
            self._start_import_phase(self._pending_path, mapping)
            return

        if dialog.exec() != FieldMappingDialog.DialogCode.Accepted:
            logger.info("用户取消字段映射，导入流程终止")
            self._pending_path = None
            return

        mapping = dialog.get_mapping()
        self._start_import_phase(self._pending_path, mapping)

    def _start_import_phase(
        self, path: str | None, mapping: dict[str, str | None]
    ) -> None:
        """启动后台线程执行写库。"""
        if not path:
            QMessageBox.warning(self, "导入失败", "读取阶段的数据已丢失，请重新选择文件。")
            return

        self._import_thread = QThread(self)
        self._import_worker = ImportWorker(path=path, config=self._config)
        self._import_worker.moveToThread(self._import_thread)
        self._import_worker.set_mapping(mapping)

        self._progress_dialog = QProgressDialog(
            "正在导入，请稍候 ...", "取消", _PROGRESS_MIN, _PROGRESS_MAX, self
        )
        self._progress_dialog.setWindowTitle("导入总体项目表")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setAutoReset(False)
        self._progress_dialog.setValue(_PROGRESS_MIN)
        self._progress_dialog.canceled.connect(self._on_progress_canceled)

        self._import_worker.progress.connect(
            self._on_import_progress, Qt.ConnectionType.QueuedConnection
        )
        self._import_worker.succeeded.connect(
            self._on_import_succeeded, Qt.ConnectionType.QueuedConnection
        )
        self._import_worker.failed.connect(
            self._on_import_failed, Qt.ConnectionType.QueuedConnection
        )
        self._import_thread.started.connect(self._import_worker.start_run_import)
        self._import_thread.start()

    def _on_import_progress(self, value: int, message: str) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.setLabelText(message)
            self._progress_dialog.setValue(value)

    def _on_import_succeeded(self, inserted: int, skipped: int) -> None:
        """导入成功：刷新全部项目 + 各分类页。"""
        self._close_progress_quietly()
        self._teardown_thread()
        self.refresh_data()
        self._refresh_category_pages()
        msg = f"已导入 {inserted} 条项目到「全部项目」。"
        if skipped > 0:
            msg += f"\n另有 {skipped} 行因缺少项目名称被跳过。"
        QMessageBox.information(self, "导入成功", msg)
        logger.info("导入完成：%d 条，跳过 %d 行", inserted, skipped)

    def _on_import_failed(self, message: str) -> None:
        self._close_progress_quietly()
        self._teardown_thread()
        QMessageBox.critical(self, "导入失败", message)
        logger.error("导入失败：%s", message)

    def _close_progress_quietly(self) -> None:
        """关闭进度对话框并断开 canceled，避免 close 误触发取消。"""
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.canceled.disconnect(self._on_progress_canceled)
            except (RuntimeError, TypeError):
                pass
            self._progress_dialog.close()
            self._progress_dialog = None

    def _on_progress_canceled(self) -> None:
        if self._import_thread is not None:
            self._import_thread.quit()
            self._import_thread.wait(3000)
        self._teardown_thread()

    def _teardown_thread(self) -> None:
        """清理线程与 Worker 引用。"""
        if self._import_thread is not None:
            self._import_thread.quit()
            self._import_thread.wait(3000)
            self._import_thread.deleteLater()
            self._import_thread = None
        self._import_worker = None

    def _refresh_category_pages(self) -> None:
        """导入/改类型后通知各分类页刷新（若有引用注入）。"""
        pages = getattr(self, "_category_pages", None) or []
        for p in pages:
            try:
                p.refresh_data()
            except Exception:  # noqa: BLE001
                logger.exception("刷新分类页失败")

    def set_category_pages(self, pages: list) -> None:
        """由内容区域注入 7 个分类页引用，供联动刷新。"""
        self._category_pages = list(pages)

    def set_open_detail_handler(self, handler) -> None:
        """注入「打开项目详情」回调（参数：项目 id）。

        由内容区域注入；双击项目行时回调以打开详情页。
        """
        self._open_detail_handler = handler

    # ------------------------------------------------------------------ 搜索 / 新增

    def _on_search_changed(self, text: str) -> None:
        """搜索框：按项目名称/编码过滤行。"""
        keyword = text.strip().lower()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            code_item = self.table.item(row, 1)
            name = name_item.text().lower() if name_item else ""
            code = code_item.text().lower() if code_item else ""
            visible = (not keyword) or (keyword in name) or (keyword in code)
            self.table.setRowHidden(row, not visible)

    def _on_add_clicked(self) -> None:
        """「新增项目」：本版未实现，仅提示。"""
        QMessageBox.information(self, "暂未实现", "「新增项目」功能将在后续版本实现。")

    def _on_item_double_clicked(self, index) -> None:
        """双击项目：打开项目详情页（基础结构，只读）。

        通过注入的回调通知内容区域载入并切换到详情页；
        项目 id 取自第 0 列 UserRole。无回调或无 id 时仅记日志。
        """
        row = index.row()
        name_item = self.table.item(row, 0)
        name = name_item.text() if name_item else ""
        project_id = name_item.data(Qt.ItemDataRole.UserRole) if name_item else None
        logger.info("双击项目（进入详情）：%s id=%s", name, project_id)
        if project_id is None or self._open_detail_handler is None:
            return
        self._open_detail_handler(int(project_id))


# ====================================================================
# 分类展示页（7 个业务类别的父类，纯展示）
# ====================================================================


class ProjectCategoryPage(BasePage):
    """分类展示页：仅展示某业务类别的项目，纯只读。

    无导入、无新增、无编辑——导入口与编辑能力全局唯一，归「全部项目」页。

    Args:
        category: 业务类别名（7 类之一）。
        config: 应用配置。
        parent: 父控件。
    """

    def __init__(
        self,
        category: str,
        config: AppConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title=category, subtitle="项目管理 · 分类展示", parent=parent
        )
        self._category = category
        self._config = config or AppConfig()
        # 进入项目详情的回调，由内容区域注入（参数：项目 id）
        self._open_detail_handler = None

        self._setup_toolbar()
        self._setup_table()
        self._connect_signals()

        self.refresh_data()

    # ------------------------------------------------------------------ 工具栏

    def _setup_toolbar(self) -> None:
        """构建顶部工具栏：仅刷新 + 搜索框（无导入/新增）。"""
        toolbar = QWidget(self)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.refresh_btn = QPushButton("刷新", toolbar)

        self.search_edit = QLineEdit(toolbar)
        self.search_edit.setPlaceholderText("搜索项目名称 / 编码 ...")
        self.search_edit.setClearButtonEnabled(True)

        layout.addWidget(self.refresh_btn)
        layout.addStretch()
        layout.addWidget(self.search_edit, 1)

        self.content_layout.addWidget(toolbar)

    # ------------------------------------------------------------------ 表格

    def _setup_table(self) -> None:
        """构建只读列表表格。"""
        self.table = QTableWidget(self)
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setStretchLastSection(True)
        for col, width in enumerate(_COLUMN_WIDTHS):
            self.table.setColumnWidth(col, width)

        self.table.setRowCount(0)
        self.table.doubleClicked.connect(self._on_item_double_clicked)

        self.content_layout.addWidget(self.table)

    # ------------------------------------------------------------------ 信号

    def _connect_signals(self) -> None:
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.search_edit.textChanged.connect(self._on_search_changed)

    # ------------------------------------------------------------------ 数据加载

    def refresh_data(self) -> None:
        """从数据库读取本类别项目并刷新表格（v1.2.3：动态统计）。"""
        conn = Database.open_db_connection(self._config.database.path)
        try:
            projects_repository.init_projects_table(conn)
            projects_repository.init_point_dictionary_table(conn)
            rows = projects_repository.fetch_projects_by_type(conn, self._category)
            stats = _fetch_project_stats(conn)
        finally:
            conn.close()
        self._render_rows(rows, stats)
        logger.info("刷新列表：%s 类 %d 条", self._category, len(rows))

    def _render_rows(self, rows: list, stats: dict[int, tuple[int, int]] | None = None) -> None:
        if stats is None:
            stats = {}
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            self._fill_row_from_db(row_idx, r, stats.get(int(r["id"]), (0, 0)))
        self.table.setSortingEnabled(True)

    def _fill_row_from_db(self, row: int, r, stats: tuple[int, int] = (0, 0)) -> None:
        """填充只读行（v1.2.3：去区县列，动态点位+完成率）。
        stats = (total_points, completion_rate) 来自 ScanResultSummary 缓存。
        """
        name = r["project_name"] or ""
        code = r["project_code"] or ""
        year = r["year"]
        ptype = r["project_type"] or self._category
        status = r["status"] or ""
        updated = (r["updated_at"] or "").replace("T", " ")

        site_count, rate = stats

        self._set_text_cell(row, 0, name)
        self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, int(r["id"]))
        self._set_text_cell(row, 1, code)
        self._set_text_cell(row, 2, ptype)
        self._set_text_cell(row, 6, status)
        self._set_text_cell(row, 7, updated)

        self._set_numeric_cell(row, _COL_YEAR, year if year is not None else 0,
                               str(year) if year is not None else _PLACEHOLDER)
        self._set_numeric_cell(row, _COL_SITE, site_count, str(site_count))
        self._set_numeric_cell(row, _COL_RATE, rate, f"{rate}%")

    def _set_text_cell(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _set_numeric_cell(self, row: int, col: int, value, display: str) -> None:
        item = NumericItem()
        item.set_numeric_value(value)
        item.setText(display)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _set_stat_cell(self, row: int, col: int, value) -> None:
        """统计列显示：0 → '--'，否则数值（完成率附 %）。"""
        v = value if isinstance(value, int) else (int(value) if value else 0)
        if col == _COL_RATE:
            display = f"{v}%" if v > 0 else _PLACEHOLDER
        else:
            display = str(v) if v > 0 else _PLACEHOLDER
        self._set_numeric_cell(row, col, v, display)

    # ------------------------------------------------------------------ 搜索

    def _on_search_changed(self, text: str) -> None:
        keyword = text.strip().lower()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            code_item = self.table.item(row, 1)
            name = name_item.text().lower() if name_item else ""
            code = code_item.text().lower() if code_item else ""
            visible = (not keyword) or (keyword in name) or (keyword in code)
            self.table.setRowHidden(row, not visible)

    def set_open_detail_handler(self, handler) -> None:
        """注入「打开项目详情」回调（参数：项目 id）。

        由内容区域注入；双击项目行时回调以打开详情页（与全部项目页一致）。
        """
        self._open_detail_handler = handler

    def _on_item_double_clicked(self, index) -> None:
        """双击项目：打开项目详情页（与全部项目页共用同一详情页）。

        通过注入的回调通知内容区域载入并切换到详情页；
        项目 id 取自第 0 列 UserRole。无回调或无 id 时仅记日志。
        """
        row = index.row()
        name_item = self.table.item(row, 0)
        name = name_item.text() if name_item else ""
        project_id = name_item.data(Qt.ItemDataRole.UserRole) if name_item else None
        logger.info("双击项目（进入详情）：%s id=%s（类别 %s）", name, project_id, self._category)
        if project_id is None or self._open_detail_handler is None:
            return
        self._open_detail_handler(int(project_id))

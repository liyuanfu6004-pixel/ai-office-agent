"""GUI 启动冒烟测试。

校验 v1.2.1 架构：
- 默认显示「全部项目」页（all_projects）
- 全部项目页含「导入总体项目表」「新增项目」按钮
- 7 个分类页**不含**导入/新增按钮，但已注入详情回调（双击进详情）
- 导航含「全部项目」节点；默认页 all_projects
- 扫描结果中心页已注册（page key=scan_center）
- 项目详情页已注册（page key=project_detail）：
  无树结构、含返回按钮 +「导入项目明细表」按钮、概览字段、整体资料面板、
  筛选栏、点位列表(5 固定列)、_load_points_from_db 方法（v1.0.0 从 point_dictionary 表加载）
- v1.1.0 架构：新增 ScaleTableWizard + scale_table_engine +
  project_profile_repository + scale_import_worker
- v1.2.0 架构：新增 ScanCenterPage + core/scan_result.py 统一扫描结果模型
- 全部项目页 + 7 分类页均注入打开详情回调
- 总页面数 = 12（全部项目 + 7 分类 + 详情 + 扫描中心 + AI + 设置）
1.2 秒后自动退出。
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ai_office_agent.config import load_config  # noqa: E402
from ai_office_agent.ui.main_window import MainWindow  # noqa: E402
from ai_office_agent.ui.theme import STYLE_SHEET  # noqa: E402
from ai_office_agent.utils.logger import setup_logger  # noqa: E402


def main() -> int:
    logger = setup_logger()
    logger.info("[smoke-gui] 开始")
    try:
        config = load_config()
        from ai_office_agent.core.database import Database
        database = Database(config.database.path)
        database.connect()

        app = QApplication(sys.argv)
        app.setStyleSheet(STYLE_SHEET)
        window = MainWindow(config=config)
        window.show()

        ca = window.content_area
        assert ca.page_stack.count() == 12, f"页面数不对: {ca.page_stack.count()}"
        assert ca.DEFAULT_PAGE == "all_projects"
        assert window.nav_tree.DEFAULT_PAGE == "all_projects"

        all_page = ca.page_stack.widget(ca._page_index["all_projects"])
        assert hasattr(all_page, "import_btn"), "全部项目页应有导入按钮"
        assert hasattr(all_page, "add_btn"), "全部项目页应有新增按钮"
        # 全部项目页已注入打开详情回调
        assert all_page._open_detail_handler is not None, "全部项目页应注入详情回调"

        # 7 分类页无导入/新增，但已注入详情回调（双击进详情）
        for key in ("community", "enterprise", "access", "equipment",
                    "pipeline", "metro", "facility"):
            page = ca.page_stack.widget(ca._page_index[key])
            assert not hasattr(page, "import_btn"), f"{key} 不应有导入按钮"
            assert not hasattr(page, "add_btn"), f"{key} 不应有新增按钮"
            assert hasattr(page, "refresh_btn"), f"{key} 应有刷新按钮"
            assert page._open_detail_handler is not None, f"{key} 应注入详情回调"

        # 项目详情页已注册：v1.1.0 重构后使用 ScaleTableWizard 智能识别引擎
        detail = ca.page_stack.widget(ca._page_index["project_detail"])
        assert hasattr(detail, "back_btn"), "详情页应有返回按钮"
        assert hasattr(detail, "import_detail_btn"), "详情页应有导入项目明细表按钮"
        assert not hasattr(detail, "tree"), "详情页不应再有树结构"
        assert hasattr(detail, "name_edit"), "详情页应有概览字段"
        assert hasattr(detail, "documents_panel"), "详情页应有项目整体资料面板"
        assert hasattr(detail, "filter_bar"), "详情页应有筛选栏"
        assert hasattr(detail, "point_table"), "详情页应有点位列表表格"
        # v1.0.0：详情页应有 _load_points_from_db 方法（从 point_dictionary 表加载）
        assert hasattr(detail, "_load_points_from_db"), "详情页应有 _load_points_from_db"
        # v1.2.1 BugFix：详情页应有安全线程清理方法（非阻塞 quit + finished 回调）
        assert hasattr(detail, "_request_thread_quit"), "v1.2.1 详情页应有 _request_thread_quit"
        assert hasattr(detail, "_on_import_thread_finished"), "v1.2.1 详情页应有 _on_import_thread_finished"
        # v1.1.0：详情页应有 _extract_dynamic_columns 静态方法
        assert hasattr(detail, "_extract_dynamic_columns"), "详情页应有 _extract_dynamic_columns"
        # 点位列表固定 5 列
        pt = detail.point_table
        assert pt.columnCount() == 5, f"点位表固定列应为 5，实际 {pt.columnCount()}"
        headers = [pt.horizontalHeaderItem(i).text() for i in range(5)]
        assert headers == ["序号", "区县", "点位名称", "图纸状态", "预算状态"], headers
        # 筛选栏含区县/图纸/预算下拉 + 名称搜索
        assert hasattr(detail.filter_bar, "county_combo")
        assert hasattr(detail.filter_bar, "name_edit")
        assert hasattr(detail.filter_bar, "drawing_combo")
        assert hasattr(detail.filter_bar, "budget_combo")
        assert hasattr(detail, "load_project"), "详情页应有 load_project 方法"

        # v1.1.0：验证新模块可导入
        import ai_office_agent.core.scale_table_engine as ste
        assert hasattr(ste, "detect_best_sheet"), "scale_table_engine 应有 detect_best_sheet"
        assert hasattr(ste, "build_preview_rows"), "scale_table_engine 应有 build_preview_rows"
        assert hasattr(ste, "build_field_candidates"), "scale_table_engine 应有 build_field_candidates"
        assert hasattr(ste, "generate_point_name"), "scale_table_engine 应有 generate_point_name"
        assert hasattr(ste, "classify_dynamic_fields"), "scale_table_engine 应有 classify_dynamic_fields"
        assert hasattr(ste, "read_all_sheets"), "scale_table_engine 应有 read_all_sheets"
        # v1.2.1：新增 Sheet 名称评分 + 多行表头
        assert hasattr(ste, "_score_sheet_name"), "v1.2.1 应有 Sheet 名称评分"
        assert hasattr(ste, "_score_table_structure"), "v1.2.1 应有表格结构评分"
        assert hasattr(ste, "_detect_header_region"), "v1.2.1 应有表头区域识别"
        assert hasattr(ste, "_build_composite_headers"), "v1.2.1 应有复合表头构建"
        assert hasattr(ste, "get_default_dynamic_fields"), "v1.2.1 应有默认动态字段（空）"

        import ai_office_agent.core.project_profile_repository as ppr
        assert hasattr(ppr, "upsert_profile"), "project_profile_repository 应有 upsert_profile"
        assert hasattr(ppr, "fetch_profile"), "project_profile_repository 应有 fetch_profile"

        from ai_office_agent.ui.widgets.scale_table_wizard import ScaleTableWizard
        assert ScaleTableWizard is not None, "ScaleTableWizard 应可导入"

        # v1.2.1：向导应有动态字段手动添加 UI
        assert hasattr(ScaleTableWizard, '_add_dynamic_field'), "v1.2.1 向导应有添加动态字段"
        assert hasattr(ScaleTableWizard, '_remove_dynamic_field'), "v1.2.1 向导应有删除动态字段"
        assert hasattr(ScaleTableWizard, '_read_dynamic_fields_from_ui'), "v1.2.1 向导应有读取动态字段"

        from ai_office_agent.data_import.scale_import_worker import ScaleImportWorker
        assert ScaleImportWorker is not None, "ScaleImportWorker 应可导入"

        # v1.2.2：验证扫描结果中心模块
        from ai_office_agent.core.scan_result import (
            ScanResultItem,
            ScanResultSummary,
            MatchStatus,
            build_scan_results,
        )
        assert MatchStatus.MATCHED.label == "已匹配", "MATCHED 标签应正确"
        assert MatchStatus.NOT_FOUND.label == "未找到", "NOT_FOUND 标签应正确"
        assert hasattr(ScanResultItem, "from_point_dict"), "ScanResultItem 应有 from_point_dict"
        assert hasattr(ScanResultSummary, "from_items"), "ScanResultSummary 应有 from_items"
        assert callable(build_scan_results), "build_scan_results 应可调用"
        # v1.2.2：ScanResultItem 应有确认字段
        assert hasattr(ScanResultItem, "confirmed"), "v1.2.2 ScanResultItem 应有 confirmed"
        assert hasattr(ScanResultItem, "match_method"), "v1.2.2 ScanResultItem 应有 match_method"
        assert hasattr(ScanResultSummary, "confirmed_count"), "v1.2.2 ScanResultSummary 应有 confirmed_count"

        # v1.2.2：验证 scan_match_history 模块
        from ai_office_agent.core import scan_match_history_repository as smhr
        assert hasattr(smhr, "init_scan_match_history_table"), "v1.2.2 应有建表"
        assert hasattr(smhr, "save_match_history"), "v1.2.2 应有 save"
        assert hasattr(smhr, "fetch_project_history"), "v1.2.2 应有 fetch history"

        # 验证扫描中心页面已注册
        scan_page = ca.page_stack.widget(ca._page_index["scan_center"])
        assert hasattr(scan_page, "scan_btn"), "扫描中心应有扫描按钮"
        assert hasattr(scan_page, "rescan_btn"), "扫描中心应有重新扫描按钮"
        assert hasattr(scan_page, "stat_cards"), "扫描中心应有统计卡片"
        assert hasattr(scan_page, "result_table"), "扫描中心应有结果列表"
        assert hasattr(scan_page, "preview_panel"), "扫描中心应有详情预览面板"
        assert hasattr(scan_page, "filter_bar"), "扫描中心应有筛选栏"
        assert hasattr(scan_page, "load_project"), "扫描中心应有 load_project 方法"
        # v1.2.2：新增按钮
        assert hasattr(scan_page, "confirm_all_btn"), "v1.2.2 应有全部确认按钮"
        assert hasattr(scan_page, "batch_confirm_btn"), "v1.2.2 应有批量确认按钮"
        assert hasattr(scan_page, "rematch_btn"), "v1.2.2 应有重新匹配按钮"
        assert hasattr(scan_page, "export_btn"), "v1.2.2 应有导出Excel按钮"
        assert hasattr(scan_page, "select_folder_btn"), "v1.3.1 应有选择项目文件夹按钮"
        # v1.2.2：结果表格应有 8 列（含确认）
        assert scan_page.result_table.columnCount() >= 8, "v1.2.2 结果表格应 >= 8 列"

        # 预留接口验证（仅定义，不实现）
        from ai_office_agent.ui.widgets.pages.scan_center_page import (
            RenamePreviewInterface,
            FolderBuilderInterface,
            HealthScoreInterface,
            AISuggestionInterface,
        )
        assert hasattr(RenamePreviewInterface, "preview_rename"), "应预留 RenamePreviewInterface"
        assert hasattr(FolderBuilderInterface, "build_folder_structure"), "应预留 FolderBuilderInterface"
        assert hasattr(HealthScoreInterface, "calculate_health"), "应预留 HealthScoreInterface"
        assert hasattr(AISuggestionInterface, "generate_suggestions"), "应预留 AISuggestionInterface"

        # 验证 point_dictionary 已升级到 v1.1.0（含 dynamic_data 列）
        from ai_office_agent.core import projects_repository
        conn = database.connection
        projects_repository.init_point_dictionary_table(conn)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(point_dictionary)")}
        assert "dynamic_data" in cols, "point_dictionary 表应含 dynamic_data 列"

        # 验证 project_profiles 表存在
        from ai_office_agent.core import project_profile_repository as ppr2
        ppr2.init_project_profiles_table(conn)
        profiles_cols = {row["name"] for row in conn.execute("PRAGMA table_info(project_profiles)")}
        assert "sheet_name" in profiles_cols, "project_profiles 应含 sheet_name 列"
        assert "dynamic_fields" in profiles_cols, "project_profiles 应含 dynamic_fields 列"
        assert "use_concatenation" in profiles_cols, "project_profiles 应含 use_concatenation 列"

        # 默认显示全部项目
        assert ca.page_stack.currentIndex() == ca._page_index["all_projects"]

        logger.info("[smoke-gui] 架构校验通过（v1.3 文件自动整理引擎）")

        QTimer.singleShot(800, app.quit)
        code = app.exec()
        database.close()
        logger.info("[smoke-gui] 结束 code=%s", code)
        print("GUI_SMOKE_OK")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

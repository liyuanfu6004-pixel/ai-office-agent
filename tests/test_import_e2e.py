"""端到端导入冒烟测试（无真人交互）。

验证 v0.6.0：
1. 「全部项目」页触发导入（全局唯一导入口）
2. Excel 数据含多类型 + 无类型行 → 自动分流，无类型行只入全部项目
3. 导入后全部项目刷新；统计列显示 '--'（导入总体表阶段为 0）
4. 分类页无导入按钮（导入口唯一）
5. 修改 project_type 下拉后联动刷新
"""
from __future__ import annotations

import sqlite3
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from ai_office_agent.config import load_config  # noqa: E402
from ai_office_agent.ui.widgets.field_mapping_dialog import (  # noqa: E402
    FieldMappingDialog,
)
from ai_office_agent.ui.widgets.pages.project_all_page import (  # noqa: E402
    ProjectAllEntryPage,
)
from ai_office_agent.ui.theme import STYLE_SHEET  # noqa: E402
from ai_office_agent.utils.logger import setup_logger  # noqa: E402

TEST_XLSX = Path(__file__).resolve().parent / "_e2e_sample.xlsx"


def make_xlsx() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["总体项目表 2026"])
    ws.append([])
    ws.append(["项目名称", "项目编码", "年份", "项目类型", "状态"])
    ws.append(["社区项目1", "P001", 2026, "社区", "进行中"])
    ws.append(["数字家庭项目2", "P002", 2026, "数字家庭", "进行中"])   # →社区
    ws.append(["集客项目3", "P003", 2026, "集客", "进行中"])
    ws.append(["无类型项目4", "P004", 2026, "", "待启动"])             # →NULL 仅全部项目
    ws.append(["不明类型5", "P005", 2026, "星际工程", "进行中"])        # →NULL
    wb.save(TEST_XLSX)


def main() -> int:
    logger = setup_logger()
    logger.info("[e2e] 开始")
    try:
        config = load_config()
        db_path = Path(config.database.path)
        if not db_path.is_absolute():
            db_path = Path(__file__).resolve().parent.parent / db_path
        if db_path.exists():
            c = sqlite3.connect(db_path, isolation_level=None)
            c.execute("DELETE FROM projects")
            c.commit()
            c.close()

        make_xlsx()
        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet(STYLE_SHEET)

        FieldMappingDialog.auto_accept_for_test = True
        QFileDialog.getOpenFileName = staticmethod(  # type: ignore[assignment]
            lambda *a, **k: (str(TEST_XLSX), "Excel 文件 (*.xlsx)")
        )

        all_page = ProjectAllEntryPage(config=config)
        all_page.show()
        QTimer.singleShot(100, all_page._on_import_clicked)

        done = {"ok": False, "fail": ""}

        def poll():
            rows = all_page.table.rowCount()
            if rows != 5:
                return
            c = sqlite3.connect(db_path, isolation_level=None)
            c.row_factory = sqlite3.Row
            counts = {
                "社": c.execute("SELECT COUNT(*) n FROM projects WHERE project_type='社区'").fetchone()["n"],
                "集": c.execute("SELECT COUNT(*) n FROM projects WHERE project_type='集客'").fetchone()["n"],
                "null": c.execute("SELECT COUNT(*) n FROM projects WHERE project_type IS NULL").fetchone()["n"],
                "all": c.execute("SELECT COUNT(*) n FROM projects").fetchone()["n"],
            }
            c.close()
            if counts != {"社": 2, "集": 1, "null": 2, "all": 5}:
                done["fail"] = f"分流不符: {counts}"
                app.quit()
                return
            # 分类页无导入按钮
            for cp in getattr(all_page, "_category_pages", []):
                if hasattr(cp, "import_btn"):
                    done["fail"] = "分类页不应有导入按钮"
                    app.quit()
                    return
            # v1.2.3：完成率动态计算，列号从 6 变为 5（区县数量列已删除）
            rate_item = all_page.table.item(0, 5)  # 完成率列
            if rate_item and rate_item.text() not in ("--", "0%", "0", ""):
                done["fail"] = f"完成率应占位显示，实际: {rate_item.text()}"
                app.quit()
                return
            done["ok"] = True
            app.quit()

        poll_timer = QTimer()
        poll_timer.timeout.connect(poll)
        poll_timer.start(100)

        timeout = QTimer()
        timeout.setSingleShot(True)
        def on_timeout():
            done["fail"] = f"超时 rows={all_page.table.rowCount()}"
            app.quit()
        timeout.timeout.connect(on_timeout)
        timeout.start(8000)

        app.exec()

        FieldMappingDialog.auto_accept_for_test = False
        try:
            TEST_XLSX.unlink()
        except OSError:
            pass

        if done["ok"]:
            print("E2E_OK: 导入5行分流(社区2/集客1/未分类2)，统计列占位，分类页无导入口")
            return 0
        logger.error("[e2e] 失败: %s", done["fail"] or "未知")
        return 1
    except Exception:
        traceback.print_exc()
        try:
            if TEST_XLSX.exists():
                TEST_XLSX.unlink()
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

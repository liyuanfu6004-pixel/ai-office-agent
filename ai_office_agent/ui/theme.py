"""界面主题与样式表模块。

定义全局 QSS（Qt Style Sheet），使界面接近 Windows 11 现代化风格：
浅灰底、圆角白卡片、柔和选中高亮、Segoe UI 字体。
"""
from __future__ import annotations

# 全局样式表
STYLE_SHEET = """
/* ---------- 全局字体 ---------- */
* {
    font-family: "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background: #F3F3F3;
}

QStatusBar {
    background: #F3F3F3;
    color: #8A8A8A;
    border-top: 1px solid #E6E6E6;
}

/* 分割条透明，保持左右紧贴 */
QSplitter::handle:horizontal {
    background: transparent;
    width: 1px;
}

/* ---------- 左侧导航树 ---------- */
QTreeWidget#NavTree {
    background: transparent;
    border: none;
    outline: none;            /* 去掉焦点虚线框 */
    padding: 8px 6px;
}
QTreeWidget#NavTree::item {
    height: 36px;
    padding-left: 10px;
    margin: 2px 4px;
    border-radius: 6px;
}
QTreeWidget#NavTree::item:hover {
    background: #ECECEC;
}
QTreeWidget#NavTree::item:selected {
    background: #E5F1FB;
    color: #1B1B1B;
}
/* 去掉缩进处的装饰背景，保持扁平 */
QTreeWidget#NavTree::branch {
    background: transparent;
}

/* ---------- 右侧内容容器与卡片 ---------- */
QFrame#ContentWrapper {
    background: #F3F3F3;
}
QFrame#ContentArea {
    background: #FFFFFF;
    border: 1px solid #EAEAEA;
    border-radius: 8px;
}
QStackedWidget {
    background: transparent;
    border: none;
}

/* ---------- 页面标题 ---------- */
QLabel#PageTitle {
    font-size: 24px;
    font-weight: 600;
    color: #1B1B1B;
    background: transparent;
}
QLabel#PageSubtitle {
    font-size: 13px;
    color: #8A8A8A;
    background: transparent;
}

/* ---------- 工具栏按钮 ---------- */
QPushButton {
    background: #FFFFFF;
    border: 1px solid #D0D0D0;
    border-radius: 6px;
    padding: 7px 16px;
    color: #1B1B1B;
}
QPushButton:hover {
    background: #F5F5F5;
    border-color: #B0B0B0;
}
QPushButton:pressed {
    background: #EDEDED;
}
QPushButton:default {
    background: #0067C0;
    border: 1px solid #0067C0;
    color: #FFFFFF;
}
QPushButton:default:hover {
    background: #0B7AD9;
    border-color: #0B7AD9;
}

/* ---------- 搜索输入框 ---------- */
QLineEdit {
    background: #FFFFFF;
    border: 1px solid #D0D0D0;
    border-radius: 6px;
    padding: 7px 10px;
    color: #1B1B1B;
}
QLineEdit:focus {
    border: 1px solid #0067C0;
}
QLineEdit::placeholder {
    color: #9A9A9A;
}

/* ---------- 项目列表表格 ---------- */
QTableWidget {
    background: #FFFFFF;
    border: 1px solid #EAEAEA;
    border-radius: 8px;
    gridline-color: #F1F1F1;
    selection-background-color: #E5F1FB;
    selection-color: #1B1B1B;
    outline: none;
}
QTableWidget::item {
    padding: 6px 8px;
    border: none;
}
QTableWidget::item:alternate {
    background: #FAFBFC;
}
QTableWidget::item:selected {
    background: #E5F1FB;
    color: #1B1B1B;
}
QHeaderView::section {
    background: #FAFAFA;
    color: #5A5A5A;
    padding: 9px 8px;
    border: none;
    border-right: 1px solid #EAEAEA;
    border-bottom: 1px solid #EAEAEA;
    font-weight: 600;
}
QHeaderView::section:hover {
    background: #F0F0F0;
}
QTableCornerButton::section {
    background: #FAFAFA;
    border: none;
    border-bottom: 1px solid #EAEAEA;
}

/* ---------- 项目详情页：概览卡 / 资料面板 ---------- */
QFrame#OverviewCard, QFrame#DocumentsPanel {
    background: #FFFFFF;
    border: 1px solid #EAEAEA;
    border-radius: 8px;
}
QLabel#PanelTitle {
    font-size: 15px;
    font-weight: 600;
    color: #1B1B1B;
    background: transparent;
}
QLabel#PanelHint {
    font-size: 12px;
    color: #9A9A9A;
    background: transparent;
}
QLabel#DocCount {
    color: #8A8A8A;
    background: transparent;
}
/* 概览卡内只读输入框：淡化边框，区别于可编辑输入框 */
QFrame#OverviewCard QLineEdit {
    background: #FAFBFC;
    border: 1px solid #ECECEC;
    color: #1B1B1B;
}

/* ---------- 扫描结果中心：统计卡片 ---------- */
QFrame#StatCard {
    background: #FFFFFF;
    border: 1px solid #EAEAEA;
    border-radius: 8px;
}

/* ---------- 扫描结果中心：详情预览面板 ---------- */
QFrame#DetailPreviewPanel {
    background: #FFFFFF;
    border: 1px solid #EAEAEA;
    border-radius: 8px;
}
"""

"""Excel 导入数据包。

包含：
- excel_reader.py：openpyxl 读取 + 表头动态识别
- import_worker.py：后台线程执行导入，避免 UI 卡死
"""

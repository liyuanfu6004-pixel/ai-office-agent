# AI Office Agent

面向通信设计人员的 Windows 11 桌面办公助手软件。

## 运行环境

- Python 3.14+
- PySide6 6.6+

## 安装依赖

在项目根目录执行：

```powershell
pip install -r requirements.txt
```

## 启动程序

```powershell
python run.py
```

## 目录结构

| 目录/文件 | 作用 |
| --- | --- |
| `run.py` | 程序启动入口 |
| `ai_office_agent/` | 主包，所有业务代码 |
| `ai_office_agent/app.py` | 应用程序入口与生命周期管理 |
| `ai_office_agent/config.py` | 配置加载与保存 |
| `ai_office_agent/core/` | 基础设施模块（数据库等） |
| `ai_office_agent/ui/` | 界面模块（主窗口及控件） |
| `ai_office_agent/utils/` | 通用工具（日志等） |
| `config/settings.json` | 应用配置文件 |
| `requirements.txt` | Python 依赖清单 |

运行时自动生成 `data/`（数据库）与 `logs/`（日志）目录。

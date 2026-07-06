"""AI Office Agent 启动入口。

在项目根目录运行以下命令即可启动程序：

    python run.py
"""
from ai_office_agent.app import main

if __name__ == "__main__":
    # 将退出码回传给操作系统
    raise SystemExit(main())

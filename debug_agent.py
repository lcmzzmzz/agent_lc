"""
PyCharm Debug 启动脚本

【正经注释】
PyCharm 以 Module name 方式运行时，断点可能不生效。
本脚本以 Script path 方式启动，内部用 runpy 调用 gpt_researcher.agent 模块，
确保断点、单步调试正常工作。

【大白话注释】
PyCharm 直接跑 agent.py 会报错（相对导入），用 Module name 跑断点又不生效。
这个脚本就是个"桥梁"——PyCharm 跑它，它帮你以正确方式启动 agent.py，
断点照打、调试照用。

用法：
    PyCharm Run Configuration:
    - Script path: D:\...\debug_agent.py
    - Working directory: D:\...\gpt-researcher-main\gpt-researcher-main
    - Python interpreter: 你的 conda 环境
"""

import runpy

if __name__ == "__main__":
    # 正经注释：runpy.run_module 以模块方式执行，等价于 python -m gpt_researcher.agent
    # 大白话注释：假装你在命令行敲了 python -m gpt_researcher.agent
    #           但因为是通过这个脚本启动的，PyCharm 的调试器能正常拦截断点
    runpy.run_module("gpt_researcher.agent", run_name="__main__")

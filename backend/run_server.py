"""
【正经注释】
GPT Researcher 后端服务器启动脚本。
本模块作为后端服务的入口点，负责配置 Python 模块搜索路径
并通过 Uvicorn ASGI 服务器启动 FastAPI 应用，支持热重载模式以便开发调试。

【大白话注释】
这个文件就是启动后端服务器的"开机按钮"。
运行这个文件就能把后端跑起来，监听 8000 端口。
开发模式下开了热重载——你改了代码，服务器会自动重启，不用手动关了再开。
"""

#!/usr/bin/env python3
"""
GPT-Researcher Backend Server Startup Script

Run this to start the research API server.
"""

import uvicorn  # 正经注释：Uvicorn ASGI 服务器，用于运行异步 Python Web 应用 / 大白话注释：一个高性能的 Web 服务器，专门跑 FastAPI 这种异步框架
import os  # 正经注释：操作系统接口模块，用于文件路径操作 / 大白话注释：用来处理文件和目录路径的
import sys  # 正经注释：系统相关模块，用于修改 Python 模块搜索路径 / 大白话注释：用来修改 Python 找模块的路径

# Add the backend directory to Python path
# 正经注释：将当前后端目录添加到 Python 模块搜索路径，确保模块可正确导入 / 大白话注释：告诉 Python "后端这个文件夹里的代码也要能找到"
backend_dir = os.path.dirname(os.path.abspath(__file__))  # 正经注释：获取当前脚本所在目录的绝对路径 / 大白话注释：拿到这个文件所在的文件夹路径
sys.path.insert(0, backend_dir)  # 正经注释：将后端目录插入到 sys.path 的最前面，优先搜索 / 大白话注释：把后端路径放到最前面，Python 找模块时先看这里

if __name__ == "__main__":
    # Change to backend directory
    # 正经注释：切换工作目录到后端目录，确保相对路径正确 / 大白话注释：把当前工作目录切到后端文件夹，这样找文件不会出错
    os.chdir(backend_dir)

    # Start the server
    # 正经注释：启动 Uvicorn ASGI 服务器，加载 FastAPI 应用 / 大白话注释：开机！启动 Web 服务器
    uvicorn.run(
        "server.app:app",  # 正经注释：指定 ASGI 应用位置，格式为"模块:变量" / 大白话注释：告诉服务器去哪里找 FastAPI 应用（server 文件夹里的 app）
        host="0.0.0.0",  # 正经注释：监听所有网络接口 / 大白话注释：0.0.0.0 意味着任何 IP 都能访问，不光是本机
        port=8000,  # 正经注释：监听端口号 / 大白话注释：在 8000 端口上提供服务
        reload=True,  # 正经注释：启用文件变更热重载 / 大白话注释：代码改了服务器自动重启，开发时很方便
        log_level="info"  # 正经注释：日志级别设为 INFO / 大白话注释：日志级别设为"信息"级，不会太啰嗦也不会太安静
    )



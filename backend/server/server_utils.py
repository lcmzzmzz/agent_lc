"""
服务端工具模块

【正经注释】
本模块是 GPT Researcher 后端服务的核心工具集，提供了研究任务执行所需的各类辅助功能。
主要包含：自定义日志处理器（CustomLogsHandler）、研究器封装（Researcher）、
WebSocket 通信处理、文件上传下载管理、环境变量配置、多代理任务执行、
命令数据提取以及报告文件生成等关键功能。

【大白话注释】
这个文件是个"工具箱"，里面装了后端服务需要的各种工具：
- 记日志的工具（把研究过程记录下来）
- 管研究的工具（启动研究任务、生成报告文件）
- 处理 WebSocket 消息的工具（接收命令、返回结果）
- 管文件的工具（上传文件、删除文件）
- 配置管理的工具（管理各种 API Key）
还有一大堆零碎但重要的辅助函数。基本上后端要干的杂活都在这里了。
"""
import asyncio  # 正经注释：导入异步 I/O 库用于并发操作 / 大白话注释：异步编程用的库
import json  # 正经注释：导入 JSON 序列化库 / 大白话注释：读写 JSON 数据的工具
import os  # 正经注释：导入操作系统接口模块 / 大白话注释：操作文件和目录的工具
import re  # 正经注释：导入正则表达式模块 / 大白话注释：用正则匹配字符串的工具
import time  # 正经注释：导入时间模块用于时间戳生成 / 大白话注释：获取时间的工具
import shutil  # 正经注释：导入文件操作高级模块 / 大白话注释：复制文件等高级文件操作
import traceback  # 正经注释：导入堆栈跟踪模块用于错误日志 / 大白话注释：出错时打印详细错误信息的工具
from typing import Awaitable, Dict, List, Any  # 正经注释：导入类型提示相关 / 大白话注释：告诉 Python 变量是啥类型
from fastapi.responses import JSONResponse, FileResponse  # 正经注释：导入 FastAPI 响应类 / 大白话注释：用来返回 JSON 或文件类型的 HTTP 响应
from gpt_researcher.document.document import DocumentLoader  # 正经注释：导入文档加载器 / 大白话注释：用来加载本地文档的工具
from gpt_researcher import GPTResearcher  # 正经注释：导入核心研究器类 / 大白话注释：GPT Researcher 的核心——做研究的引擎
from utils import write_md_to_pdf, write_md_to_word, write_text_to_md  # 正经注释：导入报告格式转换工具 / 大白话注释：把报告转成 PDF、Word、Markdown 的工具
from pathlib import Path  # 正经注释：导入路径操作类 / 大白话注释：更方便地处理文件路径
from datetime import datetime  # 正经注释：导入日期时间类 / 大白话注释：获取当前时间
from fastapi import HTTPException  # 正经注释：导入 HTTP 异常类 / 大白话注释：用来返回 HTTP 错误的
import logging  # 正经注释：导入日志模块 / 大白话注释：记日志用的
import hashlib  # 正经注释：导入哈希库用于文件名生成 / 大白话注释：生成哈希值的工具

from .multi_agent_runner import run_multi_agent_task  # 正经注释：导入多代理任务执行函数 / 大白话注释：跑多代理研究的函数

# Import chat agent
try:
    import sys  # 正经注释：导入系统模块用于路径操作 / 大白话注释：用来改 Python 找模块的路径
    backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 正经注释：计算 backend 目录的绝对路径 / 大白话注释：找到 backend 文件夹在哪
    if backend_path not in sys.path:  # 正经注释：确保 backend 目录在搜索路径中 / 大白话注释：把 backend 加到 Python 找模块的地方
        sys.path.insert(0, backend_path)
    from chat.chat import ChatAgentWithMemory  # 正经注释：导入带记忆的对话代理 / 大白话注释：能记住之前聊过什么的聊天机器人
except ImportError:
    ChatAgentWithMemory = None  # 正经注释：导入失败则设为 None / 大白话注释：没找到聊天模块就先设为空

logger = logging.getLogger(__name__)  # 正经注释：获取当前模块的日志记录器 / 大白话注释：给这个模块准备一个"记事本"

class CustomLogsHandler:
    """
    自定义研究日志流处理器。

    【正经注释】
    该类同时实现 WebSocket 实时日志推送和 JSON 文件持久化两种日志输出方式。
    在研究过程中，每条日志数据都会同时发送给 WebSocket 客户端并追加到本地 JSON 日志文件中。
    支持按数据类型分别处理：logs 类型记录为事件，其他类型更新到 content 部分。

    【大白话注释】
    这是个"双通道记事本"：一边把研究过程实时推送给浏览器（通过 WebSocket），
    一边把同样的内容写到本地 JSON 文件里留档。
    不同的信息类型还有不同的处理方式——日志类的记到"事件"里，
    其他类的（比如查询内容、报告）更新到"内容"部分。

    Args:
        websocket: WebSocket 连接对象，用于实时推送
        task: 研究任务描述文本，用于生成日志文件名
    """
    """Custom handler to capture streaming logs from the research process"""
    def __init__(self, websocket, task: str):
        """
        初始化自定义日志处理器。

        【正经注释】
        设置 WebSocket 引用、初始化日志列表、基于任务名生成安全的日志文件名，
        并在 outputs 目录下创建带有元数据的初始 JSON 日志文件。

        【大白话注释】
        准备好"双通道记事本"：记住跟谁通信（WebSocket）、准备好日志列表、
        用任务名生成一个文件名（去掉特殊字符），然后在 outputs 文件夹里
        创建一个空的 JSON 文件，写上时间戳等基本信息。

        Args:
            websocket: WebSocket 连接，可为 None（非流式场景）
            task: 任务描述文本
        """
        self.logs = []  # 正经注释：初始化日志缓存列表 / 大白话注释：在内存里也存一份日志
        self.websocket = websocket  # 正经注释：保存 WebSocket 引用 / 大白话注释：记住跟谁实时通信
        sanitized_filename = sanitize_filename(f"task_{int(time.time())}_{task}")  # 正经注释：生成安全的文件名 / 大白话注释：把任务名处理一下，变成合法的文件名
        self.log_file = os.path.join("outputs", f"{sanitized_filename}.json")  # 正经注释：构造日志文件的完整路径 / 大白话注释：日志文件放在 outputs 文件夹里
        self.timestamp = datetime.now().isoformat()  # 正经注释：记录初始化时间戳 / 大白话注释：记下现在几点几分
        # Initialize log file with metadata
        os.makedirs("outputs", exist_ok=True)  # 正经注释：确保 outputs 目录存在 / 大白话注释：outputs 文件夹没有就建一个
        with open(self.log_file, 'w') as f:  # 正经注释：创建并打开日志文件 / 大白话注释：打开文件准备写初始内容
            json.dump({
                "timestamp": self.timestamp,  # 正经注释：记录时间戳 / 大白话注释：创建时间
                "events": [],  # 正经注释：事件列表初始为空 / 大白话注释：还没发生啥事
                "content": {  # 正经注释：内容区域初始为空 / 大白话注释：研究的具体内容
                    "query": "",  # 正经注释：查询关键词 / 大白话注释：搜的啥
                    "sources": [],  # 正经注释：来源列表 / 大白话注释：从哪找到的
                    "context": [],  # 正经注释：上下文列表 / 大白话注释：背景信息
                    "report": "",  # 正经注释：报告文本 / 大白话注释：研究报告
                    "costs": 0.0  # 正经注释：研究花费 / 大白话注释：花了多少钱
                }
            }, f, indent=2)  # 正经注释：以缩进格式写入 / 大白话注释：排版好看地写进去

    async def send_json(self, data: Dict[str, Any]) -> None:
        """
        发送 JSON 数据到 WebSocket 并同时持久化到日志文件。

        【正经注释】
        将数据通过 WebSocket 实时发送给客户端，同时读取 JSON 日志文件，
        根据数据类型更新对应部分（logs 类型追加到事件列表，其他类型更新 content），
        然后写回文件。

        【大白话注释】
        一边通过 WebSocket 把数据实时推给浏览器，一边把数据存到本地文件。
        如果是"日志"类型的数据，就加到事件列表里；如果是其他类型（比如报告内容），
        就更新到内容区域。

        Args:
            data: 要发送和存储的数据字典
        """
        """Store log data and send to websocket"""
        # Send to websocket for real-time display
        if self.websocket:  # 正经注释：检查 WebSocket 是否可用 / 大白话注释：有连接才发
            await self.websocket.send_json(data)  # 正经注释：通过 WebSocket 发送 JSON 数据 / 大白话注释：把数据推给浏览器

        # Read current log file
        with open(self.log_file, 'r') as f:  # 正经注释：读取当前日志文件 / 大白话注释：先看看文件里现在有啥
            log_data = json.load(f)  # 正经注释：解析 JSON 数据 / 大白话注释：把文件内容读出来

        # Update appropriate section based on data type
        if data.get('type') == 'logs':  # 正经注释：如果是日志类型数据 / 大白话注释：如果是过程日志
            log_data['events'].append({  # 正经注释：追加到事件列表 / 大白话注释：加一条事件记录
                "timestamp": datetime.now().isoformat(),  # 正经注释：事件时间戳 / 大白话注释：什么时候发生的
                "type": "event",  # 正经注释：事件类型标记 / 大白话注释：标记为"事件"
                "data": data  # 正经注释：事件数据 / 大白话注释：具体内容
            })
        else:
            # Update content section for other types of data
            log_data['content'].update(data)  # 正经注释：更新内容部分 / 大白话注释：把新的内容合并进去

        # Save updated log file
        with open(self.log_file, 'w') as f:  # 正经注释：保存更新后的日志文件 / 大白话注释：把更新后的内容写回去
            json.dump(log_data, f, indent=2)  # 正经注释：以缩进格式写入 / 大白话注释：排版好看地写进去


class Researcher:
    """
    研究器封装类。

    【正经注释】
    封装了 GPTResearcher 核心研究流程，提供从查询初始化、研究执行、
    报告生成到文件输出的完整研究工作流。每个 Researcher 实例拥有独立的研究 ID
    和日志处理器。

    【大白话注释】
    这是个"研究员"类，把做研究的整个流程包在一起了：
    你给它一个问题，它就去查资料、写报告、生成各种格式的文件。
    每个研究员都有自己的编号和日志"记事本"。

    Args:
        query: 研究查询文本
        report_type: 报告类型，默认为 "research_report"
    """
    def __init__(self, query: str, report_type: str = "research_report"):
        """
        初始化研究器。

        【正经注释】
        根据查询和报告类型初始化研究器，生成唯一研究 ID（基于时间戳和查询哈希），
        创建日志处理器，并实例化 GPTResearcher 核心对象。

        【大白话注释】
        准备好一个"研究员"：记住要研究什么问题、生成一个独一无二的编号，
        准备好日志"记事本"，然后把核心研究引擎也启动起来。

        Args:
            query: 研究查询文本
            report_type: 报告类型，默认为 "research_report"
        """
        self.query = query  # 正经注释：保存研究查询 / 大白话注释：记住要研究啥
        self.report_type = report_type  # 正经注释：保存报告类型 / 大白话注释：记住报告要写成啥格式
        # Generate unique ID for this research task
        self.research_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(query)}"  # 正经注释：基于时间和查询哈希生成唯一 ID / 大白话注释：用时间和问题生成一个唯一编号
        # Initialize logs handler with research ID
        self.logs_handler = CustomLogsHandler(None, self.research_id)  # 正经注释：创建日志处理器（不绑定 WebSocket） / 大白话注释：准备日志"记事本"，但不跟浏览器连
        self.researcher = GPTResearcher(  # 正经注释：实例化核心研究器 / 大白话注释：把研究引擎启动起来
            query=query,
            report_type=report_type,
            websocket=self.logs_handler  # 正经注释：将日志处理器作为 WebSocket 替代 / 大白话注释：让研究引擎把日志写到"记事本"里
        )

    async def research(self) -> dict:
        """
        执行完整的研究流程并返回文件路径。

        【正经注释】
        依次执行研究过程（conduct_research）和报告撰写（write_report），
        然后调用 generate_report_files 生成 PDF、DOCX 和 MD 格式的报告文件，
        最后返回包含所有文件路径的字典。

        【大白话注释】
        让"研究员"开始干活：先查资料，再写报告，然后把报告转成
        PDF、Word 和 Markdown 三种格式。最后告诉你文件都存在哪里。

        Returns:
            dict: 包含 output 键的字典，里面有 pdf、docx、md、json 文件路径
        """
        """Conduct research and return paths to generated files"""
        await self.researcher.conduct_research()  # 正经注释：执行研究过程 / 大白话注释：开始查资料
        report = await self.researcher.write_report()  # 正经注释：生成研究报告 / 大白话注释：根据查到的资料写报告

        # Generate the files
        sanitized_filename = sanitize_filename(f"task_{int(time.time())}_{self.query}")  # 正经注释：生成安全的文件名 / 大白话注释：把文件名处理成合法的
        file_paths = await generate_report_files(report, sanitized_filename)  # 正经注释：生成多种格式的报告文件 / 大白话注释：把报告转成各种格式

        # Get the JSON log path that was created by CustomLogsHandler
        json_relative_path = os.path.relpath(self.logs_handler.log_file)  # 正经注释：获取日志文件的相对路径 / 大白话注释：拿到日志文件的路径

        return {  # 正经注释：返回包含所有文件路径的结果字典 / 大白话注释：把所有文件路径打包交出去
            "output": {
                **file_paths,  # Include PDF, DOCX, and MD paths
                "json": json_relative_path  # 正经注释：包含 JSON 日志路径 / 大白话注释：加上日志文件的路径
            }
        }

def sanitize_filename(filename: str) -> str:
    """
    将文件名清理为安全合法的格式。

    【正经注释】
    解析文件名的组成部分，对任务描述部分取 MD5 哈希前 10 位作为摘要，
    然后移除所有非单词、非空白、非连字符的字符，确保文件名在文件系统中安全可用。

    【大白话注释】
    把可能包含各种奇怪字符的文件名"洗干净"。
    把任务描述变成一串短哈希码，去掉特殊字符，让文件名不会因为非法字符而报错。

    Args:
        filename: 原始文件名字符串

    Returns:
        str: 清理后的安全文件名
    """
    # Split into components
    prefix, timestamp, *task_parts = filename.split('_')  # 正经注释：按下划线拆分文件名 / 大白话注释：把文件名按 _ 拆开
    task = '_'.join(task_parts)  # 正经注释：重新拼接任务部分 / 大白话注释：任务描述可能本身就有下划线，拼回去
    task_hash = hashlib.md5(task.encode('utf-8', errors='ignore')).hexdigest()[:10]  # 正经注释：取任务描述 MD5 哈希的前 10 位 / 大白话注释：把任务描述变成一串短哈希码

    # Reassemble and clean the filename
    sanitized = f"{prefix}_{timestamp}_{task_hash}"  # 正经注释：重新组装文件名 / 大白话注释：把前缀、时间戳、哈希码拼起来
    return re.sub(r"[^\w\s-]", "", sanitized).strip()  # 正经注释：移除所有非法字符 / 大白话注释：去掉文件名里不能用的特殊字符


async def handle_start_command(websocket, data: str, manager):
    """
    处理通过 WebSocket 发来的研究启动命令。

    【正经注释】
    解析 start 命令的 JSON 数据，提取研究参数，初始化日志处理器，
    通过 WebSocketManager 启动流式研究，生成报告文件并将路径发送回客户端。

    【大白话注释】
    当前端发来"开始研究"的命令时，这个函数就开始干活了：
    把命令里的参数拆出来（研究什么、什么格式、语气等等），
    开始做研究、生成报告文件，然后告诉前端文件都在哪里。

    Args:
        websocket: WebSocket 连接对象
        data: 包含命令参数的原始字符串（以 "start" 开头）
        manager: WebSocketManager 实例
    """
    json_data = json.loads(data[6:])  # 正经注释：去掉 "start " 前缀后解析 JSON / 大白话注释：把命令前缀去掉，解析出 JSON 数据
    (
        task,
        report_type,
        source_urls,
        document_urls,
        tone,
        headers,
        report_source,
        query_domains,
        mcp_enabled,
        mcp_strategy,
        mcp_configs,
        max_search_results,
    ) = extract_command_data(json_data)  # 正经注释：从 JSON 中提取各参数 / 大白话注释：把参数一个个拆出来

    if not task or not report_type:  # 正经注释：校验必要参数是否存在 / 大白话注释：任务和报告类型缺一不可
        print("Error: Missing task or report_type")
        return

    # Create logs handler with websocket and task
    logs_handler = CustomLogsHandler(websocket, task)  # 正经注释：创建绑定 WebSocket 的日志处理器 / 大白话注释：准备"记事本"，这次跟浏览器连着
    # Initialize log content with query
    await logs_handler.send_json({  # 正经注释：发送初始查询信息 / 大白话注释：先往日志里写上"开始查啥了"
        "query": task,
        "sources": [],
        "context": [],
        "report": ""
    })

    sanitized_filename = sanitize_filename(f"task_{int(time.time())}_{task}")  # 正经注释：生成安全的文件名 / 大白话注释：把文件名处理好

    report = await manager.start_streaming(  # 正经注释：通过管理器启动流式研究 / 大白话注释：让管理器开始做研究，实时推送进度
        task,
        report_type,
        report_source,
        source_urls,
        document_urls,
        tone,
        websocket,
        headers,
        query_domains,
        mcp_enabled,
        mcp_strategy,
        mcp_configs,
        max_search_results,
    )
    report = str(report)  # 正经注释：确保报告为字符串类型 / 大白话注释：把报告转成字符串
    file_paths = await generate_report_files(report, sanitized_filename)  # 正经注释：生成报告文件 / 大白话注释：把报告转成各种格式的文件
    # Add JSON log path to file_paths
    file_paths["json"] = os.path.relpath(logs_handler.log_file)  # 正经注释：添加日志文件路径 / 大白话注释：把日志文件的路径也加上
    await send_file_paths(websocket, file_paths)  # 正经注释：将文件路径发送回客户端 / 大白话注释：告诉前端文件都在哪里


async def handle_human_feedback(data: str):
    """
    处理人工反馈命令。

    【正经注释】
    解析 human_feedback 命令的 JSON 数据，并打印反馈内容。
    当前为占位实现，后续将添加将反馈转发给相应代理或更新研究状态的逻辑。

    【大白话注释】
    收到人工反馈时，把反馈内容打印出来。
    这功能目前还是个空壳子，以后再完善。

    Args:
        data: 包含反馈数据的原始字符串（以 "human_feedback" 开头）
    """
    feedback_data = json.loads(data[14:])  # Remove "human_feedback" prefix  # 正经注释：去掉命令前缀后解析 JSON / 大白话注释：把 "human_feedback" 前缀去掉，解析数据
    print(f"Received human feedback: {feedback_data}")  # 正经注释：打印收到的反馈 / 大白话注释：在控制台显示收到的反馈
    # TODO: Add logic to forward the feedback to the appropriate agent or update the research state


async def handle_chat_command(websocket, data: str):
    """
    处理通过 WebSocket 发来的对话命令。

    【正经注释】
    解析 chat 命令的 JSON 数据，提取消息和报告上下文，创建带记忆的对话代理
    进行对话处理，然后将回复通过 WebSocket 发送回客户端。
    支持单条消息和多轮对话两种输入格式。

    【大白话注释】
    前端发来"聊天"命令时，这个函数来处理：
    把消息解析出来，创建一个能记住上下文的聊天机器人来回答，
    然后把回答通过 WebSocket 推回给前端。
    如果只发了一条消息，会自动转成对话格式。

    Args:
        websocket: WebSocket 连接对象
        data: 包含对话数据的原始字符串（以 "chat" 开头）
    """
    """Handle chat command from WebSocket."""
    try:
        # Parse chat data - format is "chat {json_data}"
        json_str = data[5:].strip()  # Remove "chat " prefix  # 正经注释：去掉 "chat " 前缀 / 大白话注释：把 "chat " 前缀去掉
        chat_data = json.loads(json_str)  # 正经注释：解析 JSON 数据 / 大白话注释：把字符串变成字典

        message = chat_data.get("message", "")  # 正经注释：提取单条消息 / 大白话注释：拿到消息内容
        report = chat_data.get("report", "")  # 正经注释：提取报告上下文 / 大白话注释：拿到关联的报告
        messages = chat_data.get("messages", [])  # 正经注释：提取消息历史列表 / 大白话注释：拿到之前的聊天记录

        # If only message is provided, convert to messages format
        if message and not messages:  # 正经注释：如果只有单条消息，转换为消息列表格式 / 大白话注释：只给了消息没给历史记录的话，把消息包装成列表
            messages = [{"role": "user", "content": message}]

        if not messages:  # 正经注释：如果没有消息则返回错误提示 / 大白话注释：啥消息都没有就说一声
            await websocket.send_json({
                "type": "chat",
                "content": "No message provided.",
                "role": "assistant"
            })
            return

        # Check if ChatAgentWithMemory is available
        if ChatAgentWithMemory is None:  # 正经注释：检查对话代理是否可用 / 大白话注释：聊天模块没装的话
            await websocket.send_json({
                "type": "chat",
                "content": "Chat functionality is not available. Please check the server configuration.",
                "role": "assistant"
            })
            return

        # Create chat agent with the report context
        chat_agent = ChatAgentWithMemory(  # 正经注释：创建带记忆的对话代理 / 大白话注释：把聊天机器人叫出来，让它知道报告内容
            report=report,
            config_path="default",
            headers=None
        )

        # Process the chat
        response_content, tool_calls_metadata = await chat_agent.chat(messages, websocket)  # 正经注释：执行对话处理并获取回复 / 大白话注释：让聊天机器人回答问题

        # Send response back via WebSocket
        await websocket.send_json({  # 正经注释：将回复发送回客户端 / 大白话注释：把回答推给前端
            "type": "chat",
            "content": response_content,
            "role": "assistant",
            "metadata": {
                "tool_calls": tool_calls_metadata  # 正经注释：附加工具调用元数据 / 大白话注释：如果用到了工具，也告诉前端
            } if tool_calls_metadata else None
        })

        logger.info(f"Chat response sent successfully")  # 正经注释：记录发送成功日志 / 大白话注释：记下来聊天回答发成功了

    except json.JSONDecodeError as e:  # 正经注释：捕获 JSON 解析异常 / 大白话注释：消息格式不对
        logger.error(f"Failed to parse chat data: {e}")
        await websocket.send_json({
            "type": "chat",
            "content": f"Error: Invalid message format - {str(e)}",
            "role": "assistant"
        })
    except Exception as e:  # 正经注释：捕获其他所有异常 / 大白话注释：其他意外错误
        logger.error(f"Error handling chat command: {e}\n{traceback.format_exc()}")
        await websocket.send_json({
            "type": "chat",
            "content": f"Error processing your message: {str(e)}",
            "role": "assistant"
        })

async def generate_report_files(report: str, filename: str) -> Dict[str, str]:
    """
    将报告文本生成多种格式的文件。

    【正经注释】
    接收报告文本和文件名，依次生成 PDF、DOCX 和 Markdown 三种格式的文件，
    返回包含三种文件路径的字典。

    【大白话注释】
    把一份报告同时转成三种格式（PDF、Word、Markdown），
    然后告诉你每种格式的文件存在哪里。

    Args:
        report: 报告的 Markdown 文本
        filename: 输出文件的基础名称（不含扩展名）

    Returns:
        Dict[str, str]: 包含 pdf、docx、md 三个键值对的文件路径字典
    """
    pdf_path = await write_md_to_pdf(report, filename)  # 正经注释：生成 PDF 文件 / 大白话注释：转成 PDF
    docx_path = await write_md_to_word(report, filename)  # 正经注释：生成 Word 文件 / 大白话注释：转成 Word
    md_path = await write_text_to_md(report, filename)  # 正经注释：生成 Markdown 文件 / 大白话注释：存成 Markdown
    return {"pdf": pdf_path, "docx": docx_path, "md": md_path}  # 正经注释：返回所有文件路径 / 大白话注释：把三个路径打包交出去


async def send_file_paths(websocket, file_paths: Dict[str, str]):
    """
    通过 WebSocket 发送文件路径信息。

    【正经注释】
    将报告文件路径封装为 type="path" 的 JSON 消息并发送到 WebSocket 客户端。

    【大白话注释】
    告诉前端："你的文件都生成好了，在以下这些路径可以找到。"

    Args:
        websocket: WebSocket 连接对象
        file_paths: 包含各格式文件路径的字典
    """
    await websocket.send_json({"type": "path", "output": file_paths})  # 正经注释：发送路径消息 / 大白话注释：把路径信息推给前端


def get_config_dict(
    langchain_api_key: str, openai_api_key: str, tavily_api_key: str,
    google_api_key: str, google_cx_key: str, bing_api_key: str,
    searchapi_api_key: str, serpapi_api_key: str, serper_api_key: str, searx_url: str
) -> Dict[str, str]:
    """
    构建配置字典，合并传入参数和环境变量。

    【正经注释】
    接收各种 API Key 和配置参数，优先使用传入的值，如果为空则回退到对应的环境变量。
    返回一个包含所有配置项的统一字典。

    【大白话注释】
    把各种 API Key 和配置项收集到一起。你传了值就用你的，没传就去环境变量里找。
    最后打包成一个字典交出去。

    Args:
        langchain_api_key: LangChain API 密钥
        openai_api_key: OpenAI API 密钥
        tavily_api_key: Tavily 搜索 API 密钥
        google_api_key: Google API 密钥
        google_cx_key: Google 自定义搜索引擎 ID
        bing_api_key: Bing 搜索 API 密钥
        searchapi_api_key: SearchAPI 密钥
        serpapi_api_key: SerpAPI 密钥
        serper_api_key: Serper API 密钥
        searx_url: Searx 搜索引擎 URL

    Returns:
        Dict[str, str]: 包含所有配置项的字典
    """
    return {
        "LANGCHAIN_API_KEY": langchain_api_key or os.getenv("LANGCHAIN_API_KEY", ""),  # 正经注释：LangChain 密钥 / 大白话注释：LangChain 的钥匙
        "OPENAI_API_KEY": openai_api_key or os.getenv("OPENAI_API_KEY", ""),  # 正经注释：OpenAI 密钥 / 大白话注释：OpenAI 的钥匙
        "TAVILY_API_KEY": tavily_api_key or os.getenv("TAVILY_API_KEY", ""),  # 正经注释：Tavily 密钥 / 大白话注释：Tavily 搜索的钥匙
        "GOOGLE_API_KEY": google_api_key or os.getenv("GOOGLE_API_KEY", ""),  # 正经注释：Google API 密钥 / 大白话注释：Google 的钥匙
        "GOOGLE_CX_KEY": google_cx_key or os.getenv("GOOGLE_CX_KEY", ""),  # 正经注释：Google CX 密钥 / 大白话注释：Google 搜索引擎的 ID
        "BING_API_KEY": bing_api_key or os.getenv("BING_API_KEY", ""),  # 正经注释：Bing 密钥 / 大白话注释：必应搜索的钥匙
        "SEARCHAPI_API_KEY": searchapi_api_key or os.getenv("SEARCHAPI_API_KEY", ""),  # 正经注释：SearchAPI 密钥 / 大白话注释：SearchAPI 的钥匙
        "SERPAPI_API_KEY": serpapi_api_key or os.getenv("SERPAPI_API_KEY", ""),  # 正经注释：SerpAPI 密钥 / 大白话注释：SerpAPI 的钥匙
        "SERPER_API_KEY": serper_api_key or os.getenv("SERPER_API_KEY", ""),  # 正经注释：Serper 密钥 / 大白话注释：Serper 的钥匙
        "SEARX_URL": searx_url or os.getenv("SEARX_URL", ""),  # 正经注释：Searx URL / 大白话注释：Searx 搜索引擎地址
        "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2", "true"),  # 正经注释：LangChain 追踪开关 / 大白话注释：要不要开启 LangChain 追踪
        "DOC_PATH": os.getenv("DOC_PATH", "./my-docs"),  # 正经注释：文档目录路径 / 大白话注释：本地文档放在哪
        "RETRIEVER": os.getenv("RETRIEVER", ""),  # 正经注释：默认检索器 / 大白话注释：用哪个搜索引擎
        "EMBEDDING_MODEL": os.getenv("OPENAI_EMBEDDING_MODEL", "")  # 正经注释：嵌入模型配置 / 大白话注释：用哪个文本向量化模型
    }


def update_environment_variables(config: Dict[str, str]):
    """
    批量更新操作系统环境变量。

    【正经注释】
    遍历配置字典中的所有键值对，逐一设置到 os.environ 中，
    使其成为全局可用的环境变量。

    【大白话注释】
    把配置字典里的每一项都设成环境变量，这样其他地方就能用 os.getenv 拿到了。

    Args:
        config: 要更新的环境变量字典
    """
    for key, value in config.items():  # 正经注释：遍历配置字典 / 大白话注释：一个个来
        os.environ[key] = value  # 正经注释：设置环境变量 / 大白话注释：把值写进环境变量


async def handle_file_upload(file, DOC_PATH: str) -> Dict[str, str]:
    """
    处理文件上传请求。

    【正经注释】
    将上传的文件保存到指定文档目录，使用 os.path.basename 防止路径遍历攻击，
    然后使用 DocumentLoader 加载文档内容以供后续研究使用。

    【大白话注释】
    把用户上传的文件存到指定文件夹里，然后把文件内容加载到系统中，
    这样做研究的时候就能查到这些文件里的内容了。
    为了安全，只取文件名部分，防止有人搞路径穿越攻击。

    Args:
        file: 上传的文件对象（UploadFile）
        DOC_PATH: 文档存储目录路径

    Returns:
        Dict[str, str]: 包含文件名和存储路径的字典
    """
    file_path = os.path.join(DOC_PATH, os.path.basename(file.filename))  # 正经注释：构造安全的文件存储路径 / 大白话注释：把文件存到指定文件夹，只用文件名防攻击
    with open(file_path, "wb") as buffer:  # 正经注释：以二进制写入模式打开文件 / 大白话注释：打开文件准备写入
        shutil.copyfileobj(file.file, buffer)  # 正经注释：将上传文件内容拷贝到目标路径 / 大白话注释：把上传的文件内容复制过去
    print(f"File uploaded to {file_path}")  # 正经注释：打印上传成功信息 / 大白话注释：在控制台说一声文件存好了

    document_loader = DocumentLoader(DOC_PATH)  # 正经注释：创建文档加载器 / 大白话注释：准备加载文档的工具
    await document_loader.load()  # 正经注释：异步加载文档内容 / 大白话注释：把文档内容读进系统

    return {"filename": file.filename, "path": file_path}  # 正经注释：返回文件信息 / 大白话注释：告诉调用者文件名和路径


async def handle_file_deletion(filename: str, DOC_PATH: str) -> JSONResponse:
    """
    处理文件删除请求。

    【正经注释】
    在指定文档目录中查找并删除目标文件。使用 os.path.basename 防止路径遍历攻击。
    文件不存在时返回 404 响应，成功删除时返回确认消息。

    【大白话注释】
    删掉指定文件夹里的某个文件。文件不存在就告诉你"找不到"，
    找到了就删掉并说一声"删好了"。同样只取文件名防攻击。

    Args:
        filename: 要删除的文件名
        DOC_PATH: 文档存储目录路径

    Returns:
        JSONResponse: 包含操作结果的 JSON 响应
    """
    file_path = os.path.join(DOC_PATH, os.path.basename(filename))  # 正经注释：构造安全的文件路径 / 大白话注释：拼出文件的完整路径，只用文件名防攻击
    if os.path.exists(file_path):  # 正经注释：检查文件是否存在 / 大白话注释：看看文件在不在
        os.remove(file_path)  # 正经注释：删除文件 / 大白话注释：删掉它
        print(f"File deleted: {file_path}")  # 正经注释：打印删除成功信息 / 大白话注释：在控制台说一声删好了
        return JSONResponse(content={"message": "File deleted successfully"})  # 正经注释：返回成功响应 / 大白话注释：告诉调用者删成功了
    else:
        print(f"File not found: {file_path}")  # 正经注释：打印文件未找到信息 / 大白话注释：在控制台说一声找不到
        return JSONResponse(status_code=404, content={"message": "File not found"})  # 正经注释：返回 404 响应 / 大白话注释：告诉调用者文件不存在


async def execute_multi_agents(manager) -> Any:
    """
    执行多代理研究任务。

    【正经注释】
    从 WebSocketManager 的活跃连接中获取第一个 WebSocket 连接，
    使用默认参数（"Is AI in a hype cycle?"）执行多代理研究任务。
    如果没有活跃的 WebSocket 连接，返回 400 错误响应。

    【大白话注释】
    跑一遍多代理系统做研究。它会拿第一个连着的 WebSocket 来推送进度，
    用一个固定的研究问题（"AI 是不是泡沫？"）来跑。
    如果没有 WebSocket 连着就报错。

    Args:
        manager: WebSocketManager 实例

    Returns:
        Any: 包含报告的字典，或错误 JSON 响应
    """
    websocket = manager.active_connections[0] if manager.active_connections else None  # 正经注释：获取第一个活跃的 WebSocket 连接 / 大白话注释：看看有没有人连着，拿第一个
    if websocket:  # 正经注释：有活跃连接则执行任务 / 大白话注释：有人连着就开始
        report = await run_multi_agent_task("Is AI in a hype cycle?", websocket, stream_output)  # 正经注释：执行多代理研究任务 / 大白话注释：跑多代理研究，用默认问题
        return {"report": report}  # 正经注释：返回研究报告 / 大白话注释：把报告交出去
    else:
        return JSONResponse(status_code=400, content={"message": "No active WebSocket connection"})  # 正经注释：无连接返回 400 错误 / 大白话注释：没人连着就报错


async def handle_websocket_communication(websocket, manager):
    """
    处理 WebSocket 通信的主循环。

    【正经注释】
    持续监听 WebSocket 消息，根据消息内容分发到不同的命令处理器。
    支持 ping 心跳检测、start 研究命令、human_feedback 反馈命令、chat 对话命令。
    使用 asyncio.Task 管理长时间运行的研究任务，同一时间只允许运行一个任务。
    在连接断开时自动取消正在运行的任务。

    【大白话注释】
    这是 WebSocket 通信的"总调度"：不停接收前端发来的消息，按消息类型分发给不同的人去处理。
    - ping：回复 pong（心跳检测）
    - start：启动研究
    - human_feedback：收到人工反馈
    - chat：开始对话
    同一时间只允许跑一个研究任务，多出来的请求会被拒绝。
    连接断了就自动把正在跑的任务取消掉。

    Args:
        websocket: WebSocket 连接对象
        manager: WebSocketManager 实例
    """
    running_task: asyncio.Task | None = None  # 正经注释：当前运行中的任务引用 / 大白话注释：记住现在有没有在跑的任务

    def run_long_running_task(awaitable: Awaitable) -> asyncio.Task:
        """
        将异步任务包装为安全的 asyncio.Task 并启动。

        【正经注释】
        创建一个包装协程，捕获 CancelledError 和通用 Exception，
        在出错时通过 WebSocket 发送错误日志消息。返回已启动的 Task 对象。

        【大白话注释】
        把一个任务包一层"安全网"再启动：
        如果任务被取消了，就优雅地结束；
        如果出错了，就告诉前端"出错了"而不是直接崩溃。

        Args:
            awaitable: 要执行的异步操作

        Returns:
            asyncio.Task: 已创建并启动的任务对象
        """
        async def safe_run():  # 正经注释：安全包装协程 / 大白话注释：带"安全网"的任务执行函数
            try:
                await awaitable  # 正经注释：执行实际任务 / 大白话注释：开始干活
            except asyncio.CancelledError:  # 正经注释：捕获任务取消异常 / 大白话注释：任务被取消了
                logger.info("Task cancelled.")
                raise  # 正经注释：重新抛出取消异常以正确终止任务 / 大白话注释：正式结束任务
            except Exception as e:  # 正经注释：捕获其他所有异常 / 大白话注释：出错了
                logger.error(f"Error running task: {e}\n{traceback.format_exc()}")
                await websocket.send_json(  # 正经注释：通过 WebSocket 发送错误信息 / 大白话注释：告诉前端出错了
                    {
                        "type": "logs",
                        "content": "error",
                        "output": f"Error: {e}",
                    }
                )

        return asyncio.create_task(safe_run())  # 正经注释：创建并启动异步任务 / 大白话注释：把任务扔到后台去跑

    try:
        while True:  # 正经注释：持续监听 WebSocket 消息 / 大白话注释：不停地接收消息
            try:
                data = await websocket.receive_text()  # 正经注释：等待接收文本消息 / 大白话注释：等前端发消息过来
                logger.info(f"Received WebSocket message: {data[:50]}..." if len(data) > 50 else data)  # 正经注释：记录收到的消息（截断过长的） / 大白话注释：在日志里记下来收到啥了

                if data == "ping":  # 正经注释：处理心跳检测 / 大白话注释：前端问"还在吗？"
                    await websocket.send_text("pong")  # 正经注释：回复 pong / 大白话注释：回复"在呢！"
                elif running_task and not running_task.done():  # 正经注释：检查是否有任务正在运行 / 大白话注释：已经有任务在跑了
                    # discard any new request if a task is already running
                    logger.warning(  # 正经注释：记录警告日志 / 大白话注释：记下来"又来请求了但我忙着呢"
                        f"Received request while task is already running. Request data preview: {data[: min(20, len(data))]}..."
                    )
                    await websocket.send_json(  # 正经注释：通知客户端任务正在运行 / 大白话注释：告诉前端"忙着呢，等着"
                        {
                            "type": "logs",
                            "content": "warning",
                            "output": "Task already running. Please wait.",
                        }
                    )
                # Normalize command detection by checking startswith after stripping whitespace
                elif data.strip().startswith("start"):  # 正经注释：处理研究启动命令 / 大白话注释：收到"开始研究"命令
                    logger.info(f"Processing start command")
                    running_task = run_long_running_task(  # 正经注释：在后台启动研究任务 / 大白话注释：把研究任务扔到后台去跑
                        handle_start_command(websocket, data, manager)
                    )
                elif data.strip().startswith("human_feedback"):  # 正经注释：处理人工反馈命令 / 大白话注释：收到人工反馈了
                    logger.info(f"Processing human_feedback command")
                    running_task = run_long_running_task(handle_human_feedback(data))  # 正经注释：在后台处理反馈 / 大白话注释：把反馈处理扔到后台
                elif data.strip().startswith("chat"):  # 正经注释：处理对话命令 / 大白话注释：收到"聊天"命令
                    logger.info(f"Processing chat command")
                    running_task = run_long_running_task(handle_chat_command(websocket, data))  # 正经注释：在后台启动对话 / 大白话注释：把聊天扔到后台去处理
                else:  # 正经注释：未知命令处理 / 大白话注释：不认识的命令
                    error_msg = f"Error: Unknown command or not enough parameters provided. Received: '{data[:100]}...'" if len(data) > 100 else f"Error: Unknown command or not enough parameters provided. Received: '{data}'"
                    logger.error(error_msg)  # 正经注释：记录错误日志 / 大白话注释：记下来出了啥错
                    print(error_msg)
                    await websocket.send_json({  # 正经注释：通知客户端命令不可识别 / 大白话注释：告诉前端"你说啥我听不懂"
                        "type": "error",
                        "content": "error",
                        "output": "Unknown command received by server"
                    })
            except Exception as e:  # 正经注释：捕获消息处理异常 / 大白话注释：处理消息时出错了
                logger.error(f"WebSocket error: {str(e)}\n{traceback.format_exc()}")
                print(f"WebSocket error: {e}")
                break  # 正经注释：跳出循环结束通信 / 大白话注释：出错了就不听了
    finally:
        if running_task and not running_task.done():  # 正经注释：通信结束时取消未完成的任务 / 大白话注释：断了连接就把还在跑的活儿取消掉
            running_task.cancel()

def extract_command_data(json_data: Dict) -> tuple:
    """
    从命令 JSON 数据中提取所有研究参数。

    【正经注释】
    从传入的 JSON 字典中提取研究任务所需的所有参数，包括任务描述、报告类型、
    来源 URL、文档 URL、语气、请求头、报告来源、查询域名、MCP 配置等。
    对于可选字段提供合理的默认值。

    【大白话注释】
    从前端发来的 JSON 数据里，把做研究需要的参数一个个拿出来：
    研究什么问题、报告什么格式、从哪些网站查、语气怎么样等等。
    如果有些参数没给，就用默认值。

    Args:
        json_data: 包含命令参数的字典

    Returns:
        tuple: 按顺序包含所有提取出的参数值
    """
    return (
        json_data.get("task"),  # 正经注释：研究任务描述 / 大白话注释：要研究啥
        json_data.get("report_type"),  # 正经注释：报告类型 / 大白话注释：报告啥格式
        json_data.get("source_urls"),  # 正经注释：来源 URL 列表 / 大白话注释：从哪些网址查
        json_data.get("document_urls"),  # 正经注释：文档 URL 列表 / 大白话注释：从哪些文档查
        json_data.get("tone"),  # 正经注释：报告语气 / 大白话注释：用啥语气写
        json_data.get("headers", {}),  # 正经注释：HTTP 请求头 / 大白话注释：请求头信息，默认空的
        json_data.get("report_source"),  # 正经注释：报告来源类型 / 大白话注释：从哪里查资料（网络/本地/混合）
        json_data.get("query_domains", []),  # 正经注释：限定查询域名列表 / 大白话注释：只在哪些网站查，默认不限
        json_data.get("mcp_enabled", False),  # 正经注释：MCP 是否启用 / 大白话注释：要不要用 MCP 工具，默认不用
        json_data.get("mcp_strategy", "fast"),  # 正经注释：MCP 策略 / 大白话注释：MCP 用什么策略，默认"快速"
        json_data.get("mcp_configs", []),  # 正经注释：MCP 配置列表 / 大白话注释：MCP 的具体配置，默认空的
        json_data.get("max_search_results"),  # 正经注释：最大搜索结果数 / 大白话注释：最多搜多少条结果
    )

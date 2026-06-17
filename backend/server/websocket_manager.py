"""
WebSocket 管理器模块

【正经注释】
本模块实现了 WebSocket 连接的完整生命周期管理，包括连接的建立与断开、消息队列的维护、
发送任务的调度以及研究任务的流式启动。同时包含核心的 run_agent 函数，
负责根据报告类型（多代理、详细报告、基础报告）初始化并执行相应的研究器。

【大白话注释】
这个模块管的是 WebSocket 连接——就是前端和后端之间的"实时通信通道"。
它负责：谁连上来了就记住、谁走了就清理掉、消息排队发别堵车、
还能启动研究任务并实时把进度推给前端。
另外还有个核心函数 run_agent，根据你要什么类型的报告，
选对应的研究引擎来干活。
"""
import os  # 正经注释：导入操作系统接口模块 / 大白话注释：操作文件和环境变量的工具
import asyncio  # 正经注释：导入异步 I/O 库 / 大白话注释：异步编程用的库
import datetime  # 正经注释：导入日期时间模块 / 大白话注释：处理时间的工具
import json  # 正经注释：导入 JSON 序列化库 / 大白话注释：读写 JSON 的工具
import logging  # 正经注释：导入日志模块 / 大白话注释：记日志的工具
import os  # 正经注释：再次导入 os（冗余但保留原样） / 大白话注释：重复导入，不影响功能
import traceback  # 正经注释：导入堆栈跟踪模块 / 大白话注释：出错时打印详细错误信息的工具
from typing import Dict, List  # 正经注释：导入类型提示相关 / 大白话注释：告诉 Python 变量是啥类型

from fastapi import WebSocket  # 正经注释：导入 FastAPI WebSocket 类 / 大白话注释：FastAPI 的 WebSocket 支持

from backend.report_type import BasicReport, DetailedReport  # 正经注释：导入基础报告和详细报告处理器 / 大白话注释：两种报告类型的处理引擎

from gpt_researcher.utils.enum import ReportType, Tone  # 正经注释：导入报告类型和语气枚举 / 大白话注释：报告类型和语气的选项列表
from gpt_researcher.actions import stream_output  # Import stream_output  # 正经注释：导入流式输出函数 / 大白话注释：用来实时推送研究进度的函数
from .multi_agent_runner import run_multi_agent_task  # 正经注释：导入多代理任务执行函数 / 大白话注释：跑多代理研究的函数
from .server_utils import CustomLogsHandler  # 正经注释：导入自定义日志处理器 / 大白话注释：那个"双通道记事本"

logger = logging.getLogger(__name__)  # 正经注释：获取当前模块的日志记录器 / 大白话注释：给这个模块准备一个"记事本"

class WebSocketManager:
    """
    WebSocket 连接管理器。

    【正经注释】
    管理 WebSocket 连接的生命周期，维护活跃连接列表、每个连接的消息队列
    和对应的发送任务。通过异步消息队列实现消息的有序发送，
    避免并发写入导致的消息交错问题。

    【大白话注释】
    这个类就是个"前台接待员"：谁连上来了就登记一下，给每人分一个消息队列
    （就是排队等发消息的通道），然后安排一个"快递员"专门给这个人送消息。
    人走了就把登记信息删掉、把快递员辞了。
    """
    """Manage websockets"""

    def __init__(self):
        """
        初始化 WebSocket 管理器。

        【正经注释】
        初始化三个核心数据结构：活跃连接列表、发送任务映射和消息队列映射。

        【大白话注释】
        准备三个本子：
        - 第一个记着"谁在线"
        - 第二个记着"谁的快递员是谁"
        - 第三个记着"谁的消息还没发完"
        """
        """Initialize the WebSocketManager class."""
        self.active_connections: List[WebSocket] = []  # 正经注释：当前活跃的 WebSocket 连接列表 / 大白话注释：谁现在在线
        self.sender_tasks: Dict[WebSocket, asyncio.Task] = {}  # 正经注释：每个连接对应的发送任务 / 大白话注释：每个在线用户的专属快递员
        self.message_queues: Dict[WebSocket, asyncio.Queue] = {}  # 正经注释：每个连接的消息队列 / 大白话注释：每个在线用户的消息排队通道

    async def start_sender(self, websocket: WebSocket):
        """
        启动指定连接的消息发送循环。

        【正经注释】
        持续从消息队列中取出消息并发送到 WebSocket。收到 None 值时视为关闭信号并退出循环。
        处理 ping 心跳检测，连接断开时自动退出。

        【大白话注释】
        这就是个"快递员"的工作流程：不停从消息队列里取消息，取到就送出去。
        如果取到的是 None，说明该下班了。如果是 ping 就回 pong。
        如果收件人不在了（连接断了），快递员也就不用干了。

        Args:
            websocket: 要发送消息的 WebSocket 连接
        """
        """Start the sender task."""
        queue = self.message_queues.get(websocket)  # 正经注释：获取该连接的消息队列 / 大白话注释：找到这个人的消息通道
        if not queue:  # 正经注释：没有队列则直接返回 / 大白话注释：没有通道就算了
            return

        while True:  # 正经注释：持续发送消息循环 / 大白话注释：不停地取消息、发消息
            try:
                message = await queue.get()  # 正经注释：从队列中取出下一条消息 / 大白话注释：从通道里取一条消息
                if message is None:  # Shutdown signal  # 正经注释：None 表示关闭信号 / 大白话注释：收到"下班"信号
                    break  # 正经注释：退出发送循环 / 大白话注释：下班了

                if websocket in self.active_connections:  # 正经注释：检查连接是否仍然活跃 / 大白话注释：看看收件人还在不在
                    if message == "ping":  # 正经注释：处理心跳消息 / 大白话注释：收到心跳检测
                        await websocket.send_text("pong")  # 正经注释：回复 pong / 大白话注释：回个"还活着"
                    else:
                        await websocket.send_text(message)  # 正经注释：发送普通文本消息 / 大白话注释：把消息送出去
                else:
                    break  # 正经注释：连接已断开则退出 / 大白话注释：人不在了，下班
            except Exception as e:  # 正经注释：捕获发送异常 / 大白话注释：送消息出问题了
                print(f"Error in sender task: {e}")
                break  # 正经注释：异常时退出循环 / 大白话注释：出问题就不送了

    async def connect(self, websocket: WebSocket):
        """
        接受并注册新的 WebSocket 连接。

        【正经注释】
        完成 WebSocket 握手（accept），将连接添加到活跃列表，
        创建对应的消息队列并启动专属的发送任务。
        如果连接过程中出现异常，自动清理已创建的资源。

        【大白话注释】
        新客人来了：握个手（accept）、登记到"在线名单"里、
        给他分配一个消息通道和一个专属快递员。
        要是握手失败了就赶紧把登记信息清掉。

        Args:
            websocket: 新的 WebSocket 连接对象
        """
        """Connect a websocket."""
        try:
            await websocket.accept()  # 正经注释：接受 WebSocket 连接请求 / 大白话注释：跟前端握手
            self.active_connections.append(websocket)  # 正经注释：将连接添加到活跃列表 / 大白话注释：登记到"在线名单"
            self.message_queues[websocket] = asyncio.Queue()  # 正经注释：创建消息队列 / 大白话注释：给这人开一个消息通道
            self.sender_tasks[websocket] = asyncio.create_task(  # 正经注释：启动专属发送任务 / 大白话注释：给这人配一个快递员
                self.start_sender(websocket))
        except Exception as e:  # 正经注释：捕获连接异常 / 大白话注释：握手出问题了
            print(f"Error connecting websocket: {e}")
            if websocket in self.active_connections:  # 正经注释：检查连接是否已部分注册 / 大白话注释：看看有没有部分登记了
                await self.disconnect(websocket)  # 正经注释：执行清理断开操作 / 大白话注释：赶紧清理掉

    async def disconnect(self, websocket: WebSocket):
        """
        断开并清理指定的 WebSocket 连接。

        【正经注释】
        按顺序执行清理操作：从活跃列表移除、取消发送任务、清理消息队列、
        最后关闭 WebSocket 连接。每一步都有独立的异常处理，
        确保即使某步失败也能继续后续清理。

        【大白话注释】
        客人走了，要做一系列清理工作：
        1. 从"在线名单"里删掉
        2. 把专属快递员辞了
        3. 把消息通道关了
        4. 把连接关掉
        每一步都可能出问题，但出了问题也要继续往下清理，不能半途而废。

        Args:
            websocket: 要断开的 WebSocket 连接对象
        """
        """Disconnect a websocket."""
        try:
            if websocket in self.active_connections:  # 正经注释：检查连接是否在活跃列表中 / 大白话注释：看看这人确实是在线的
                self.active_connections.remove(websocket)  # 正经注释：从活跃列表移除 / 大白话注释：从在线名单删掉

                # Cancel sender task if it exists
                if websocket in self.sender_tasks:  # 正经注释：检查是否有发送任务需要取消 / 大白话注释：看看有没有快递员在干活
                    try:
                        self.sender_tasks[websocket].cancel()  # 正经注释：取消发送任务 / 大白话注释：辞掉快递员
                        await self.message_queues[websocket].put(None)  # 正经注释：发送关闭信号 / 大白话注释：往通道里扔一个"下班"信号
                    except Exception as e:
                        logger.error(f"Error canceling sender task: {e}")
                    finally:
                        # Always try to clean up regardless of errors
                        if websocket in self.sender_tasks:  # 正经注释：确保删除发送任务引用 / 大白话注释：不管有没有出错，都把快递员的档案删了
                            del self.sender_tasks[websocket]

                # Clean up message queue
                if websocket in self.message_queues:  # 正经注释：检查是否有消息队列需要清理 / 大白话注释：看看有没有消息通道要关
                    del self.message_queues[websocket]  # 正经注释：删除消息队列 / 大白话注释：关掉消息通道

                # Finally close the WebSocket
                try:
                    await websocket.close()  # 正经注释：关闭 WebSocket 连接 / 大白话注释：把连接彻底关掉
                except Exception as e:
                    logger.info(f"WebSocket already closed: {e}")  # 正经注释：连接已关闭的情况 / 大白话注释：可能已经关了，没关系
        except Exception as e:  # 正经注释：捕获外层清理异常 / 大白话注释：清理过程本身出问题了
            logger.error(f"Error during WebSocket disconnection: {e}")
            # Still try to close the connection if possible
            try:
                await websocket.close()  # 正经注释：最后尝试关闭连接 / 大白话注释：再试一次关连接
            except Exception:
                pass  # If this fails too, there's nothing more we can do  # 正经注释：放弃处理 / 大白话注释：实在不行就算了

    async def start_streaming(self, task, report_type, report_source, source_urls, document_urls, tone, websocket, headers=None, query_domains=[], mcp_enabled=False, mcp_strategy="fast", mcp_configs=[], max_search_results=None):
        """
        启动流式研究过程。

        【正经注释】
        解析语气枚举值，获取配置文件路径，然后调用 run_agent 函数启动研究任务。
        所有参数将透传给底层的研究执行函数。

        【大白话注释】
        这个函数就是个"传话筒"：把研究参数整理好（比如把语气从字符串转成枚举），
        然后交给 run_agent 去真正执行研究。

        Args:
            task: 研究任务描述
            report_type: 报告类型
            report_source: 报告来源类型
            source_urls: 来源 URL 列表
            document_urls: 文档 URL 列表
            tone: 报告语气（字符串形式）
            websocket: WebSocket 连接
            headers: HTTP 请求头
            query_domains: 查询限定域名
            mcp_enabled: 是否启用 MCP
            mcp_strategy: MCP 策略
            mcp_configs: MCP 配置列表
            max_search_results: 最大搜索结果数

        Returns:
            研究报告文本
        """
        """Start streaming the output."""
        tone = Tone[tone]  # 正经注释：将语气字符串转换为 Tone 枚举值 / 大白话注释：把"Objective"这种字符串变成枚举
        # add customized JSON config file path here
        config_path = os.environ.get("CONFIG_PATH", "default")  # 正经注释：获取自定义配置文件路径 / 大白话注释：看看有没有指定的配置文件

        # Pass MCP parameters to run_agent
        report = await run_agent(  # 正经注释：调用研究执行函数 / 大白话注释：让研究引擎开始干活
            task, report_type, report_source, source_urls, document_urls, tone, websocket,
            headers=headers, query_domains=query_domains, config_path=config_path,
            mcp_enabled=mcp_enabled, mcp_strategy=mcp_strategy, mcp_configs=mcp_configs,
            max_search_results=max_search_results
        )
        return report  # 正经注释：返回研究报告 / 大白话注释：把研究报告交出去

async def run_agent(task, report_type, report_source, source_urls, document_urls, tone: Tone, websocket, stream_output=stream_output, headers=None, query_domains=[], config_path="", return_researcher=False, mcp_enabled=False, mcp_strategy="fast", mcp_configs=[], max_search_results=None):
    """
    核心研究代理执行函数。

    【正经注释】
    根据报告类型（multi_agents / DetailedReport / BasicReport）初始化相应的研究器并执行研究。
    支持 MCP（Model Context Protocol）工具集成，通过 logs_handler 实现日志的实时推送和持久化。
    return_researcher 参数允许调用方获取底层 GPTResearcher 实例以访问更多研究元数据。

    【大白话注释】
    这是整个研究的"发动机"：根据你要什么类型的报告，选不同的研究引擎来干活。
    - 多代理模式：让一群 AI 协作完成研究
    - 详细报告模式：深入分析，子话题逐一研究
    - 基础报告模式：标准的研究报告
    它还会准备好日志处理器，实时记录研究过程并推送给前端。
    如果你说 return_researcher=True，它会把研究引擎本身也交给你，
    方便你查看更多细节（比如查了哪些网站、花了多少钱）。

    Args:
        task: 研究任务描述
        report_type: 报告类型字符串
        report_source: 报告来源
        source_urls: 指定来源 URL 列表
        document_urls: 指定文档 URL 列表
        tone: Tone 枚举值
        websocket: WebSocket 连接（可为 None）
        stream_output: 流式输出函数
        headers: HTTP 请求头
        query_domains: 查询限定域名列表
        config_path: 配置文件路径
        return_researcher: 是否返回研究器实例
        mcp_enabled: 是否启用 MCP
        mcp_strategy: MCP 策略
        mcp_configs: MCP 配置列表
        max_search_results: 最大搜索结果数

    Returns:
        str | tuple: 研究报告文本，或 (报告, 研究器实例) 元组
    """
    """Run the agent."""
    # Create logs handler for this research task
    logs_handler = CustomLogsHandler(websocket, task)  # 正经注释：为本次研究创建日志处理器 / 大白话注释：准备好"记事本"

    # Log MCP initialization. Retriever and strategy are configured per-request
    # inside GPTResearcher via mcp_configs/mcp_strategy params — no os.environ
    # mutation needed here (mutating os.environ would persist across requests and
    # affect unrelated sessions, see issue #1676).
    if mcp_enabled and mcp_configs:  # 正经注释：MCP 启用且有配置时记录初始化日志 / 大白话注释：如果开了 MCP 工具，就说一声
        print(f"🔧 MCP enabled with strategy '{mcp_strategy}' and {len(mcp_configs)} server(s)")
        await logs_handler.send_json({  # 正经注释：通过日志处理器发送 MCP 初始化信息 / 大白话注释：往"记事本"里记一下 MCP 的配置
            "type": "logs",
            "content": "mcp_init",
            "output": f"🔧 MCP enabled with strategy '{mcp_strategy}' and {len(mcp_configs)} server(s)"
        })

    # Initialize researcher based on report type
    if report_type == "multi_agents":  # 正经注释：多代理报告类型 / 大白话注释：一群 AI 一起干活
        report = await run_multi_agent_task(  # 正经注释：执行多代理研究任务 / 大白话注释：让多代理团队开始研究
            query=task,
            websocket=logs_handler,  # Use logs_handler instead of raw websocket
            stream_output=stream_output,
            tone=tone,
            headers=headers
        )
        report = report.get("report", "")  # 正经注释：从结果中提取报告文本 / 大白话注释：把报告内容拿出来

    elif report_type == ReportType.DetailedReport.value:  # 正经注释：详细报告类型 / 大白话注释：要一份详细的研究报告
        researcher = DetailedReport(  # 正经注释：初始化详细报告研究器 / 大白话注释：启动详细报告引擎
            query=task,
            query_domains=query_domains,
            report_type=report_type,
            report_source=report_source,
            source_urls=source_urls,
            document_urls=document_urls,
            tone=tone,
            config_path=config_path,
            websocket=logs_handler,  # Use logs_handler instead of raw websocket
            headers=headers,
            mcp_configs=mcp_configs if mcp_enabled else None,  # 正经注释：仅在启用 MCP 时传入配置 / 大白话注释：开了 MCP 才给它配置
            mcp_strategy=mcp_strategy if mcp_enabled else None,
            max_search_results=max_search_results,
        )
        report = await researcher.run()  # 正经注释：执行详细报告生成 / 大白话注释：让引擎跑起来

    else:  # 正经注释：基础报告类型（默认） / 大白话注释：普通的研究报告
        researcher = BasicReport(  # 正经注释：初始化基础报告研究器 / 大白话注释：启动基础报告引擎
            query=task,
            query_domains=query_domains,
            report_type=report_type,
            report_source=report_source,
            source_urls=source_urls,
            document_urls=document_urls,
            tone=tone,
            config_path=config_path,
            websocket=logs_handler,  # Use logs_handler instead of raw websocket
            headers=headers,
            mcp_configs=mcp_configs if mcp_enabled else None,
            mcp_strategy=mcp_strategy if mcp_enabled else None,
            max_search_results=max_search_results,
        )
        report = await researcher.run()  # 正经注释：执行基础报告生成 / 大白话注释：让引擎跑起来

    if report_type != "multi_agents" and return_researcher:  # 正经注释：非多代理模式且需要返回研究器实例 / 大白话注释：不是多代理模式，而且你还想拿到研究引擎本身
        return report, researcher.gpt_researcher  # 正经注释：返回报告和底层研究器实例 / 大白话注释：把报告和研究引擎一起交出去
    else:
        return report  # 正经注释：仅返回报告文本 / 大白话注释：只把报告交出去

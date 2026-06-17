"""
基础报告模块（basic_report）

【正经注释】
本模块实现了 BasicReport 类，提供最基础的报告生成功能。
该类封装了 GPTResearcher 的初始化与调用流程，支持查询域名过滤、
报告类型配置、WebSocket 实时通信、MCP（Model Context Protocol）扩展等特性。
通过该类可以快速执行一次完整的研究流程：研究 -> 写报告 -> 返回结果。

【大白话注释】
这个文件就是"基础版报告生成器"。它干的活很简单：你给它一个问题，它帮你研究完，
然后写一份报告扔回来。封装了 GPTResearcher，省得你自己去调一堆参数。
如果你只是想要一份普普通通的研究报告，用这个就对了。
"""

import hashlib  # 正经注释：提供 MD5 等哈希算法，用于生成唯一的研究 ID / 大白话注释：用来给每次研究生成一个独一无二的"身份证号"
import time  # 正经注释：提供时间相关功能，用于在研究 ID 中嵌入时间戳 / 大白话注释：拿当前时间，让研究 ID 带上时间信息
from fastapi import WebSocket  # 正经注释：导入 FastAPI 的 WebSocket 类，用于与前端建立实时双向通信 / 大白话注释：用来跟前端"打电话"，实时告诉前端研究进展
from typing import Any  # 正经注释：导入 Any 类型提示，用于表示可以是任意类型 / 大白话注释：类型标注用的，告诉 Python 这里啥类型都行

from gpt_researcher import GPTResearcher  # 正经注释：导入核心研究器类，是执行研究和生成报告的主要引擎 / 大白话注释：把"研究大脑"请过来，所有的研究活儿都是它干的


class BasicReport:
    """
    基础报告生成类

    【正经注释】
    封装了 GPTResearcher 的标准使用流程，提供统一的初始化接口。
    支持配置查询参数、报告类型、数据源、语气风格、WebSocket 实时推送、
    MCP 扩展协议等。调用 run() 方法即可执行完整的研究与报告生成流程。

    【大白话注释】
    这个类就是个"一键生成报告"的包装器。你把各种参数丢进来，它帮你把底层的
    GPTResearcher 配好，最后调一下 run() 就能拿到报告。不用你自己操心底层细节。
    """

    def __init__(
        self,
        query: str,  # 正经注释：用户的原始查询字符串 / 大白话注释：你想研究啥问题
        query_domains: list,  # 正经注释：限制搜索范围的域名列表 / 大白话注释：只在这些网站里搜，比如只搜 wikipedia.org
        report_type: str,  # 正经注释：报告类型标识，如 research_report / 大白话注释：报告的风格，是"研究型"还是"大纲型"之类的
        report_source: str,  # 正经注释：数据来源类型，如 web、local、hybrid / 大白话注释：从哪儿找资料——网上搜、本地文档、还是都来点
        source_urls,  # 正经注释：用户预设的参考 URL 列表 / 大白话注释：你已经知道的有用网址，直接塞进去
        document_urls,  # 正经注释：用户提供的本地文档路径列表 / 大白话注释：你本地的文档文件路径，让它也参考参考
        tone: Any,  # 正经注释：报告的写作语气，如 Objective（客观）、Informal（非正式） / 大白话注释：报告用啥语气写——正式的、随意的、还是学术的
        config_path: str,  # 正经注释：配置文件路径，用于自定义研究行为 / 大白话注释：配置文件在哪，可以改默认设置
        websocket: WebSocket,  # 正经注释：WebSocket 连接实例，用于向前端推送实时进度 / 大白话注释：跟前端通话的"电话线"，研究到哪一步了实时通知
        headers=None,  # 正经注释：自定义 HTTP 请求头 / 大白话注释：发网络请求时带的额外头部信息，一般用不上
        mcp_configs=None,  # 正经注释：MCP（Model Context Protocol）服务配置 / 大白话注释：MCP扩展配置，让 AI 能调用外部工具
        mcp_strategy=None,  # 正经注释：MCP 服务的调用策略 / 大白话注释：MCP工具怎么调、调哪个的策略
        max_search_results=None,  # 正经注释：每次搜索的最大结果数量限制 / 大白话注释：每次搜索最多返回多少条结果，别太多了看不过来
    ):
        self.query = query  # 正经注释：保存用户查询字符串为实例属性 / 大白话注释：记住用户问了啥
        self.query_domains = query_domains  # 正经注释：保存域名过滤列表 / 大白话注释：记住只搜哪些网站
        self.report_type = report_type  # 正经注释：保存报告类型 / 大白话注释：记住要生成啥类型的报告
        self.report_source = report_source  # 正经注释：保存数据来源配置 / 大白话注释：记住资料从哪儿来
        self.source_urls = source_urls  # 正经注释：保存预设 URL 列表 / 大白话注释：记住用户给的网址
        self.document_urls = document_urls  # 正经注释：保存文档路径列表 / 大白话注释：记住本地文档在哪
        self.tone = tone  # 正经注释：保存报告语气设置 / 大白话注释：记住用啥语气写
        self.config_path = config_path  # 正经注释：保存配置文件路径 / 大白话注释：记住配置文件位置
        self.websocket = websocket  # 正经注释：保存 WebSocket 连接 / 大白话注释：记住跟前端的"电话线"
        self.headers = headers or {}  # 正经注释：保存请求头，默认为空字典 / 大白话注释：请求头没给就默认空的

        # Generate a unique research ID for this report
        self.research_id = self._generate_research_id(query)  # 正经注释：基于查询内容和时间戳生成唯一研究标识 / 大白话注释：给这次研究起个唯一编号，方便追踪

        # Initialize researcher with optional MCP parameters
        gpt_researcher_params = {  # 正经注释：构建传入 GPTResearcher 的参数字典 / 大白话注释：把所有参数打包，准备传给"研究大脑"
            "query": self.query,  # 正经注释：传入查询字符串 / 大白话注释：把问题传过去
            "query_domains": self.query_domains,  # 正经注释：传入域名过滤 / 大白话注释：把网站限制传过去
            "report_type": self.report_type,  # 正经注释：传入报告类型 / 大白话注释：把报告风格传过去
            "report_source": self.report_source,  # 正经注释：传入数据来源 / 大白话注释：把资料来源传过去
            "source_urls": self.source_urls,  # 正经注释：传入预设 URL / 大白话注释：把已有网址传过去
            "document_urls": self.document_urls,  # 正经注释：传入文档路径 / 大白话注释：把本地文档传过去
            "tone": self.tone,  # 正经注释：传入语气设置 / 大白话注释：把语气要求传过去
            "config_path": self.config_path,  # 正经注释：传入配置路径 / 大白话注释：把配置文件位置传过去
            "websocket": self.websocket,  # 正经注释：传入 WebSocket 连接 / 大白话注释：把"电话线"接上
            "headers": self.headers,  # 正经注释：传入请求头 / 大白话注释：把额外请求信息传过去
        }

        # Add MCP parameters if provided
        if mcp_configs is not None:  # 正经注释：如果提供了 MCP 配置则添加到参数中 / 大白话注释：如果有 MCP 工具配置就带上
            gpt_researcher_params["mcp_configs"] = mcp_configs
        if mcp_strategy is not None:  # 正经注释：如果提供了 MCP 策略则添加到参数中 / 大白话注释：如果有 MCP 调用策略也带上
            gpt_researcher_params["mcp_strategy"] = mcp_strategy

        self.gpt_researcher = GPTResearcher(**gpt_researcher_params)  # 正经注释：使用参数字典初始化 GPTResearcher 实例 / 大白话注释：把打包好的参数丢给"研究大脑"，让它准备开工

        # Override max_search_results_per_query if provided by user
        if max_search_results is not None:  # 正经注释：如果用户指定了最大搜索结果数，覆盖默认配置 / 大白话注释：用户说了搜多少条就搜多少条，别用默认值
            self.gpt_researcher.cfg.max_search_results_per_query = int(max_search_results)

    def _generate_research_id(self, query: str) -> str:
        """
        生成唯一研究标识

        【正经注释】
        基于当前时间戳和查询字符串的 MD5 哈希前 8 位，组合生成唯一的研究 ID。
        格式为 research_{timestamp}_{hash}，确保不同时间和不同查询产生不同 ID。

        【大白话注释】
        给每次研究搞一个"身份证号"。用当前时间 + 查询内容的哈希值拼起来，
        保证每次研究的编号都不一样，不会搞混。

        Args:
            query: 用户查询字符串
        Returns:
            格式为 research_{时间戳}_{哈希} 的唯一 ID
        """
        timestamp = str(int(time.time()))  # 正经注释：获取当前时间戳并转为整数字符串 / 大白话注释：拿到现在的秒级时间戳
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]  # 正经注释：对查询字符串取 MD5 哈希，截取前 8 位作为短标识 / 大白话注释：把问题变成一串短代码，方便辨认
        return f"research_{timestamp}_{query_hash}"  # 正经注释：拼接时间戳和哈希值生成最终研究 ID / 大白话注释：把时间戳和短代码拼在一起，就是独一无二的编号了

    async def run(self):
        """
        执行研究与报告生成

        【正经注释】
        异步方法，按顺序执行两个核心步骤：
        1. 调用 conduct_research() 进行信息检索与上下文构建
        2. 调用 write_report() 基于研究结果生成最终报告
        最终返回完整的 Markdown 格式报告文本。

        【大白话注释】
        一键启动按钮！先让"研究大脑"去网上搜资料、整理信息，
        然后让它根据搜到的信息写一份报告，最后把报告交给你。

        Returns:
            str: 完整的研究报告文本（Markdown 格式）
        """
        await self.gpt_researcher.conduct_research()  # 正经注释：执行研究阶段，包括查询规划、信息检索与上下文聚合 / 大白话注释：让"研究大脑"去搜资料、整理信息
        report = await self.gpt_researcher.write_report()  # 正经注释：基于研究结果生成结构化的 Markdown 报告 / 大白话注释：让"研究大脑"把搜到的信息写成报告
        return report  # 正经注释：返回生成的报告文本 / 大白话注释：把写好的报告交出去

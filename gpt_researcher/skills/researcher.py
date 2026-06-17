"""研究执行器技能模块（Research Conductor Skill）
【正经注释】
本模块提供 ResearchConductor 类，负责管理和协调研究的核心执行流程，
包括查询规划（Query Planning）、网络搜索（Web Searching）、MCP 检索器管理
以及从多种来源（Web/本地/向量库/MCP）收集研究上下文。

【大白话注释】
这个文件就是 GPT Researcher 的"搜索员"——负责实际的调研工作：
- 把你的大问题拆成几个小问题
- 拿着小问题去各个搜索引擎搜资料
- 把搜到的网页内容抓回来、整理好
- 交给"写手"去写报告

核心方法 conduct_research() 是整个研究流程的起点。
"""
import asyncio												# 正经注释：异步 I/O 库，用于并发搜索多个子查询 / 大白话注释：让搜索员能同时干好几件事
import logging												# 正经注释：日志记录库 / 大白话注释：记工作日志
import os													# 正经注释：操作系统接口，用于读取环境变量 / 大白话注释：读系统配置
import random												# 正经注释：随机数库，用于打乱搜索 URL 顺序避免偏倚 / 大白话注释：抽签决定先搜哪个网页

from ..actions.agent_creator import choose_agent			# 正经注释：代理选择器，根据查询自动匹配合适的研究角色 / 大白话注释：自动选"谁来研究"
from ..actions.query_processing import get_search_results, plan_research_outline	# 正经注释：搜索执行和查询规划函数 / 大白话注释：搜资料 + 把大问题拆小
from ..actions.utils import stream_output					# 正经注释：WebSocket 实时输出工具 / 大白话注释：实时推送"正在搜xxx"的进度
from ..document import DocumentLoader, LangChainDocumentLoader, OnlineDocumentLoader	# 正经注释：文档加载器，支持本地/在线/LangChain 文档 / 大白话注释：从不同地方读取文件资料
from ..utils.enum import ReportSource, ReportType			# 正经注释：报告来源和类型的枚举定义 / 大白话注释：报告从哪找资料、什么格式的常量
from ..utils.logging_config import get_json_handler			# 正经注释：JSON 日志处理器工厂 / 大白话注释：一种特殊日志，输出 JSON 格式


class ResearchConductor:
    """研究执行器类（Research Conductor）
    【正经注释】
    管理和协调完整的研究流程，核心职责包括：
    - 查询规划：将原始查询分解为多个子查询
    - 网络搜索：通过多个检索器并行执行搜索
    - MCP 检索管理：智能缓存和复用 MCP 外部工具的结果
    - 上下文收集：从 Web、本地文档、向量库等多种来源聚合研究素材

    【大白话注释】
    这个类就是"搜索员"，负责整个调研的执行过程：
    - 把你的问题拆成几个小问题去搜
    - 同时用多个搜索引擎搜资料
    - 如果有外部工具（MCP），也会用上
    - 把搜到的东西整理好交给下一步

    Attributes:
        researcher: 持有对父级 GPTResearcher 实例的引用（大白话：能访问"总指挥"的所有信息）
        logger: 研究事件的日志记录器（大白话：记日志的笔）
        json_handler: JSON 格式日志处理器（大白话：另一种日志格式）
    """

    def __init__(self, researcher):
        """初始化研究执行器
        【正经注释】绑定父级 GPTResearcher 实例引用，初始化日志和 MCP 缓存。
        【大白话注释】告诉搜索员"你是给谁干活的"，并准备好记事本和缓存。
        Args:
            researcher: 父级 GPTResearcher 实例（大白话：你的"老板"）
        """
        self.researcher = researcher						# 正经注释：持有对父级 GPTResearcher 的引用，可访问配置、上下文等共享状态 / 大白话注释：记住"老板"是谁
        self.logger = logging.getLogger('research')			# 正经注释：创建以 'research' 为名的日志记录器 / 大白话注释：准备一个叫"研究"的记事本
        self.json_handler = get_json_handler()				# 正经注释：获取 JSON 格式的日志处理器实例 / 大白话注释：另一种格式的日志工具
        self._mcp_results_cache = None						# 正经注释：MCP 结果缓存，避免对同一查询重复调用外部工具 / 大白话注释：搜过的结果先存着，别重复搜
        self._mcp_query_count = 0							# 正经注释：MCP 查询计数器，用于平衡模式下的使用量追踪 / 大白话注释：记录用了几次外部工具

    async def plan_research(self, query, query_domains=None):
        """规划研究策略——将原始查询分解为子查询
        【正经注释】
        先用主查询进行初始搜索获取背景信息，再将搜索结果传给 LLM 规划出
        多个有针对性的子查询。子查询用于后续并行搜索以提高覆盖面。
        【大白话注释】
        先用你的问题"随便搜一下"了解个大概，然后让 AI 根据搜索结果
        把大问题拆成几个更具体的小问题，后面分别去搜。
        Args:
            query: 原始查询（大白话：你问的大问题）
            query_domains: 限制搜索的域名列表（大白话：只在特定网站上搜）
        Returns:
            List[str]: 子查询列表（大白话：拆出来的小问题清单）
        """
        await stream_output(									# 正经注释：通过 WebSocket 推送"正在规划研究"的进度 / 大白话注释：告诉前端"我在想怎么搜"
            "logs",
            "planning_research",
            f"🌐 Browsing the web to learn more about the task: {query}...",
            self.researcher.websocket,
        )

        search_results = await get_search_results(query, self.researcher.retrievers[0], query_domains, researcher=self.researcher)	# 正经注释：用第一个检索器执行初始搜索，获取背景信息 / 大白话注释：先拿主搜索引擎搜一下，看看有啥
        self.logger.info(f"Initial search results obtained: {len(search_results)} results")	# 正经注释：记录初始搜索结果数量 / 大白话注释：日志——搜到了几条结果

        await stream_output(									# 正经注释：推送"正在规划策略"状态 / 大白话注释：告诉前端"我在拆分问题"
            "logs",
            "planning_research",
            f"🤔 Planning the research strategy and subtasks...",
            self.researcher.websocket,
        )

        retriever_names = [r.__name__ for r in self.researcher.retrievers]	# 正经注释：收集所有检索器的名称，传递给规划器用于 MCP 优化 / 大白话注释：把搜索引擎的名字列出来

        outline = await plan_research_outline(				# 正经注释：调用 LLM 基于搜索结果生成研究大纲（子查询列表） / 大白话注释：让 AI 看着搜索结果，把大问题拆成小问题
            query=query,
            search_results=search_results,
            agent_role_prompt=self.researcher.role,
            cfg=self.researcher.cfg,
            parent_query=self.researcher.parent_query,
            report_type=self.researcher.report_type,
            cost_callback=self.researcher.add_costs,
            retriever_names=retriever_names,
            **self.researcher.kwargs
        )
        self.logger.info(f"Research outline planned: {outline}")	# 正经注释：记录生成的研究大纲 / 大白话注释：日志——拆出来的小问题列表
        return outline										# 正经注释：返回子查询列表 / 大白话注释：把小问题清单交出去

    async def conduct_research(self):
        """执行完整的研究流程
        【正经注释】
        根据报告来源（report_source）选择不同的研究策略：
        - source_urls: 直接从指定 URL 抓取内容
        - Web: 通过网络搜索引擎搜索
        - Local: 从本地文档加载
        - Hybrid: 同时搜索本地文档和网络
        - Azure: 从 Azure 存储加载文档
        - LangChainDocuments: 从 LangChain 文档对象加载
        - LangChainVectorStore: 从向量数据库检索
        研究完成后可选择对来源进行精选（curate）。
        【大白话注释】
        这是"开始干活"的主入口！根据配置决定从哪找资料：
        - 你给了网址？→ 直接抓那些网页
        - 网络模式？→ 上网搜
        - 本地模式？→ 读你电脑上的文件
        - 混合模式？→ 文件和网络都搜
        最后还能让"评审"挑一挑，只留最好的资料。
        Returns:
            研究上下文数据（大白话：搜集到的所有素材）
        """
        if self.json_handler:								# 正经注释：将查询记录到 JSON 日志 / 大白话注释：在日志里记下要研究什么
            self.json_handler.update_content("query", self.researcher.query)

        self.logger.info(f"Starting research for query: {self.researcher.query}")	# 正经注释：记录研究开始事件 / 大白话注释：日志——开始研究啦

        retriever_names = [r.__name__ for r in self.researcher.retrievers]	# 正经注释：收集并记录活跃的检索器名称 / 大白话注释：看看配了哪些搜索引擎
        self.logger.info(f"Active retrievers: {retriever_names}")	# 正经注释：记录活跃检索器信息 / 大白话注释：日志——搜索引擎清单

        self.researcher.visited_urls.clear()				# 正经注释：清空已访问 URL 集合，确保每次研究从零开始 / 大白话注释：把"看过的网页"清空，重新来
        research_data = []									# 正经注释：初始化研究数据容器 / 大白话注释：准备一个空篮子装资料

        if self.researcher.verbose:							# 正经注释：详细模式下推送研究启动信息 / 大白话注释：如果开了"字幕"就告诉用户开始了
            await stream_output(
                "logs",
                "starting_research",
                f"🔍 Starting the research task for '{self.researcher.query}'...",
                self.researcher.websocket,
            )
            await stream_output(								# 正经注释：推送当前代理类型 / 大白话注释：告诉用户用的什么"研究员"
                "logs",
                "agent_generated",
                self.researcher.agent,
                self.researcher.websocket
            )

        if not (self.researcher.agent and self.researcher.role):	# 正经注释：如果未预设代理和角色，自动选择 / 大白话注释：没指定"谁来做"就让 AI 选一个
            self.researcher.agent, self.researcher.role = await choose_agent(
                query=self.researcher.query,
                cfg=self.researcher.cfg,
                parent_query=self.researcher.parent_query,
                cost_callback=self.researcher.add_costs,
                headers=self.researcher.headers,
                prompt_family=self.researcher.prompt_family
            )

        has_mcp_retriever = any("mcpretriever" in r.__name__.lower() for r in self.researcher.retrievers)	# 正经注释：检查是否配置了 MCP 检索器 / 大白话注释：看看有没有外部工具
        if has_mcp_retriever:								# 正经注释：记录 MCP 检索器状态 / 大白话注释：日志——有外部工具可用
            self.logger.info("MCP retrievers configured and will be used with standard research flow")

        if self.researcher.source_urls:						# 正经注释：分支1 - 从指定 URL 直接抓取 / 大白话注释：如果你给了网址，就直接抓那些网页
            self.logger.info("Using provided source URLs")
            research_data = await self._get_context_by_urls(self.researcher.source_urls)	# 正经注释：抓取指定 URL 的内容 / 大白话注释：去抓你指定的网页
            if research_data and len(research_data) == 0 and self.researcher.verbose:	# 正经注释：指定 URL 无内容时的提示 / 大白话注释：给的网址没找到东西
                await stream_output(
                    "logs",
                    "answering_from_memory",
                    f"🧐 I was unable to find relevant context in the provided sources...",
                    self.researcher.websocket,
                )
            if self.researcher.complement_source_urls:		# 正经注释：是否用网络搜索补充指定 URL 的不足 / 大白话注释：给的网址不够，再上网搜搜补充
                self.logger.info("Complementing with web search")
                additional_research = await self._get_context_by_web_search(self.researcher.query, [], self.researcher.query_domains)
                research_data += ' '.join(additional_research)	# 正经注释：将补充内容拼接到已有数据 / 大白话注释：把补充搜到的加到篮子里
        elif self.researcher.report_source == ReportSource.Web.value:	# 正经注释：分支2 - Web 搜索模式 / 大白话注释：上网搜资料
            self.logger.info("Using web search with all configured retrievers")
            research_data = await self._get_context_by_web_search(self.researcher.query, [], self.researcher.query_domains)
        elif self.researcher.report_source == ReportSource.Local.value:	# 正经注释：分支3 - 本地文档模式 / 大白话注释：从电脑上的文件里找资料
            self.logger.info("Using local search")
            document_data = await DocumentLoader(self.researcher.cfg.doc_path).load()	# 正经注释：从配置的文档路径加载本地文件 / 大白话注释：读取指定文件夹里的文档
            self.logger.info(f"Loaded {len(document_data)} documents")
            if self.researcher.vector_store:				# 正经注释：将文档加载到向量数据库以支持语义搜索 / 大白话注释：把文件内容存到"智能搜索库"
                self.researcher.vector_store.load(document_data)

            research_data = await self._get_context_by_web_search(self.researcher.query, document_data, self.researcher.query_domains)
        elif self.researcher.report_source == ReportSource.Hybrid.value:	# 正经注释：分支4 - 混合模式（本地+网络） / 大白话注释：文件和网络都搜
            if self.researcher.document_urls:				# 正经注释：优先从在线 URL 加载文档 / 大白话注释：如果给了在线文档链接就从网上下
                document_data = await OnlineDocumentLoader(self.researcher.document_urls).load()
            else:
                document_data = await DocumentLoader(self.researcher.cfg.doc_path).load()	# 正经注释：否则从本地路径加载 / 大白话注释：没给链接就读本地的
            if self.researcher.vector_store:				# 正经注释：加载到向量库 / 大白话注释：存到"智能搜索库"
                self.researcher.vector_store.load(document_data)
            docs_context = await self._get_context_by_web_search(self.researcher.query, document_data, self.researcher.query_domains)	# 正经注释：基于文档的上下文搜索 / 大白话注释：在文档里搜相关内容
            web_context = await self._get_context_by_web_search(self.researcher.query, [], self.researcher.query_domains)	# 正经注释：纯网络搜索的上下文 / 大白话注释：在网上搜相关内容
            research_data = self.researcher.prompt_family.join_local_web_documents(docs_context, web_context)	# 正经注释：合并本地和网络上下文 / 大白话注释：把文件和网络搜到的合并
        elif self.researcher.report_source == ReportSource.Azure.value:	# 正经注释：分支5 - Azure 云存储模式 / 大白话注释：从微软云盘上找资料
            from ..document.azure_document_loader import AzureDocumentLoader	# 正经注释：延迟导入 Azure 文档加载器 / 大白话注释：用到时才导入，省内存
            azure_loader = AzureDocumentLoader(
                container_name=os.getenv("AZURE_CONTAINER_NAME"),	# 正经注释：Azure 存储容器名称 / 大白话注释：云盘上的"文件夹名"
                connection_string=os.getenv("AZURE_CONNECTION_STRING")	# 正经注释：Azure 连接字符串 / 大白话注释：连接云盘的"钥匙"
            )
            azure_files = await azure_loader.load()			# 正经注释：从 Azure 加载文件列表 / 大白话注释：从云盘下载文件
            document_data = await DocumentLoader(azure_files).load()  # Reuse existing loader	# 正经注释：复用现有文档加载器处理文件 / 大白话注释：用同一个工具处理下载的文件
            research_data = await self._get_context_by_web_search(self.researcher.query, document_data)

        elif self.researcher.report_source == ReportSource.LangChainDocuments.value:	# 正经注释：分支6 - LangChain 文档模式 / 大白话注释：直接用传进来的 LangChain 文档
            langchain_documents_data = await LangChainDocumentLoader(	# 正经注释：通过 LangChain 文档加载器处理 / 大白话注释：把 LangChain 格式的文档转成统一格式
                self.researcher.documents
            ).load()
            if self.researcher.vector_store:				# 正经注释：加载到向量库 / 大白话注释：存到"智能搜索库"
                self.researcher.vector_store.load(langchain_documents_data)
            research_data = await self._get_context_by_web_search(
                self.researcher.query, langchain_documents_data, self.researcher.query_domains
            )
        elif self.researcher.report_source == ReportSource.LangChainVectorStore.value:	# 正经注释：分支7 - 向量库检索模式 / 大白话注释：从向量数据库里搜
            research_data = await self._get_context_by_vectorstore(self.researcher.query, self.researcher.vector_store_filter)

        # Rank and curate the sources						# 正经注释：来源排序和精选阶段 / 大白话注释：挑一挑，只留最好的资料
        self.researcher.context = research_data				# 正经注释：将原始研究数据赋值给上下文 / 大白话注释：先全存起来
        if self.researcher.cfg.curate_sources:				# 正经注释：如果配置了来源精选，调用 SourceCurator 筛选 / 大白话注释：开了"精选"就让评审挑好的
            self.logger.info("Curating sources")
            self.researcher.context = await self.researcher.source_curator.curate_sources(research_data)

        if self.researcher.verbose:							# 正经注释：详细模式下推送研究完成和费用信息 / 大白话注释：开了"字幕"就告诉用户搞定了
            await stream_output(
                "logs",
                "research_step_finalized",
                f"Finalized research step.\n💸 Total Research Costs: ${self.researcher.get_costs()}",
                self.researcher.websocket,
            )
            if self.json_handler:							# 正经注释：更新 JSON 日志中的费用和上下文 / 大白话注释：在 JSON 日志里也记一笔
                self.json_handler.update_content("costs", self.researcher.get_costs())
                self.json_handler.update_content("context", self.researcher.context)

        self.logger.info(f"Research completed. Context size: {len(str(self.researcher.context))}")	# 正经注释：记录研究完成和上下文大小 / 大白话注释：日志——研究搞定，素材有多大
        return self.researcher.context						# 正经注释：返回最终的研究上下文 / 大白话注释：把素材交出去

    async def _get_context_by_urls(self, urls):
        """从指定 URL 列表抓取并压缩上下文
        【正经注释】过滤已访问的 URL，抓取新页面内容，可选存入向量库，最后通过语义搜索提取相关内容。
        【大白话注释】去指定的几个网页抓内容，先去掉已经看过的，抓回来后整理出跟问题相关的部分。
        Args:
            urls: URL 列表（大白话：指定的网页链接列表）
        Returns:
            上下文内容（大白话：整理好的素材）
        """
        self.logger.info(f"Getting context from URLs: {urls}")	# 正经注释：记录开始处理 URL / 大白话注释：日志——开始抓这些网页

        new_search_urls = await self._get_new_urls(urls)	# 正经注释：过滤出未访问过的新 URL / 大白话注释：去掉已经看过的网页
        self.logger.info(f"New URLs to process: {new_search_urls}")	# 正经注释：记录新 URL 数量 / 大白话注释：日志——要抓几个新网页

        scraped_content = await self.researcher.scraper_manager.browse_urls(new_search_urls)	# 正经注释：通过浏览器管理器抓取页面内容 / 大白话注释：让爬虫去抓网页内容
        self.logger.info(f"Scraped content from {len(scraped_content)} URLs")	# 正经注释：记录抓取结果数量 / 大白话注释：日志——抓到了几个网页

        if self.researcher.vector_store:					# 正经注释：将抓取内容加载到向量库以支持语义搜索 / 大白话注释：存到"智能搜索库"
            self.researcher.vector_store.load(scraped_content)

        context = await self.researcher.context_manager.get_similar_content_by_query(	# 正经注释：通过语义搜索提取与查询相关的内容 / 大白话注释：从抓到的内容里挑跟问题相关的
            self.researcher.query, scraped_content
        )
        return context										# 正经注释：返回提取的相关上下文 / 大白话注释：把挑好的素材交出去

    # Add logging to other methods similarly...				# 正经注释：TODO - 其他方法也需要添加类似日志 / 大白话注释：待办——给其他方法也加上日志

    async def _get_context_by_vectorstore(self, query, filter: dict | None = None):
        """从向量数据库检索上下文
        【正经注释】规划子查询后，对每个子查询在向量库中进行语义检索，
        最后通过 asyncio.gather 并行执行所有子查询以提高效率。
        如果不是子课题报告，会将原始查询也加入搜索列表。
        【大白话注释】从"智能搜索库"里找资料：
        1. 把大问题拆成小问题
        2. 每个小问题都去库里搜一下
        3. 所有搜索同时进行，不用排队等
        Args:
            query: 搜索查询（大白话：要搜什么）
            filter: 向量库过滤条件（大白话：加什么筛选条件）
        Returns:
            context: 上下文列表（大白话：搜到的素材列表）
        """
        self.logger.info(f"Starting vectorstore search for query: {query}")	# 正经注释：记录向量库搜索开始 / 大白话注释：日志——开始在向量库里搜
        context = []										# 正经注释：初始化上下文容器 / 大白话注释：准备空篮子
        sub_queries = await self.plan_research(query)		# 正经注释：规划子查询列表 / 大白话注释：把大问题拆成小的
        if self.researcher.report_type != "subtopic_report":	# 正经注释：非子课题报告时，将原始查询加入搜索以确保覆盖 / 大白话注释：不是子课题的话，把原问题也加上
            sub_queries.append(query)

        if self.researcher.verbose:							# 正经注释：详细模式下推送子查询列表 / 大白话注释：开了"字幕"就告诉用户拆了哪些小问题
            await stream_output(
                "logs",
                "subqueries",
                f"🗂️  I will conduct my research based on the following queries: {sub_queries}...",
                self.researcher.websocket,
                True,
                sub_queries,
            )

        context = await asyncio.gather(						# 正经注释：并行执行所有子查询的向量库搜索 / 大白话注释：同时搜所有小问题，不用一个一个等
            *[
                self._process_sub_query_with_vectorstore(sub_query, filter)
                for sub_query in sub_queries
            ]
        )
        return context										# 正经注释：返回所有子查询的结果 / 大白话注释：把搜到的全部交出去

    async def _get_context_by_web_search(self, query, scraped_data: list | None = None, query_domains: list | None = None):
        """通过网络搜索获取上下文（核心方法）
        【正经注释】
        网络搜索的核心执行方法，流程为：
        1. 根据 MCP 策略预处理外部工具结果（fast/deep/disabled）
        2. 规划子查询列表
        3. 并行执行所有子查询的搜索和内容提取
        4. 合并所有子查询的上下文
        MCP 策略说明：
        - fast: 用原始查询执行一次 MCP，后续子查询复用缓存（默认）
        - deep: 每个子查询都单独执行 MCP（更全面但更慢）
        - disabled: 完全跳过 MCP
        【大白话注释】
        这是"上网搜资料"的核心方法：
        1. 如果有外部工具（MCP），先决定怎么用它（快速/深度/关闭）
        2. 把大问题拆成小问题
        3. 同时搜所有小问题
        4. 把搜到的东西合在一起
        Args:
            query: 搜索查询（大白话：要搜什么）
            scraped_data: 已有的抓取数据（大白话：之前已经抓过的资料） 有现成资料的（Local/Hybrid/Azure/LangChain）
            query_domains: 限制搜索的域名（大白话：只在特定网站搜）
        Returns:
            context: 上下文列表（大白话：搜到的素材）
        """
        self.logger.info(f"Starting web search for query: {query}")	# 正经注释：记录网络搜索开始 / 大白话注释：日志——开始上网搜

        if scraped_data is None:								# 正经注释：默认参数初始化 / 大白话注释：没传已有资料就设为空
            scraped_data = []
        if query_domains is None:
            query_domains = []

        mcp_retrievers = [r for r in self.researcher.retrievers if "mcpretriever" in r.__name__.lower()]	# 正经注释：从检索器列表中筛选出 MCP 类型的检索器 / 大白话注释：把外部工具挑出来

        mcp_strategy = self._get_mcp_strategy()				# 正经注释：获取 MCP 执行策略配置 / 大白话注释：看看外部工具用哪种模式

        if mcp_retrievers and self._mcp_results_cache is None:	# 正经注释：有 MCP 检索器且缓存为空时，执行首次 MCP 搜索 / 大白话注释：有外部工具但还没搜过，就先搜一次
            if mcp_strategy == "disabled":						# 正经注释：策略1 - 禁用 MCP / 大白话注释：关闭外部工具
                self.logger.info("MCP disabled by strategy, skipping MCP research")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_disabled",
                        f"⚡ MCP research disabled by configuration",
                        self.researcher.websocket,
                    )
            elif mcp_strategy == "fast":						# 正经注释：策略2 - 快速模式，仅用原始查询执行一次 / 大白话注释：快速模式——只搜一次就缓存
                self.logger.info("MCP fast strategy: Running once with original query")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_optimization",
                        f"🚀 MCP Fast: Running once for main query (performance mode)",
                        self.researcher.websocket,
                    )

                mcp_context = await self._execute_mcp_research_for_queries([query], mcp_retrievers)	# 正经注释：用原始查询执行一次 MCP 搜索 / 大白话注释：拿你的问题去问一次外部工具
                self._mcp_results_cache = mcp_context		# 正经注释：缓存结果供后续子查询复用 / 大白话注释：搜到的结果存起来，后面直接用
                self.logger.info(f"MCP results cached: {len(mcp_context)} total context entries")
            elif mcp_strategy == "deep":						# 正经注释：策略3 - 深度模式，每个子查询单独执行 MCP / 大白话注释：深度模式——每个小问题都问一次外部工具
                self.logger.info("MCP deep strategy: Will run for all queries")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_comprehensive",
                        f"🔍 MCP Deep: Will run for each sub-query (thorough mode)",
                        self.researcher.websocket,
                    )
                # Don't cache - let each sub-query run MCP individually	# 正经注释：不缓存，让每个子查询独立运行 MCP / 大白话注释：不存缓存，每个小问题都要重新搜
            else:												# 正经注释：未知策略回退到快速模式 / 大白话注释：不认识的策略就当快速处理
                self.logger.warning(f"Unknown MCP strategy '{mcp_strategy}', defaulting to fast")
                mcp_context = await self._execute_mcp_research_for_queries([query], mcp_retrievers)
                self._mcp_results_cache = mcp_context
                self.logger.info(f"MCP results cached: {len(mcp_context)} total context entries")

        sub_queries = await self.plan_research(query, query_domains)	#：把大问题拆成小问题  例如['Python JavaScript 2025 开发者趋势报告 Octoverse TIOBE', '2025年 Python AI数据科学与 JavaScript Web开发 趋势对比', 'Python FastAPI 异步编程 与 TypeScript 2025 生态发展对比']
        self.logger.info(f"Generated sub-queries: {sub_queries}")	# 正经注释：记录生成的子查询 / 大白话注释：日志——拆了哪些小问题

        if self.researcher.report_type != "subtopic_report":	# 正经注释：非子课题报告时追加原始查询 / 大白话注释：不是子课题就把原问题也加上
            sub_queries.append(query)

        if self.researcher.verbose:								# 正经注释：详细模式下推送子查询信息 / 大白话注释：开了"字幕"就告诉用户
            await stream_output(
                "logs",
                "subqueries",
                f"🗂️ I will conduct my research based on the following queries: {sub_queries}...",
                self.researcher.websocket,
                True,
                sub_queries,
            )

        try:													# 正经注释：并行执行所有子查询，并合并结果 / 大白话注释：同时搜所有小问题
            context = await asyncio.gather(						# 正经注释：asyncio.gather 并行执行所有子查询处理 / 大白话注释：同时搜，不用排队
                *[
                    self._process_sub_query(sub_query, scraped_data, query_domains)
                    for sub_query in sub_queries
                ],return_exceptions=True
            )
            self.logger.info(f"Gathered context from {len(context)} sub-queries")	# 正经注释：记录收集到的子查询结果数 / 大白话注释：日志——几个小问题搜到了
            context = [c for c in context if c]					# 正经注释：过滤掉空结果 / 大白话注释：去掉没搜到东西的
            if context:
                combined_context = " ".join(context)				# 正经注释：将所有非空结果拼接为完整上下文 / 大白话注释：把搜到的拼在一起
                self.logger.info(f"Combined context size: {len(combined_context)}")	# 正经注释：记录合并后的上下文大小 / 大白话注释：日志——素材总共多大
                return combined_context							# 正经注释：返回合并后的上下文 / 大白话注释：把拼好的素材交出去
            return []											# 正经注释：所有子查询都无结果时返回空列表 / 大白话注释：啥也没搜到
        except Exception as e:									# 正经注释：异常处理，确保单个查询失败不影响整体流程 / 大白话注释：出错了也不崩溃，记个日志就行
            self.logger.error(f"Error during web search: {e}", exc_info=True)
            return []

    def _get_mcp_strategy(self) -> str:
        """获取 MCP 执行策略配置
        【正经注释】按优先级获取策略：实例级设置 > 配置文件设置 > 默认值 "fast"。
        【大白话注释】看看外部工具用哪种模式，按这个顺序找：
        1. 代码里直接设的（最优先）
        2. 配置文件里的
        3. 都没有就用"快速模式"
        Returns:
            str: MCP 策略名称（大白话："disabled"/"fast"/"deep"）
        """
        if hasattr(self.researcher, 'mcp_strategy') and self.researcher.mcp_strategy is not None:	# 正经注释：优先级1 - 实例级设置 / 大白话注释：先看代码里有没有直接设
            return self.researcher.mcp_strategy

        if hasattr(self.researcher.cfg, 'mcp_strategy'):		# 正经注释：优先级2 - 配置文件设置 / 大白话注释：再看配置文件里有没有
            return self.researcher.cfg.mcp_strategy

        return "fast"											# 正经注释：优先级3 - 默认使用快速模式 / 大白话注释：都没有就用快速模式

    async def _execute_mcp_research_for_queries(self, queries: list, mcp_retrievers: list) -> list:
        """为一组查询批量执行 MCP 搜索
        【正经注释】遍历查询列表，对每个查询使用所有 MCP 检索器执行搜索，
        将结果统一格式化为 {content, url, title, query, source_type} 的上下文条目。
        单个查询或检索器的失败不影响其他查询的处理。
        【大白话注释】拿一组问题去问外部工具，把所有回答都收回来：
        - 每个问题用每个外部工具都问一遍
        - 把回答整理成统一格式
        - 某个工具出错了不影响其他的
        Args:
            queries: 查询列表（大白话：要问的问题清单）
            mcp_retrievers: MCP 检索器列表（大白话：可用的外部工具清单）
        Returns:
            list: 合并后的 MCP 上下文条目列表（大白话：外部工具的所有回答）
        """
        all_mcp_context = []									# 正经注释：初始化所有 MCP 上下文的容器 / 大白话注释：准备一个大篮子装所有结果

        for i, query in enumerate(queries, 1):					# 正经注释：遍历每个查询 / 大白话注释：一个一个问题来
            self.logger.info(f"Executing MCP research for query {i}/{len(queries)}: {query}")

            for retriever in mcp_retrievers:					# 正经注释：对每个 MCP 检索器执行搜索 / 大白话注释：每个外部工具都问一遍
                try:
                    mcp_results = await self._execute_mcp_research(retriever, query)	# 正经注释：执行单个 MCP 搜索 / 大白话注释：问一次
                    if mcp_results:
                        for result in mcp_results:				# 正经注释：将每条结果格式化为统一的上下文条目 / 大白话注释：把回答整理一下
                            content = result.get("body", "")	# 正经注释：提取正文内容 / 大白话注释：回答的内容
                            url = result.get("href", "")		# 正经注释：提取来源 URL / 大白话注释：回答来自哪个链接
                            title = result.get("title", "")		# 正经注释：提取标题 / 大白话注释：回答的标题

                            if content:
                                context_entry = {				# 正经注释：构建标准化的上下文条目 / 大白话注释：把回答装成统一格式
                                    "content": content,
                                    "url": url,
                                    "title": title,
                                    "query": query,				# 正经注释：记录对应的查询 / 大白话注释：哪个问题问出来的
                                    "source_type": "mcp"			# 正经注释：标记来源类型为 MCP / 大白话注释：标记"这是外部工具给的"
                                }
                                all_mcp_context.append(context_entry)	# 正经注释：追加到结果列表 / 大白话注释：放到大篮子里

                        self.logger.info(f"Added {len(mcp_results)} MCP results for query: {query}")	# 正经注释：记录该查询的 MCP 结果数量 / 大白话注释：日志——这次问到了几条

                        if self.researcher.verbose:				# 正经注释：详细模式下推送缓存进度 / 大白话注释：开了"字幕"就告诉用户进度
                            await stream_output(
                                "logs",
                                "mcp_results_cached",
                                f"✅ Cached {len(mcp_results)} MCP results from query {i}/{len(queries)}",
                                self.researcher.websocket,
                            )
                except Exception as e:							# 正经注释：单个查询失败不影响其他查询 / 大白话注释：某个工具出错了也没事，继续问下一个
                    self.logger.error(f"Error in MCP research for query '{query}': {e}")
                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_cache_error",
                            f"⚠️ MCP research error for query {i}, continuing with other sources",
                            self.researcher.websocket,
                        )

        return all_mcp_context								# 正经注释：返回所有 MCP 上下文条目 / 大白话注释：把大篮子交出去

    async def _process_sub_query(self, sub_query: str, scraped_data: list = [], query_domains: list = []):
        """处理单个子查询：搜索 + 抓取 + 上下文提取
        【正经注释】
        子查询的核心处理逻辑：
        1. 根据 MCP 策略获取或复用 MCP 上下文
        2. 通过非 MCP 检索器搜索并抓取网页内容
        3. 通过语义搜索提取相关内容
        4. 智能合并 MCP 和 Web 上下文
        包含完整的错误处理，单个子查询失败不影响其他子查询。
        【大白话注释】
        处理一个小问题的完整流程：
        1. 如果有外部工具，看看怎么用它（用缓存/重新搜/跳过）
        2. 用普通搜索引擎搜网页、抓内容
        3. 从抓到的内容里挑相关的
        4. 把外部工具和搜索引擎的结果合在一起
        Args:
            sub_query: 子查询文本（大白话：这个小问题是啥）
            scraped_data: 已有的抓取数据（大白话：之前抓过的资料）
            query_domains: 限制搜索的域名（大白话：只在哪些网站搜）
        Returns:
            合并后的上下文字符串（大白话：整理好的素材）
        """
        if self.json_handler:									# 正经注释：记录子查询事件到 JSON 日志 / 大白话注释：在日志里记下正在搜哪个小问题
            self.json_handler.log_event("sub_query", {
                "query": sub_query,
                "scraped_data_size": len(scraped_data)
            })

        if self.researcher.verbose:								# 正经注释：推送子查询研究开始信息 / 大白话注释：告诉用户"正在搜xxx"
            await stream_output(
                "logs",
                "running_subquery_research",
                f"\n🔍 Running research for '{sub_query}'...",
                self.researcher.websocket,
            )

        try:  #这里是mcp的处理
            mcp_retrievers = [r for r in self.researcher.retrievers if "mcpretriever" in r.__name__.lower()]	# 正经注释：筛选 MCP 检索器 / 大白话注释：挑出外部工具
            non_mcp_retrievers = [r for r in self.researcher.retrievers if "mcpretriever" not in r.__name__.lower()]	# 正经注释：筛选非 MCP 检索器 / 大白话注释：挑出普通搜索引擎

            mcp_context = []									# 正经注释：初始化 MCP 上下文容器 / 大白话注释：准备装外部工具的结果
            web_context = ""									# 正经注释：初始化 Web 上下文 / 大白话注释：准备装搜索引擎的结果

            mcp_strategy = self._get_mcp_strategy()				# 正经注释：获取当前 MCP 策略 / 大白话注释：看看外部工具用哪种模式

            if mcp_retrievers:									# 正经注释：有 MCP 检索器时，根据策略处理 / 大白话注释：有外部工具就用上
                if mcp_strategy == "disabled":					# 正经注释：禁用模式 - 完全跳过 MCP / 大白话注释：跳过外部工具
                    self.logger.info(f"MCP disabled for sub-query: {sub_query}")
                elif mcp_strategy == "fast" and self._mcp_results_cache is not None:	# 正经注释：快速模式 - 复用已缓存的 MCP 结果 / 大白话注释：快速模式——直接用之前搜过的
                    mcp_context = self._mcp_results_cache.copy()	# 正经注释：拷贝缓存结果 / 大白话注释：把之前存的结果拿出来

                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_cache_reuse",
                            f"♻️ Reusing cached MCP results ({len(mcp_context)} sources) for: {sub_query}",
                            self.researcher.websocket,
                        )

                    self.logger.info(f"Reused {len(mcp_context)} cached MCP results for sub-query: {sub_query}")
                elif mcp_strategy == "deep":					# 正经注释：深度模式 - 每个子查询单独执行 MCP / 大白话注释：深度模式——重新搜一次外部工具
                    self.logger.info(f"Running deep MCP research for: {sub_query}")
                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_comprehensive_run",
                            f"🔍 Running deep MCP research for: {sub_query}",
                            self.researcher.websocket,
                        )

                    mcp_context = await self._execute_mcp_research_for_queries([sub_query], mcp_retrievers)	# 正经注释：为该子查询执行 MCP 搜索 / 大白话注释：拿这个小问题去问外部工具
                else:											# 正经注释：兜底 - 缓存不可用时回退到逐个查询执行 / 大白话注释：缓存没建好就临时搜一次
                    self.logger.warning("MCP cache not available, falling back to per-sub-query execution")
                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_fallback",
                            f"🔌 MCP cache unavailable, running MCP research for: {sub_query}",
                            self.researcher.websocket,
                        )

                    mcp_context = await self._execute_mcp_research_for_queries([sub_query], mcp_retrievers)

            if not scraped_data:								# 【Web通道第一步：广撒网】通过搜索引擎搜+抓网页（所有子查询），拿回一堆原始内容（可能几万字）
                scraped_data = await self._scrape_data_by_urls(sub_query, query_domains)
                self.logger.info(f"Scraped data size: {len(scraped_data)}")

            if scraped_data:									# 【Web通道第二步：精确筛选】用 embedding 相似度从原始内容中挑出跟子查询最相关的片段
                web_context = await self.researcher.context_manager.get_similar_content_by_query(sub_query, scraped_data)
                self.logger.info(f"Web content found for sub-query: {len(str(web_context)) if web_context else 0} chars")

            combined_context = self._combine_mcp_and_web_context(mcp_context, web_context, sub_query)	# 正经注释：智能合并 MCP 和 Web 上下文 / 大白话注释：把外部工具和搜索引擎的结果拼在一起

            if combined_context:								# 正经注释：记录上下文合并结果 / 大白话注释：有结果就记录一下
                context_length = len(str(combined_context))
                self.logger.info(f"Combined context for '{sub_query}': {context_length} chars")

                if self.researcher.verbose:						# 正经注释：详细模式下推送上下文统计 / 大白话注释：告诉用户搜到了多少
                    mcp_count = len(mcp_context)
                    web_available = bool(web_context)
                    cache_used = self._mcp_results_cache is not None and mcp_retrievers and mcp_strategy != "deep"
                    cache_status = " (cached)" if cache_used else ""
                    await stream_output(
                        "logs",
                        "context_combined",
                        f"📚 Combined research context: {mcp_count} MCP sources{cache_status}, {'web content' if web_available else 'no web content'}",
                        self.researcher.websocket,
                    )
            else:												# 正经注释：无合并上下文时的警告 / 大白话注释：啥也没搜到
                self.logger.warning(f"No combined context found for sub-query: {sub_query}")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "subquery_context_not_found",
                        f"🤷 No content found for '{sub_query}'...",
                        self.researcher.websocket,
                    )

            if combined_context and self.json_handler:			# 正经注释：记录内容发现事件到 JSON 日志 / 大白话注释：在 JSON 日志里记一笔搜到了什么
                self.json_handler.log_event("content_found", {
                    "sub_query": sub_query,
                    "content_size": len(str(combined_context)),
                    "mcp_sources": len(mcp_context),
                    "web_content": bool(web_context)
                })

            return combined_context							# 正经注释：返回合并后的上下文 / 大白话注释：把整理好的素材交出去

        except Exception as e:									# 正经注释：异常处理，记录错误并返回空字符串 / 大白话注释：出错了记个日志，返回空结果
            self.logger.error(f"Error processing sub-query {sub_query}: {e}", exc_info=True)
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "subquery_error",
                    f"❌ Error processing '{sub_query}': {str(e)}",
                    self.researcher.websocket,
                )
            return ""

    async def _execute_mcp_research(self, retriever, query):
        """执行单次 MCP 检索器搜索（两阶段方法）
        【正经注释】
        实例化 MCP 检索器并执行两阶段搜索：
        阶段1：选择最优的 MCP 工具
        阶段2：使用选定工具执行搜索
        通过传入 researcher 实例使检索器能访问 cfg 和 mcp_configs。
        【大白话注释】
        用一个外部工具搜一次：
        1. 先选最合适的工具
        2. 用选好的工具搜索
        把完整的"老板信息"传给工具，这样工具能自己找需要的配置。
        Args:
            retriever: MCP 检索器类（大白话：哪个外部工具）
            query: 搜索查询（大白话：要搜什么）
        Returns:
            list: MCP 搜索结果列表（大白话：外部工具的回答）
        """
        retriever_name = retriever.__name__						# 正经注释：获取检索器名称用于日志 / 大白话注释：记下工具的名字

        self.logger.info(f"Executing MCP research with {retriever_name} for query: {query}")

        try:
            retriever_instance = retriever(						# 正经注释：实例化 MCP 检索器，传入查询、请求头、域名限制等参数 / 大白话注释：创建工具实例，告诉它要搜什么
                query=query,
                headers=self.researcher.headers,
                query_domains=self.researcher.query_domains,
                websocket=self.researcher.websocket,
                researcher=self.researcher						# 正经注释：传入完整 researcher 实例以访问 cfg 和 mcp_configs / 大白话注释：把"老板"的完整信息都给它
            )

            if self.researcher.verbose:							# 正经注释：推送 MCP 工具选择阶段信息 / 大白话注释：告诉用户"在选工具了"
                await stream_output(
                    "logs",
                    "mcp_retrieval_stage1",
                    f"🧠 Stage 1: Selecting optimal MCP tools for: {query}",
                    self.researcher.websocket,
                )

            results = retriever_instance.search(				# 正经注释：执行两阶段 MCP 搜索 / 大白话注释：让工具去搜
                max_results=self.researcher.cfg.max_search_results_per_query	# 正经注释：限制最大返回结果数 / 大白话注释：最多返回几条结果
            )

            if results:											# 正经注释：有结果时记录并推送 / 大白话注释：搜到了东西
                result_count = len(results)
                self.logger.info(f"MCP research completed: {result_count} results from {retriever_name}")

                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_research_complete",
                        f"🎯 MCP research completed: {result_count} intelligent results obtained",
                        self.researcher.websocket,
                    )

                return results									# 正经注释：返回搜索结果 / 大白话注释：把结果交出去
            else:												# 正经注释：无结果时的处理 / 大白话注释：没搜到东西
                self.logger.info(f"No results returned from MCP research with {retriever_name}")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "mcp_no_results",
                        f"ℹ️ No relevant information found via MCP for: {query}",
                        self.researcher.websocket,
                    )
                return []										# 正经注释：返回空列表 / 大白话注释：返回空篮子

        except Exception as e:									# 正经注释：MCP 搜索异常处理 / 大白话注释：外部工具出错了
            self.logger.error(f"Error in MCP research with {retriever_name}: {str(e)}")
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "mcp_research_error",
                    f"⚠️ MCP research error: {str(e)} - continuing with other sources",
                    self.researcher.websocket,
                )
            return []											# 正经注释：返回空列表，确保不影响其他来源 / 大白话注释：返回空结果，别影响其他工具

    def _combine_mcp_and_web_context(self, mcp_context: list, web_context: str, sub_query: str) -> str:
        """智能合并 MCP 和 Web 研究上下文
        【正经注释】
        将 MCP 工具结果和 Web 搜索结果合并为统一格式的上下文字符串。
        Web 上下文优先排列，MCP 结果按条目格式化并附带来源引用信息。
        使用 "---" 分隔符清晰区分不同来源。
        【大白话注释】
        把外部工具的回答和搜索引擎的结果拼在一起：
        - 先放搜索引擎的结果
        - 再放外部工具的结果，每条都带上"来自哪里"的标注
        - 不同来源之间用分隔线隔开
        Args:
            mcp_context: MCP 上下文条目列表（大白话：外部工具的回答列表）
            web_context: Web 上下文字符串（大白话：搜索引擎的结果）
            sub_query: 当前子查询（大白话：正在搜的小问题）
        Returns:
            str: 合并后的上下文字符串（大白话：拼好的所有素材）
        """
        combined_parts = []										# 正经注释：初始化合并结果容器 / 大白话注释：准备拼装的零件

        if web_context and web_context.strip():					# 正经注释：优先添加 Web 上下文 / 大白话注释：先放搜索引擎的结果
            combined_parts.append(web_context.strip())
            self.logger.debug(f"Added web context: {len(web_context)} chars")

        if mcp_context:											# 正经注释：添加 MCP 上下文并格式化 / 大白话注释：再放外部工具的结果
            mcp_formatted = []									# 正经注释：格式化后的 MCP 条目列表 / 大白话注释：整理好格式的结果

            for i, item in enumerate(mcp_context):				# 正经注释：遍历每条 MCP 结果 / 大白话注释：一条一条整理
                content = item.get("content", "")				# 正经注释：提取正文内容 / 大白话注释：回答内容
                url = item.get("url", "")						# 正经注释：提取来源 URL / 大白话注释：回答来自哪个链接
                title = item.get("title", f"MCP Result {i+1}")	# 正经注释：提取标题，无标题时使用默认编号 / 大白话注释：回答的标题

                if content and content.strip():
                    if url and url != f"mcp://llm_analysis":	# 正经注释：有效 URL 时添加带链接的引用 / 大白话注释：有链接就标上链接
                        citation = f"\n\n*Source: {title} ({url})*"
                    else:										# 正经注释：无有效 URL 时仅添加标题引用 / 大白话注释：没链接就只标标题
                        citation = f"\n\n*Source: {title}*"

                    formatted_content = f"{content.strip()}{citation}"	# 正经注释：拼接正文和引用信息 / 大白话注释：把内容和来源拼在一起
                    mcp_formatted.append(formatted_content)

            if mcp_formatted:									# 正经注释：将格式化的 MCP 结果用分隔线连接后添加到合并列表 / 大白话注释：把整理好的外部工具结果加进去
                mcp_section = "\n\n---\n\n".join(mcp_formatted)	# 正经注释：使用分隔线连接各条目 / 大白话注释：每条结果之间画条线隔开
                combined_parts.append(mcp_section)
                self.logger.debug(f"Added {len(mcp_context)} MCP context entries")

        if combined_parts:										# 正经注释：合并所有部分为最终上下文 / 大白话注释：把所有零件拼起来
            final_context = "\n\n".join(combined_parts)			# 正经注释：用双换行连接 Web 和 MCP 部分 / 大白话注释：搜索引擎和外部工具的结果之间空一行
            self.logger.info(f"Combined context for '{sub_query}': {len(final_context)} total chars")
            return final_context								# 正经注释：返回合并后的上下文 / 大白话注释：把拼好的交出去
        else:													# 正经注释：无任何上下文可合并 / 大白话注释：啥也没有
            self.logger.warning(f"No context to combine for sub-query: {sub_query}")
            return ""											# 正经注释：返回空字符串 / 大白话注释：返回空

    async def _process_sub_query_with_vectorstore(self, sub_query: str, filter: dict | None = None):
        """从向量数据库处理单个子查询
        【正经注释】对子查询在向量库中进行语义检索，直接返回相关上下文。
        适用于用户提供了预构建向量数据库的场景。
        【大白话注释】在"智能搜索库"里搜一个小问题，直接返回搜到的结果。
        Args:
            sub_query: 子查询文本（大白话：小问题）
            filter: 过滤条件（大白话：搜索时的筛选条件）
        Returns:
            str: 上下文内容（大白话：搜到的素材）
        """
        if self.researcher.verbose:								# 正经注释：推送向量库子查询研究信息 / 大白话注释：告诉用户"在向量库里搜xxx"
            await stream_output(
                "logs",
                "running_subquery_with_vectorstore_research",
                f"\n🔍 Running research for '{sub_query}'...",
                self.researcher.websocket,
            )

        context = await self.researcher.context_manager.get_similar_content_by_query_with_vectorstore(sub_query, filter)	# 正经注释：在向量库中按子查询和过滤条件检索 / 大白话注释：在智能搜索库里搜

        return context											# 正经注释：返回检索结果 / 大白话注释：把搜到的交出去

    async def _get_new_urls(self, url_set_input):
        """从 URL 集合中过滤出未访问过的新 URL
        【正经注释】遍历输入的 URL 集合，排除已访问过的 URL，
        将新 URL 同时记录到 visited_urls 集合中以避免后续重复访问。
        【大白话注释】看一堆网址，只挑出没看过的，并且把新网址记到"已看列表"里。
        Args:
            url_set_input: 输入的 URL 集合（大白话：一堆网页链接）
        Returns:
            list[str]: 新 URL 列表（大白话：没看过的网页链接）
        """

        new_urls = []											# 正经注释：初始化新 URL 列表 / 大白话注释：准备装新网址
        for url in url_set_input:								# 正经注释：遍历每个 URL / 大白话注释：一个一个看
            if url not in self.researcher.visited_urls:			# 正经注释：检查 URL 是否已在已访问集合中 / 大白话注释：没看过就留下
                self.researcher.visited_urls.add(url)			# 正经注释：添加到已访问集合 / 大白话注释：标记为"已看"
                new_urls.append(url)							# 正经注释：添加到新 URL 列表 / 大白话注释：放到新篮子里
                if self.researcher.verbose:						# 正经注释：详细模式下推送新 URL 信息 / 大白话注释：告诉用户新发现了一个网址
                    await stream_output(
                        "logs",
                        "added_source_url",
                        f"✅ Added source url to research: {url}\n",
                        self.researcher.websocket,
                        True,
                        url,
                    )

        return new_urls										# 正经注释：返回新 URL 列表 / 大白话注释：把新网址交出去

    async def _search_relevant_source_urls(self, query, query_domains: list | None = None):
        """搜索并收集相关的来源 URL
        【正经注释】
        遍历所有检索器（跳过 MCP），对每个检索器执行搜索：
        - 已有 raw_content 的结果直接保留（如 PubMed Central 等已获取全文的检索器）
        - 仅有 URL 的结果加入待抓取列表
        最后过滤已访问的 URL 并随机打乱顺序。
        【大白话注释】
        用搜索引擎找相关的网页链接：
        - 有些搜索引擎已经把网页内容一起返回了（就不需要再抓了）
        - 有些只返回了链接（需要后面再抓内容）
        - 去掉已经看过的链接，然后随机排个序
        Args:
            query: 搜索查询（大白话：要搜什么）
            query_domains: 限制搜索的域名（大白话：只在哪些网站搜）
        Returns:
            tuple: (新 URL 列表, 预取内容列表)（大白话：（要抓的链接，已经有内容的链接））
        """
        new_search_urls = []									# 正经注释：待抓取的 URL 列表 / 大白话注释：需要抓内容的链接
        prefetched_content = []								# 正经注释：已有完整内容的结果列表 / 大白话注释：已经有内容的链接（不用再抓）
        if query_domains is None:
            query_domains = []

        for retriever_class in self.researcher.retrievers:		# 正经注释：遍历所有检索器 / 大白话注释：每个搜索引擎都用一遍
            if "mcpretriever" in retriever_class.__name__.lower():	# 正经注释：跳过 MCP 检索器，它们不提供可抓取的 URL / 大白话注释：外部工具不用这个方式搜
                continue

            try:
                retriever = retriever_class(query, query_domains=query_domains)	# 正经注释：实例化检索器 / 大白话注释：创建搜索引擎实例

                search_results = await asyncio.to_thread(		# 正经注释：在线程池中执行同步搜索，避免阻塞事件循环 / 大白话注释：用后台线程搜，不耽误其他事
                    retriever.search, max_results=self.researcher.cfg.max_search_results_per_query
                )

                if not search_results:							# 正经注释：无结果则跳过该检索器 / 大白话注释：没搜到就换下一个
                    continue

                for result in search_results:					# 正经注释：分类处理每条搜索结果 / 大白话注释：逐条看搜索结果
                    url = result.get("href") or result.get("url")	# 正经注释：提取 URL（兼容 href 和 url 两种键名） / 大白话注释：拿到链接
                    raw_content = result.get("raw_content")		# 正经注释：提取原始内容 / 大白话注释：看看有没有直接附带的网页内容
                    if url and raw_content and len(raw_content) > 100:	# 正经注释：有完整内容（>100字符）的直接保留，无需再抓取 / 大白话注释：内容够长就不用再抓了
                        prefetched_content.append({
                            "url": url,
                            "raw_content": raw_content,
                        })
                        self.researcher.add_research_sources([{"url": url}])	# 正经注释：记录为研究来源 / 大白话注释：记下来"这个链接用过"
                    elif url:									# 正经注释：仅有 URL 的加入待抓取列表 / 大白话注释：只有链接没内容，后面再抓
                        new_search_urls.append(url)
            except Exception as e:								# 正经注释：单个检索器失败不影响其他检索器 / 大白话注释：某个搜索引擎出错了也没事
                self.logger.error(f"Error searching with {retriever_class.__name__}: {e}")

        new_search_urls = await self._get_new_urls(new_search_urls)	# 正经注释：过滤已访问 URL / 大白话注释：去掉看过的
        random.shuffle(new_search_urls)							# 正经注释：随机打乱 URL 顺序，避免对特定来源的偏倚 / 大白话注释：随机排个序，别老先看同一个网站

        return new_search_urls, prefetched_content				# 正经注释：返回待抓取 URL 和预取内容 / 大白话注释：把两种链接都交出去

    async def _scrape_data_by_urls(self, sub_query, query_domains: list | None = None):
        """根据子查询搜索并抓取网页内容
        【正经注释】
        完整的搜索-抓取流程：
        1. 通过检索器搜索获取相关 URL和内容 url如果没有内容就走第2步
        2. 对需要抓取的 URL 使用浏览器管理器获取页面内容
        3. 合并预取内容（检索器已提供的全文）
        4. 可选加载到向量库
        【大白话注释】
        搜网页 + 抓内容的完整流程：
        1. 先用搜索引擎找到相关网页链接
        2. 让爬虫去抓那些需要抓的网页
        3. 把搜索引擎已经给的内容和爬虫抓的内容合并
        4. 如果有智能搜索库就存进去
        Args:
            sub_query: 子查询文本（大白话：小问题）
        Returns:
            list: 抓取的内容结果列表（大白话：抓到的所有内容）
        """
        if query_domains is None:
            query_domains = []

        new_search_urls, prefetched_content = await self._search_relevant_source_urls(sub_query, query_domains)	# 正经注释：搜索获取 URL 和预取内容 / 大白话注释：搜一遍，拿到链接和已有内容

        if self.researcher.verbose:								# 正经注释：详细模式下推送搜索进度 / 大白话注释：告诉用户"正在搜"
            await stream_output(
                "logs",
                "researching",
                f"🤔 Researching for relevant information across multiple sources...\n",
                self.researcher.websocket,
            )

        scraped_content = await self.researcher.scraper_manager.browse_urls(new_search_urls)	# 正经注释：通过浏览器管理器抓取待处理的 URL / 大白话注释：让爬虫去抓网页

        scraped_content.extend(prefetched_content)				# 正经注释：合并预取内容（检索器已提供的全文无需再抓取） / 大白话注释：把搜索引擎直接给的内容也加进来

        if self.researcher.vector_store:						# 正经注释：将抓取内容加载到向量库以支持语义检索 / 大白话注释：存到智能搜索库
            self.researcher.vector_store.load(scraped_content)

        return scraped_content								# 正经注释：返回所有抓取内容 / 大白话注释：把所有内容交出去

    async def _search(self, retriever, query):
        """使用指定检索器执行搜索
        【正经注释】
        通用检索器搜索方法，实例化检索器后执行搜索。
        MCP 检索器需要传入额外的 websocket 和 researcher 参数。
        包含详细的日志记录和错误处理。
        【大白话注释】
        用一个搜索引擎搜一次：
        - 如果是外部工具，还要多传一些参数
        - 搜到了就返回结果列表
        - 没搜到就返回空列表
        - 出错了也不崩溃
        Args:
            retriever: 检索器类（大白话：哪个搜索引擎）
            query: 搜索查询（大白话：搜什么）
        Returns:
            list: 搜索结果列表（大白话：搜到的结果）
        """
        retriever_name = retriever.__name__						# 正经注释：获取检索器名称 / 大白话注释：记住搜索引擎的名字
        is_mcp_retriever = "mcpretriever" in retriever_name.lower()	# 正经注释：判断是否为 MCP 检索器 / 大白话注释：是不是外部工具

        self.logger.info(f"Searching with {retriever_name} for query: {query}")

        try:
            retriever_instance = retriever(						# 正经注释：实例化检索器，MCP 检索器需要额外参数 / 大白话注释：创建搜索引擎实例
                query=query,
                headers=self.researcher.headers,
                query_domains=self.researcher.query_domains,
                websocket=self.researcher.websocket if is_mcp_retriever else None,	# 正经注释：MCP 检索器需要 WebSocket 连接 / 大白话注释：外部工具需要实时推送通道
                researcher=self.researcher if is_mcp_retriever else None	# 正经注释：MCP 检索器需要 researcher 实例 / 大白话注释：外部工具需要"老板信息"
            )

            if is_mcp_retriever and self.researcher.verbose:	# 正经注释：MCP 检索器在详细模式下推送查询信息 / 大白话注释：告诉用户"在问外部工具"
                await stream_output(
                    "logs",
                    "mcp_retrieval",
                    f"🔌 Consulting MCP server(s) for information on: {query}",
                    self.researcher.websocket,
                )

            if hasattr(retriever_instance, 'search'):			# 正经注释：检查检索器是否有 search 方法 / 大白话注释：确认这个工具能搜
                results = retriever_instance.search(
                    max_results=self.researcher.cfg.max_search_results_per_query	# 正经注释：限制最大结果数 / 大白话注释：最多返回几条
                )

                if results:										# 正经注释：有结果时的处理 / 大白话注释：搜到了东西
                    result_count = len(results)
                    self.logger.info(f"Received {result_count} results from {retriever_name}")

                    if is_mcp_retriever:						# 正经注释：MCP 检索器的特殊日志 / 大白话注释：外部工具的详细记录
                        if self.researcher.verbose:
                            await stream_output(
                                "logs",
                                "mcp_results",
                                f"✓ Retrieved {result_count} results from MCP server",
                                self.researcher.websocket,
                            )

                        for i, result in enumerate(results[:3]):	# 正经注释：记录前 3 条结果的详细信息 / 大白话注释：日志——前3条是啥
                            title = result.get("title", "No title")
                            url = result.get("href", "No URL")
                            content_length = len(result.get("body", "")) if result.get("body") else 0
                            self.logger.info(f"MCP result {i+1}: '{title}' from {url} ({content_length} chars)")

                        if result_count > 3:					# 正经注释：超过 3 条时记录剩余数量 / 大白话注释：日志——还有几条没细说
                            self.logger.info(f"... and {result_count - 3} more MCP results")
                else:											# 正经注释：无结果时的处理 / 大白话注释：没搜到东西
                    self.logger.info(f"No results returned from {retriever_name}")
                    if is_mcp_retriever and self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "mcp_no_results",
                            f"ℹ️ No relevant information found from MCP server for: {query}",
                            self.researcher.websocket,
                        )

                return results									# 正经注释：返回搜索结果 / 大白话注释：把结果交出去
            else:												# 正经注释：检索器没有 search 方法的错误 / 大白话注释：这个工具不能用
                self.logger.error(f"Retriever {retriever_name} does not have a search method")
                return []
        except Exception as e:									# 正经注释：搜索异常处理 / 大白话注释：出错了
            self.logger.error(f"Error searching with {retriever_name}: {str(e)}")
            if is_mcp_retriever and self.researcher.verbose:
                await stream_output(
                    "logs",
                    "mcp_error",
                    f"❌ Error retrieving information from MCP server: {str(e)}",
                    self.researcher.websocket,
                )
            return []											# 正经注释：返回空列表 / 大白话注释：返回空结果

    async def _extract_content(self, results):
        """从搜索结果中提取内容
        【正经注释】
        从搜索结果字典中提取 URL，过滤已访问的 URL，
        然后通过浏览器管理器抓取新页面的内容。
        【大白话注释】
        拿到搜索结果后，去抓那些没看过的网页内容：
        1. 从搜索结果里挑出链接
        2. 去掉已经看过的
        3. 让爬虫去抓新链接的内容
        Args:
            results: 搜索结果列表（大白话：搜索引擎返回的结果）
        Returns:
            list: 抓取的内容列表（大白话：抓到的网页内容）
        """
        self.logger.info(f"Extracting content from {len(results)} search results")	# 正经注释：记录开始提取内容 / 大白话注释：日志——开始抓网页

        urls = []												# 正经注释：从搜索结果中提取 URL / 大白话注释：准备装链接
        for result in results:
            if isinstance(result, dict) and "href" in result:	# 正经注释：检查结果格式并提取 href 字段 / 大白话注释：看看有没有链接
                urls.append(result["href"])

        if not urls:											# 正经注释：无 URL 则直接返回空 / 大白话注释：没链接就不用抓了
            return []

        new_urls = [url for url in urls if url not in self.researcher.visited_urls]	# 正经注释：过滤已访问 URL / 大白话注释：去掉看过的

        if not new_urls:										# 正经注释：无新 URL 则返回空 / 大白话注释：都是看过的
            return []

        scraped_content = await self.researcher.scraper_manager.browse_urls(new_urls)	# 正经注释：抓取新 URL 的内容 / 大白话注释：让爬虫去抓

        self.researcher.visited_urls.update(new_urls)			# 正经注释：将新 URL 标记为已访问 / 大白话注释：标记"这些看过了"

        return scraped_content								# 正经注释：返回抓取内容 / 大白话注释：把抓到的交出去

    async def _summarize_content(self, query, content):
        """对提取的内容进行摘要
        【正经注释】
        通过上下文管理器的语义搜索对内容进行相关性提取，
        返回与查询最相关的内容摘要。
        【大白话注释】
        从一堆内容里挑出跟问题最相关的部分，相当于"写摘要"。
        Args:
            query: 搜索查询（大白话：要找什么）
            content: 待摘要的内容（大白话：一大堆素材）
        Returns:
            str: 摘要内容（大白话：挑出来的相关部分）
        """
        self.logger.info(f"Summarizing content for query: {query}")	# 正经注释：记录摘要开始 / 大白话注释：日志——开始提取相关内容

        if not content:											# 正经注释：无内容直接返回空 / 大白话注释：没东西可提
            return ""

        summary = await self.researcher.context_manager.get_similar_content_by_query(	# 正经注释：通过语义搜索提取与查询相关的内容 / 大白话注释：用 AI 找相关部分
            query, content
        )

        return summary											# 正经注释：返回摘要结果 / 大白话注释：把提取的交出去

    async def _update_search_progress(self, current, total):
        """更新搜索进度
        【正经注释】计算当前进度百分比并通过 WebSocket 推送进度事件。
        【大白话注释】告诉用户"搜了百分之几了"。
        Args:
            current: 已处理的子查询数（大白话：搞定了几个）
            total: 子查询总数（大白话：一共几个）
        """
        if self.researcher.verbose and self.researcher.websocket:	# 正经注释：仅在详细模式且有 WebSocket 连接时推送 / 大白话注释：开了字幕且有人看才播报
            progress = int((current / total) * 100)				# 正经注释：计算百分比 / 大白话注释：算百分比
            await stream_output(
                "logs",
                "research_progress",
                f"📊 Research Progress: {progress}%",
                self.researcher.websocket,
                True,
                {
                    "current": current,
                    "total": total,
                    "progress": progress
                }
            )
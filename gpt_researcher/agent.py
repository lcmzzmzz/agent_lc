"""
GPT Researcher 核心代理模块

【正经注释】
本模块定义了 GPTResearcher 主类，作为整个自动化研究系统的编排器（Orchestrator）。
负责协调 LLM 调用、网络搜索、内容抓取、上下文管理和报告生成等子系统的交互。
采用 planner-executor-publisher 架构模式，支持多种报告类型和检索源。

核心依赖：
- Config: 配置管理系统，支持环境变量 > JSON 配置 > 默认值三级优先级
- GenericLLMProvider: LLM 抽象层，兼容所有 LangChain 支持的模型
- Memory: 基于 Embedding 的向量记忆系统
- 各种 Skill 模块: 研究执行、报告生成、浏览器管理等独立能力单元

【大白话注释】
这就是 GPT Researcher 的"大脑"——一个能自动帮你做调研的 AI 助手。
你给它一个问题，它会：
- 自动选一个合适的"研究员角色"来干活
- 上网搜各种资料
- 把搜到的东西整理成有用的上下文
- 最后帮你写出一份带引用的研究报告

支持的功能：
- 多种搜索引擎（Tavily、Google、DuckDuckGo 等）
- 多种报告类型（研究报告、资源报告、大纲报告、深度研究等）
- 实时 WebSocket 推送研究进度
- MCP（Model Context Protocol）工具集成
- 自动生成配图

一句话总结：一个"给问题、出报告"的自动化研究引擎。
"""

import json
import os
from typing import Any, Optional

# 正经注释：导入 actions 模块中的共享操作函数，用于代理选择、搜索、Markdown 处理等
# 大白话注释：把"选研究员"、"搜索"、"提取标题"这些通用工具都拿过来
from .actions import (
    add_references,
    choose_agent,
    extract_headers,
    extract_sections,
    get_retrievers,
    get_search_results,
    table_of_contents,
)
from .config import Config
from .llm_provider import GenericLLMProvider
from .memory import Memory
from .prompts import get_prompt_family

# 正经注释：导入各个 Skill 模块，每个模块封装一种独立的研究能力
# 大白话注释：把"搜索员"、"写手"、"浏览器"、"精选器"这些"干活的人"都请过来
from .skills.browser import BrowserManager
from .skills.context_manager import ContextManager
from .skills.curator import SourceCurator
from .skills.deep_research import DeepResearchSkill
from .skills.image_generator import ImageGenerator
from .skills.researcher import ResearchConductor
from .skills.writer import ReportGenerator
from .utils.enum import ReportSource, ReportType, Tone
from .utils.llm import create_chat_completion
from .vector_store import VectorStoreWrapper


class GPTResearcher:
    """
    GPT Researcher 核心代理类

    【正经注释】
    整个自动化研究系统的主编排器（Orchestrator），负责协调以下子系统：
    - 代理选择（Agent Selection）：根据查询内容自动匹配合适的研究角色
    - 网络搜索与内容抓取（Search & Scrape）：多搜索引擎并行检索 + 页面抓取
    - 上下文管理（Context Management）：对搜集到的内容进行去重、过滤、排序
    - 报告生成（Report Generation）：基于上下文生成结构化的研究报告
    - 成本追踪（Cost Tracking）：实时统计各步骤的 API 调用费用

    设计模式：外观模式（Facade），将复杂的子系统交互封装在统一的接口后面。
    所有核心研究方法均为 async，遵循异步 I/O 最佳实践。

    Attributes:
        query: 研究查询或问题
        report_type: 报告类型（research_report、resource_report 等）
        cfg: 配置对象（Config 实例）
        context: 累积的研究上下文数据
        research_costs: 累计 API 调用费用（美元）
        step_costs: 按步骤分类的费用明细字典

    【大白话注释】
    这个类就是整个系统的"总指挥"，你只要告诉它"我想研究什么"，剩下的它全包了：
    - 先选一个合适的"研究员"（比如科技专家、金融分析师）
    - 让研究员去网上搜资料
    - 把搜到的资料整理、去重、筛选
    - 最后写成一份漂亮的报告

    主要属性：
    - query: 你问的问题
    - report_type: 报告类型（完整报告、资源报告、大纲报告等）
    - cfg: 配置信息（模型、搜索引擎等各种设置）
    - context: 搜集到的所有研究素材
    - research_costs: 花了多少钱（API 调用费）
    - step_costs: 每个步骤分别花了多少

    一句话总结：研究任务的"大管家"，负责调度所有资源完成从提问到出报告的全流程。
    """

    def __init__(
        self,
        query: str,
        report_type: str = ReportType.ResearchReport.value,
        report_format: str = "markdown",
        report_source: str = ReportSource.Web.value,
        tone: Tone = Tone.Objective,
        source_urls: list[str] | None = None,
        document_urls: list[str] | None = None,
        complement_source_urls: bool = False,
        query_domains: list[str] | None = None,
        documents=None,
        vector_store=None,
        vector_store_filter=None,
        config_path=None,
        websocket=None,
        agent=None,
        role=None,
        parent_query: str = "",
        subtopics: list | None = None,
        visited_urls: set | None = None,
        verbose: bool = True,
        context=None,
        headers: dict | None = None,
        max_subtopics: int = 5,
        log_handler=None,
        prompt_family: str | None = None,
        mcp_configs: list[dict] | None = None,
        mcp_max_iterations: int | None = None,
        mcp_strategy: str | None = None,
        **kwargs
    ):
        """
        初始化 GPT Researcher 实例

        【正经注释】
        构造函数负责初始化研究代理的全部状态，包括：
        - 配置加载（Config）：从配置文件和环境变量中读取设置
        - 检索器初始化（Retrievers）：根据配置创建搜索引擎适配器
        - 记忆系统初始化（Memory）：基于 Embedding 模型的向量存储
        - 各 Skill 组件实例化：ResearchConductor、ReportGenerator、BrowserManager 等
        - MCP 配置处理：解析并注册外部工具服务器

        注意：report_type 为 DeepResearch 时会额外初始化 DeepResearchSkill 组件。

        【大白话注释】
        这个初始化就是"把所有工具都准备好"的过程：
        - 读取配置文件（用哪个模型、哪个搜索引擎等）
        - 把搜索引擎、记忆系统、各种"干活的人"都创建好
        - 如果是"深度研究"模式，还会准备一个专门的深度研究工具

        Args:
            query: 研究问题（大白话：你想调研什么）
            report_type: 报告类型，默认是完整研究报告（大白话：你要什么格式的报告）
            report_format: 报告输出格式，默认 markdown（大白话：报告用什么格式写）
            report_source: 信息来源，默认 Web 搜索（大白话：从哪里找资料——网上、本地、还是混合）
            tone: 报告语气，默认客观（大白话：报告用啥语气写——客观、主观、正式等）
            source_urls: 指定使用的 URL 列表（大白话：强制只用这些网址的资料）
            document_urls: 文档 URL 列表（大白话：指定的文档资料链接）
            complement_source_urls: 是否用网络搜索补充指定 URL（大白话：给的网址不够，要不要再上网搜搜补充）
            query_domains: 限制搜索的域名列表（大白话：只在指定网站上搜，比如只搜 wikipedia.org）
            documents: LangChain 文档对象（大白话：直接传入已有的文档资料）
            vector_store: 向量数据库（大白话：用于语义搜索的数据库）
            vector_store_filter: 向量库过滤条件（大白话：搜数据库时加的筛选条件）
            config_path: 配置文件路径（大白话：自定义配置文件的位置）
            websocket: WebSocket 连接（大白话：实时推送研究进度的通道）
            agent: 预定义的代理类型（大白话：直接指定用什么"研究员"，跳过自动选择）
            role: 预定义的代理角色（大白话：直接指定研究员的角色描述）
            parent_query: 父级查询（大白话：子课题报告所属的主问题）
            subtopics: 子课题列表（大白话：要研究的各个子话题）
            visited_urls: 已访问的 URL 集合（大白话：已经看过的网页，避免重复）
            verbose: 是否输出详细日志（大白话：要不要打印详细的运行过程）
            context: 预加载的研究上下文（大白话：直接传入已有的研究素材）
            headers: 请求头（大白话：发给 API 的额外请求头信息）
            max_subtopics: 最大子课题数量（大白话：最多拆分几个子话题）
            log_handler: 日志处理器（大白话：自定义日志的处理方式）
            prompt_family: 提示词家族（大白话：用哪套提示词模板）
            mcp_configs: MCP 服务器配置列表（大白话：外部工具服务器的配置信息）
            mcp_max_iterations: MCP 最大迭代次数（已废弃，大白话：旧参数，建议用 mcp_strategy）
            mcp_strategy: MCP 执行策略（大白话：外部工具怎么用——快速模式/深度模式/关闭）
                - "fast": 快速模式，用原始查询跑一次（默认）
                - "deep": 深度模式，每个子查询都跑一遍
                - "disabled": 不用外部工具，只用网络搜索
        """
        # 正经注释：保存额外关键字参数，供后续 LLM 调用和代理选择时透传
        # 大白话注释：把多出来的参数先存着，后面可能会用到
        self.kwargs = kwargs
        self.query = query
        self.report_type = report_type

        # 正经注释：加载配置对象，支持自定义配置文件路径；设置日志详细程度
        # 大白话注释：读配置文件，设置要不要打印详细日志
        self.cfg = Config(config_path)
        self.cfg.set_verbose(verbose)

        # 正经注释：报告来源优先使用参数传入值，其次从配置读取
        # 大白话注释：报告从哪找资料，优先用你传的参数，没传就从配置文件读
        self.report_source = report_source if report_source else getattr(self.cfg, 'report_source', None)
        self.report_format = report_format
        self.max_subtopics = max_subtopics

        # 正经注释：确保 tone 是 Tone 枚举类型，防止传入字符串导致后续逻辑异常
        # 大白话注释：统一语气格式，不管传进来的是字符串还是枚举，都转成枚举
        self.tone = tone if isinstance(tone, Tone) else Tone.Objective

        self.source_urls = source_urls
        self.document_urls = document_urls
        self.complement_source_urls = complement_source_urls
        self.query_domains = query_domains or []

        # 正经注释：初始化研究数据容器，用于存储抓取的源内容、图片等
        # 大白话注释：准备几个空篮子，后面用来装搜到的资料和图片
        self.research_sources = []  # 正经注释：抓取的来源列表，包含标题、内容和图片
        self.research_images = []   # 正经注释：精选的研究图片列表

        self.documents = documents

        # 正经注释：用 VectorStoreWrapper 封装向量数据库，提供统一的检索接口
        # 大白话注释：如果传了向量数据库就包一层壳子，方便后面调用
        self.vector_store = VectorStoreWrapper(vector_store) if vector_store else None
        self.vector_store_filter = vector_store_filter
        self.websocket = websocket
        self.agent = agent
        self.role = role
        self.parent_query = parent_query
        self.subtopics = subtopics or []
        self.visited_urls = visited_urls or set()
        self.verbose = verbose
        self.context = context or []
        self.headers = headers or {}

        # 正经注释：初始化成本追踪变量，research_costs 为累计总费用，step_costs 按步骤记录明细
        # 大白话注释：建个账本，记录调用 AI 接口花了多少钱（美元）
        self.research_costs = 0.0
        self.step_costs: dict[str, float] = {}
        self._current_step: str = "general"  # 正经注释：当前执行步骤标识，用于成本归属
        self.log_handler = log_handler

        # 正经注释：加载提示词家族（Prompt Family），决定 LLM 交互时使用的提示词模板
        # 大白话注释：选一套"提问模板"，决定怎么跟 AI 沟通
        self.prompt_family = get_prompt_family(prompt_family or self.cfg.prompt_family, self.cfg)

        # 【正经注释】
        # 处理 MCP（Model Context Protocol）配置，将外部工具服务器注册为检索器。
        # 通过修改 cfg.retrievers 而非 os.environ 来避免进程级环境变量污染（修复 #1676）。
        # 【大白话注释】
        # 如果配了外部工具（MCP），就把它加到"搜索工具箱"里。
        # 注意：直接改配置对象，不动系统环境变量，防止影响其他同时运行的请求。
        self.mcp_configs = mcp_configs
        if mcp_configs:
            self._process_mcp_configs(mcp_configs)

        # 正经注释：根据配置创建搜索引擎检索器实例列表
        # 大白话注释：把配置好的搜索引擎（比如 Tavily、Google）都准备好
        self.retrievers = get_retrievers(self.headers, self.cfg)

        # 正经注释：初始化 Embedding 记忆系统，用于上下文的向量化和语义检索
        # 大白话注释：建一个"记忆库"，用向量来存储和查找研究素材
        self.memory = Memory(
            self.cfg.embedding_provider, self.cfg.embedding_model, **self.cfg.embedding_kwargs
        )

        # 正经注释：默认使用 UTF-8 编码，从 kwargs 中提取后移除，避免传递给 LLM API
        # 大白话注释：设定编码方式，然后从额外参数里删掉，别传给 AI 接口
        self.encoding = kwargs.get('encoding', 'utf-8')
        self.kwargs.pop('encoding', None)

        # 【正经注释】
        # 实例化各 Skill 组件，每个组件封装一种独立的研究能力。
        # 所有组件都持有对 self（GPTResearcher 实例）的引用，可访问共享状态。
        # 【大白话注释】
        # 把"干活的人"都叫过来，每个人都能看到"总指挥"的信息
        self.research_conductor: ResearchConductor = ResearchConductor(self)    # 正经注释：研究执行器 / 大白话注释：负责搜资料的"搜索员"
        self.report_generator: ReportGenerator = ReportGenerator(self)          # 正经注释：报告生成器 / 大白话注释：负责写报告的"写手"
        self.context_manager: ContextManager = ContextManager(self)             # 正经注释：上下文管理器 / 大白话注释：负责整理素材的"编辑"
        self.scraper_manager: BrowserManager = BrowserManager(self)             # 正经注释：浏览器管理器 / 大白话注释：负责抓网页的"爬虫"
        self.source_curator: SourceCurator = SourceCurator(self)                # 正经注释：来源精选器 / 大白话注释：负责挑选好资料的"评审"

        # 正经注释：深度研究组件仅在报告类型为 DeepResearch 时初始化，支持递归树状探索
        # 大白话注释：如果是"深度研究"模式，再加一个专门做深度调研的高手
        self.deep_researcher: Optional[DeepResearchSkill] = None
        if report_type == ReportType.DeepResearch.value:
            self.deep_researcher = DeepResearchSkill(self)

        # 正经注释：图片生成器为可选组件，仅在配置了 API Key 时激活
        # 大白话注释：如果配了图片生成的 Key，就准备一个"画师"
        self.image_generator: Optional[ImageGenerator] = ImageGenerator(self)
        self.available_images: list = []  # 正经注释：预生成的图片列表，在报告生成前准备好以便嵌入
        self._research_id: str = ""       # 正经注释：本次研究会话的唯一标识符

        # 正经注释：解析 MCP 执行策略，支持新旧参数的向后兼容
        # 大白话注释：确定外部工具的使用方式，兼容老版本的参数格式
        self.mcp_strategy = self._resolve_mcp_strategy(mcp_strategy, mcp_max_iterations)

    def _generate_research_id(self) -> str:
        """
        生成唯一的研究会话 ID

        【正经注释】
        基于查询内容和当前时间戳生成 MD5 哈希值的前 12 位作为唯一标识。
        使用延迟计算（Lazy Initialization）模式，仅在首次调用时生成。
        适合用于日志追踪、图片命名等需要唯一标识的场景。

        【大白话注释】
        给这次研究任务生成一个"身份证号"。
        用你的问题加上当前时间，算出一串不重复的编号。
        只在第一次用的时候才生成，之后就一直用同一个。

        Returns:
            str: 研究会话的唯一标识符（大白话：这次研究的"身份证号"）
        """
        if not self._research_id:
            import hashlib
            import time
            # 正经注释：将查询文本与时间戳拼接后计算 MD5，取前 12 位确保简洁
            # 大白话注释：把问题和时间混在一起，算一个不重复的编号
            unique_str = f"{self.query}_{time.time()}"
            self._research_id = f"research_{hashlib.md5(unique_str.encode()).hexdigest()[:12]}"
        return self._research_id

    def _resolve_mcp_strategy(self, mcp_strategy: str | None, mcp_max_iterations: int | None) -> str:
        """
        解析 MCP 执行策略（支持向后兼容）

        【正经注释】
        按优先级从高到低解析 MCP 策略，支持新旧参数名的平滑迁移。
        优先级链：参数 mcp_strategy → 参数 mcp_max_iterations → 配置文件 → 默认值 "fast"。
        旧参数名映射：optimized → fast，comprehensive → deep。
        无效值自动降级为 fast 并输出警告日志。

        【大白话注释】
        确定"外部工具怎么用"，按这个顺序找：
        1. 你传的新参数 mcp_strategy（最优先）
        2. 旧参数 mcp_max_iterations（兼容老代码）
        3. 配置文件里的设置
        4. 都没有就用"快速模式"（fast）

        Args:
            mcp_strategy: 新版策略参数（大白话：直接指定 fast/deep/disabled）
            mcp_max_iterations: 旧版参数（大白话：老代码用的数字参数，已废弃）

        Returns:
            str: 解析后的策略（大白话：最终决定用哪种模式——"fast"/"deep"/"disabled"）
        """
        # 【正经注释】优先级 1：使用 mcp_strategy 参数
        # 【大白话注释】先看你有没有直接告诉我要用哪种模式
        if mcp_strategy is not None:
            # 正经注释：支持新版策略名称
            # 大白话注释：如果传的是新名字，直接用
            if mcp_strategy in ["fast", "deep", "disabled"]:
                return mcp_strategy
            # 正经注释：兼容旧版策略名称，映射到新名称并输出废弃警告
            # 大白话注释：如果传的是老名字，自动换成新的，提醒你下次用新名字
            elif mcp_strategy == "optimized":
                import logging
                logging.getLogger(__name__).warning("mcp_strategy 'optimized' is deprecated, use 'fast' instead")
                return "fast"
            elif mcp_strategy == "comprehensive":
                import logging
                logging.getLogger(__name__).warning("mcp_strategy 'comprehensive' is deprecated, use 'deep' instead")
                return "deep"
            else:
                # 正经注释：无效值降级为 fast 模式
                # 大白话注释：传了个不认识的值，默认用快速模式
                import logging
                logging.getLogger(__name__).warning(f"Invalid mcp_strategy '{mcp_strategy}', defaulting to 'fast'")
                return "fast"

        # 【正经注释】优先级 2：从旧参数 mcp_max_iterations 转换，保持向后兼容
        # 【大白话注释】第二步看老参数，把数字翻译成新模式
        if mcp_max_iterations is not None:
            import logging
            logging.getLogger(__name__).warning("mcp_max_iterations is deprecated, use mcp_strategy instead")

            # 正经注释：0 表示禁用，1 表示快速，-1 表示深度，其他值默认快速
            # 大白话注释：0=不用，1=快速，-1=深度，其他数字都当快速处理
            if mcp_max_iterations == 0:
                return "disabled"
            elif mcp_max_iterations == 1:
                return "fast"
            elif mcp_max_iterations == -1:
                return "deep"
            else:
                return "fast"

        # 【正经注释】优先级 3：从配置文件中读取策略设置
        # 【大白话注释】第三步去配置文件里找找有没有设置
        if hasattr(self.cfg, 'mcp_strategy'):
            config_strategy = self.cfg.mcp_strategy
            if config_strategy in ["fast", "deep", "disabled"]:
                return config_strategy
            # 正经注释：配置中的旧名称也需要映射
            # 大白话注释：配置文件里写的老名字也要转换
            elif config_strategy == "optimized":
                return "fast"
            elif config_strategy == "comprehensive":
                return "deep"

        # 【正经注释】优先级 4：默认使用 fast 策略
        # 【大白话注释】上面都没找到，就用默认的"快速模式"
        return "fast"

    def _process_mcp_configs(self, mcp_configs: list[dict]) -> None:
        """
        处理 MCP 服务器配置列表

        【正经注释】
        将 MCP 检索器注册到活跃检索器列表中。关键设计决策：
        通过直接修改 cfg.retrievers 而非 os.environ 来避免进程级环境变量污染。
        这解决了并发请求之间的隔离问题（修复 #1676）。
        支持字符串（逗号分隔）和列表两种 retrievers 配置格式。

        【大白话注释】
        把外部工具（MCP）加到"搜索工具箱"里。
        重要：直接改配置对象，不动系统环境变量——因为环境变量是全局共享的，
        如果改了它，同时跑的其他研究任务也会受影响，会出 bug。

        Args:
            mcp_configs: MCP 服务器配置字典列表（大白话：外部工具的配置信息列表）
        """
        # 正经注释：将 "mcp" 追加到配置的检索器列表，兼容字符串和列表两种格式
        # 大白话注释：在搜索引擎清单里加上"MCP"这个工具
        if hasattr(self.cfg, 'retrievers') and self.cfg.retrievers:
            current_retrievers = (
                list(self.cfg.retrievers)
                if isinstance(self.cfg.retrievers, list)
                else [r.strip() for r in str(self.cfg.retrievers).split(",") if r.strip()]
            )
            if "mcp" not in current_retrievers:
                current_retrievers.append("mcp")
                self.cfg.retrievers = current_retrievers
        else:
            # 正经注释：如果配置中没有检索器，则仅使用 MCP
            # 大白话注释：如果之前啥搜索引擎都没配，那就只用 MCP
            self.cfg.retrievers = ["mcp"]

        # 正经注释：保存配置供 MCP 检索器后续使用
        # 大白话注释：把外部工具的配置信息存好，后面搜索的时候要用
        self.mcp_configs = mcp_configs

    async def _log_event(self, event_type: str, **kwargs):
        """
        统一日志事件处理器

        【正经注释】
        内部日志分发方法，根据事件类型调用 log_handler 对应的回调。
        同时使用 Python logging 模块作为备份日志通道。
        采用 try-except 保护，确保日志异常不会中断研究流程。

        【大白话注释】
        这是"记录日志"的方法，把研究过程中的每一步都记下来。
        - 如果有人"监听"日志（比如前端界面），就把事件通知给他
        - 同时也用 Python 自带的日志系统写一份备份
        - 就算日志出错了也不影响正常研究

        Args:
            event_type: 事件类型（大白话：发生了什么事）
                - "tool": 工具调用事件
                - "action": 代理动作事件
                - "research": 研究步骤事件
            **kwargs: 事件详情参数（大白话：事件的具体信息）
        """
        if self.log_handler:
            try:
                # 正经注释：根据事件类型分发到 log_handler 的不同回调方法
                # 大白话注释：不同类型的日志用不同的方式处理
                if event_type == "tool":
                    await self.log_handler.on_tool_start(kwargs.get('tool_name', ''), **kwargs)
                elif event_type == "action":
                    await self.log_handler.on_agent_action(kwargs.get('action', ''), **kwargs)
                elif event_type == "research":
                    await self.log_handler.on_research_step(kwargs.get('step', ''), kwargs.get('details', {}))

                # 正经注释：使用 Python logging 作为备份日志通道，确保事件不丢失
                # 大白话注释：再写一份到 Python 的日志系统里，以防万一
                import logging
                research_logger = logging.getLogger('research')
                research_logger.info(f"{event_type}: {json.dumps(kwargs, default=str)}")

            except Exception as e:
                # 正经注释：日志异常不应中断研究流程，仅记录错误
                # 大白话注释：日志出错了没关系，记下来就行，别影响正常工作
                import logging
                logging.getLogger('research').error(f"Error in _log_event: {e}", exc_info=True)

    async def conduct_research(self, on_progress=None):
        """
        执行完整的研究流程

        【正经注释】
        研究系统的核心编排方法，执行以下流程：
        1. 记录研究开始事件
        2. 若为深度研究类型（DeepResearch），转入专用处理流程
        3. 若未指定代理，调用 choose_agent 自动选择合适的研究代理和角色
        4. 通过 ResearchConductor 执行搜索、抓取、上下文整理
        5. 若启用图片生成，在报告生成前预先生成配图

        所有步骤通过 _log_event 记录，支持 WebSocket 实时推送进度。

        【大白话注释】
        这就是"开始做研究"的主入口！整个流程是：
        1. 先打个招呼"研究开始了"
        2. 如果是深度研究模式，走专门的深度研究通道
        3. 如果没指定研究员，先自动挑一个合适的（比如选"科技专家"来研究技术问题）
        4. 让研究员去搜资料、抓网页、整理素材
        5. 如果开了图片生成，就提前把配图也准备好

        Args:
            on_progress: 进度回调函数（大白话：深度研究时用来汇报进度的）

        Returns:
            累积的研究上下文（大白话：搜集到的所有研究素材）
        """
        # 正经注释：记录研究开始事件，包含查询、报告类型、代理等元信息
        # 大白话注释：先记个日志——"研究开始啦，问题是xxx"
        await self._log_event("research", step="start", details={
            "query": self.query,
            "report_type": self.report_type,
            "agent": self.agent,
            "role": self.role
        })

        # 正经注释：深度研究类型走独立处理流程，支持递归树状探索
        # 大白话注释：如果是"深度研究"模式，就交给专门的深度研究模块去处理
        if self.report_type == ReportType.DeepResearch.value and self.deep_researcher:
            self._current_step = "deep_research"
            return await self._handle_deep_research(on_progress)

        # 【正经注释】
        # 代理选择阶段：如果未预设代理和角色，则通过 LLM 分析查询内容，
        # 自动选择最合适的研究代理类型（如科技、金融、医疗等）。
        # 【大白话注释】
        # 如果还没指定"谁来研究"，就让 AI 看看这个问题适合什么"专家"来做
        if not (self.agent and self.role):
            self._current_step = "agent_selection"
            await self._log_event("action", action="choose_agent")
            self.agent, self.role = await choose_agent(
                query=self.query,
                cfg=self.cfg,
                parent_query=self.parent_query,
                cost_callback=self.add_costs,
                headers=self.headers,
                prompt_family=self.prompt_family,
                **self.kwargs,
            )
            await self._log_event("action", action="agent_selected", details={
                "agent": self.agent,
                "role": self.role
            })

        # 正经注释：执行研究流程——搜索、抓取、上下文整理
        # 大白话注释：让研究员去搜资料，把所有有用的素材收集起来
        await self._log_event("research", step="conducting_research", details={
            "agent": self.agent,
            "role": self.role
        })
        self._current_step = "research"
        self.context = await self.research_conductor.conduct_research()   #把所有子查询得到的 拼起来成为一个str

        await self._log_event("research", step="research_completed", details={
            "context_length": len(self.context)
        })

        # 【正经注释】
        # 图片预生成阶段：在报告生成前执行，提升用户体验。
        # 将上下文列表转换为字符串供图片分析使用，生成与内容相关的配图。
        # 【大白话注释】
        # 如果开了"自动配图"功能，就在写报告之前先把图画好。
        # 这样写报告的时候就可以直接把图插进去了，不用临时等。
        self.available_images = []
        if self.image_generator and self.image_generator.is_enabled():
            await self._log_event("research", step="planning_images")
            # 正经注释：将上下文列表拼接为字符串，便于图片生成器分析内容
            # 大白话注释：把所有素材拼成一段文字，让"画师"看看需要画什么图
            context_str = "\n\n".join(self.context) if isinstance(self.context, list) else str(self.context)
            self.available_images = await self.image_generator.plan_and_generate_images(
                context=context_str,
                query=self.query,
                research_id=self._generate_research_id(),
            )
            await self._log_event("research", step="images_pre_generated", details={
                "images_count": len(self.available_images)
            })

        return self.context

    async def _handle_deep_research(self, on_progress=None):
        """
        处理深度研究模式的执行与日志记录

        【正经注释】
        深度研究的专用处理流程，使用 DeepResearchSkill 进行递归树状探索。
        支持 breadth（广度）和 depth（深度）两个维度控制研究范围，
        通过 concurrency_limit 控制并行搜索数量。
        完成后统计总成本并记录详细的完成日志。

        【大白话注释】
        深度研究就是"刨根问底"模式：
        - 不只是搜一次，而是像树一样不断往下展开子问题
        - breadth 控制每层展开几个分支
        - depth 控制往深了挖几层
        - 最后把所有挖到的素材汇总，算一下总共花了多少钱

        Args:
            on_progress: 进度回调函数（大白话：用来实时汇报"搜到第几层了"）

        Returns:
            深度研究累积的上下文（大白话：所有层级搜到的素材）
        """
        # 正经注释：记录深度研究初始化配置
        # 大白话注释：先记个日志，说明深度研究的参数配置（搜多宽、多深、并行几个）
        await self._log_event("research", step="deep_research_initialize", details={
            "type": "deep_research",
            "breadth": self.deep_researcher.breadth,
            "depth": self.deep_researcher.depth,
            "concurrency": self.deep_researcher.concurrency_limit
        })

        # 正经注释：记录深度研究正式开始
        # 大白话注释：日志——"深度研究正式开始！"
        await self._log_event("research", step="deep_research_start", details={
            "query": self.query,
            "breadth": self.deep_researcher.breadth,
            "depth": self.deep_researcher.depth,
            "concurrency": self.deep_researcher.concurrency_limit
        })

        # 正经注释：执行深度研究，获取累积上下文
        # 大白话注释：开始挖！把所有层级搜到的资料都收回来
        self.context = await self.deep_researcher.run(on_progress=on_progress)

        # 正经注释：获取研究总成本
        # 大白话注释：算算总共花了多少钱
        total_costs = self.get_costs()

        # 正经注释：记录深度研究完成事件，包含上下文长度、访问 URL 数和总成本
        # 大白话注释：日志——"深度研究搞定了！收集了多少素材、看了多少网页、花了多少钱"
        await self._log_event("research", step="deep_research_complete", details={
            "context_length": len(self.context),
            "visited_urls": len(self.visited_urls),
            "total_costs": total_costs
        })

        # 正经注释：记录最终成本更新事件
        # 大白话注释：再记一笔费用明细
        await self._log_event("research", step="cost_update", details={
            "cost": total_costs,
            "total_cost": total_costs,
            "research_type": "deep_research"
        })

        return self.context

    async def write_report(
        self,
        existing_headers: list = [],
        relevant_written_contents: list = [],
        ext_context=None,
        custom_prompt="",
    ) -> str:
        """
        生成研究报告

        【正经注释】
        调用 ReportGenerator 生成结构化的研究报告。
        支持传入外部上下文替代内部积累的研究素材，以及自定义提示词引导生成方向。
        如果在 conduct_research 阶段预生成了图片，会自动嵌入报告中。
        通过 existing_headers 参数避免子报告之间的标题重复。

        【大白话注释】
        "写报告"的方法——把搜集到的素材整理成一份正式的研究报告。
        - 可以用自己搜的素材，也可以用外部传入的素材
        - 如果之前提前画好了配图，会自动把图插到报告里
        - 可以给写手一些特别的要求（custom_prompt）

        Args:
            existing_headers: 已有标题列表，避免重复（大白话：已经写过的标题，别再写一遍）
            relevant_written_contents: 已写内容列表，供参考（大白话：之前写过的段落，写的时候参考一下）
            ext_context: 外部上下文（大白话：不用自己搜的素材，直接用你给的）
            custom_prompt: 自定义提示词（大白话：给写手的特别指示）

        Returns:
            str: 生成的报告文本（大白话：写好的报告，Markdown 格式）
        """
        # 正经注释：标记是否有预生成的图片可用
        # 大白话注释：看看之前有没有提前画好图
        has_available_images = bool(self.available_images)

        self._current_step = "report_writing"
        await self._log_event("research", step="writing_report", details={
            "existing_headers": existing_headers,
            "context_source": "external" if ext_context else "internal",
            "available_images_count": len(self.available_images),
        })

        # 正经注释：调用报告生成器，传入上下文和预生成图片
        # 大白话注释：让"写手"开始写报告，把素材和配图都交给他
        report = await self.report_generator.write_report(
            existing_headers=existing_headers,
            relevant_written_contents=relevant_written_contents,
            ext_context=ext_context or self.context,  # 正经注释：优先使用外部上下文，否则用内部素材
            custom_prompt=custom_prompt,
            available_images=self.available_images,
        )

        await self._log_event("research", step="report_completed", details={
            "report_length": len(report),
            "images_embedded": len(self.available_images) if has_available_images else 0,
        })
        return report

    async def write_report_conclusion(self, report_body: str) -> str:
        """
        生成报告结论部分

        【正经注释】
        基于报告正文内容，通过 LLM 生成总结性结论段落。
        结论应涵盖研究发现、关键见解和未来展望。

        【大白话注释】
        给报告写一个"总结"——看了报告的正文，归纳出核心结论。
        就像论文最后的"结论"章节。

        Args:
            report_body: 报告正文（大白话：已经写好的报告主体内容）

        Returns:
            str: 结论文本（大白话：写好的总结段落）
        """
        await self._log_event("research", step="writing_conclusion")
        conclusion = await self.report_generator.write_report_conclusion(report_body)
        await self._log_event("research", step="conclusion_completed")
        return conclusion

    async def write_introduction(self) -> str:
        """
        生成报告引言部分

        【正经注释】
        通过 LLM 生成研究报告的开篇引言，介绍研究背景、目的和概览。
        引言应概述研究范围和报告结构，为读者建立预期。

        【大白话注释】
        给报告写一个"开头"——介绍研究什么、为什么要研究、报告大概讲了啥。
        就像论文前面的"引言"章节。

        Returns:
            str: 引言文本（大白话：写好的开头段落）
        """
        await self._log_event("research", step="writing_introduction")
        intro = await self.report_generator.write_introduction()
        await self._log_event("research", step="introduction_completed")
        return intro

    async def quick_search(self, query: str, query_domains: list[str] = None, aggregated_summary: bool = False) -> list[Any] | str:
        """
        快速搜索（不走完整研究流程）

        【正经注释】
        轻量级搜索方法，仅执行单次搜索操作，不触发代理选择、上下文管理等完整研究流程。
        支持两种返回模式：原始搜索结果列表 或 经 LLM 综合的摘要文本。
        适用于需要快速获取信息的场景，如实时问答、辅助决策等。

        【大白话注释】
        这就是"随手搜一下"——不走完整的研究流程，直接搜完就给你结果。
        - 默认返回搜索结果列表（一堆标题、内容、链接）
        - 如果 aggregated_summary=True，会让 AI 把搜索结果总结成一段话
        适合只需要快速了解一下的场景。

        Args:
            query: 搜索查询（大白话：想搜什么）
            query_domains: 限制搜索的域名（大白话：只在特定网站上搜）
            aggregated_summary: 是否返回综合摘要（大白话：要不要让 AI 帮你总结一下）

        Returns:
            搜索结果列表 或 摘要字符串（大白话：要么是一堆搜索结果，要么是一段总结）
        """
        # 正经注释：使用第一个检索器执行搜索
        # 大白话注释：用配好的搜索引擎搜一下
        search_results = await get_search_results(query, self.retrievers[0], query_domains=query_domains)

        if not aggregated_summary:
            return search_results

        # 正经注释：将搜索结果格式化为带编号的文本，作为 LLM 摘要的输入上下文
        # 大白话注释：把搜索结果拼成一段文字，准备让 AI 来总结
        context = ""
        for i, result in enumerate(search_results, 1):
            context += f"[{i}] {result.get('title', '')}: {result.get('content', '')} ({result.get('url', '')})\n\n"

        # 正经注释：构建快速摘要提示词，调用 SMART_LLM 生成综合摘要
        # 大白话注释：让 AI 把这些搜索结果总结成一段话
        prompt = self.prompt_family.generate_quick_summary_prompt(query, context)

        summary = await create_chat_completion(
            model=self.cfg.smart_llm_model,
            messages=[{"role": "user", "content": prompt}],
            llm_provider=self.cfg.smart_llm_provider,
            max_tokens=self.cfg.smart_token_limit,
            llm_kwargs=self.cfg.llm_kwargs,
            cost_callback=self.add_costs
        )

        return summary

    async def get_subtopics(self):
        """
        生成研究子课题

        【正经注释】
        委托 ReportGenerator 基于研究查询生成子课题列表。
        用于 DetailedReport 类型，将复杂查询分解为可独立研究的子主题。

        【大白话注释】
        把一个大问题拆成几个小问题来分别研究。
        比如"AI 发展现状"可以拆成"大模型"、"自动驾驶"、"医疗 AI"等。

        Returns:
            list: 子课题列表（大白话：拆分出来的小问题清单）
        """
        return await self.report_generator.get_subtopics()

    async def get_draft_section_titles(self, current_subtopic: str) -> list[str]:
        """
        为子课题生成草稿章节标题

        【正经注释】
        针对指定的子课题，通过 LLM 生成报告的章节标题列表。
        用于 DetailedReport 的分章节写作流程。

        【大白话注释】
        给某个小问题列一个"写作提纲"——比如要写哪几个小节。

        Args:
            current_subtopic: 当前子课题（大白话：正在研究的那个小问题）

        Returns:
            list[str]: 章节标题列表（大白话：小节的标题清单）
        """
        return await self.report_generator.get_draft_section_titles(current_subtopic)

    async def get_similar_written_contents_by_draft_section_titles(
        self,
        current_subtopic: str,
        draft_section_titles: list[str],
        written_contents: list[dict],
        max_results: int = 10
    ) -> list[str]:
        """
        根据章节标题查找已写过的相似内容

        【正经注释】
        在已写内容中进行语义搜索，找到与当前章节标题相似的段落。
        用于 DetailedReport 流程中避免重复写作，保持内容连贯性。
        通过 ContextManager 的向量检索实现语义匹配。

        【大白话注释】
        写报告前先看看之前写过什么相关的内容，避免"车轱辘话来回说"。
        用 AI 来理解含义，找到语义相似（不一定是字面相同）的内容。

        Args:
            current_subtopic: 当前子课题（大白话：现在在写哪个小问题）
            draft_section_titles: 草稿章节标题（大白话：这节打算叫什么名字）
            written_contents: 已写内容列表（大白话：之前已经写好的段落）
            max_results: 最多返回几条（大白话：最多找几条相似的）

        Returns:
            list[str]: 相似内容列表（大白话：之前写过的相关段落）
        """
        return await self.context_manager.get_similar_written_contents_by_draft_section_titles(
            current_subtopic,
            draft_section_titles,
            written_contents,
            max_results
        )

    # ==================== 工具方法 ====================
    # 正经注释：以下为数据访问和状态管理的辅助方法
    # 大白话注释：下面这些就是"取东西"和"记东西"的小工具

    def get_research_images(self, top_k: int = 10) -> list[dict[str, Any]]:
        """
        获取研究过程中收集的图片

        【正经注释】
        返回研究过程中收集的前 top_k 张图片。
        图片来源包括网页抓取和 AI 生成。

        【大白话注释】
        把研究中找到的或 AI 画的图片拿出来，默认最多拿 10 张。

        Args:
            top_k: 返回数量上限（大白话：最多拿几张）

        Returns:
            list[dict]: 图片信息列表（大白话：图片的详细信息）
        """
        return self.research_images[:top_k]

    def add_research_images(self, images: list[dict[str, Any]]) -> None:
        """
        添加研究图片

        【正经注释】
        将图片字典追加到研究图片集合中。
        通常在抓取网页或生成图片后调用。

        【大白话注释】
        把新找到的图片存起来。

        Args:
            images: 图片字典列表（大白话：要存的图片信息）
        """
        self.research_images.extend(images)

    def get_research_sources(self) -> list[dict[str, Any]]:
        """
        获取所有研究来源

        【正经注释】
        返回研究过程中抓取的所有来源数据，每条包含标题、内容和图片信息。

        【大白话注释】
        把所有用过的资料来源拿出来。

        Returns:
            list[dict]: 来源字典列表（大白话：所有资料来源的详细信息）
        """
        return self.research_sources

    def add_research_sources(self, sources: list[dict[str, Any]]) -> None:
        """
        添加研究来源

        【正经注释】
        将来源数据追加到研究来源集合中。
        每条来源应包含 title、content 等字段。

        【大白话注释】
        把新找到的资料来源存起来。

        Args:
            sources: 来源字典列表（大白话：要存的资料来源）
        """
        self.research_sources.extend(sources)

    def add_references(self, report_markdown: str, visited_urls: set) -> str:
        """
        给报告添加参考文献

        【正经注释】
        在 Markdown 报告末尾追加参考文献部分，列出所有访问过的 URL。
        自动去重并格式化为引用列表。

        【大白话注释】
        在报告最后加上"参考资料"——把看过的网页链接列出来。

        Args:
            report_markdown: 报告 Markdown 文本（大白话：报告内容）
            visited_urls: 访问过的 URL 集合（大白话：看过的网页链接）

        Returns:
            str: 带参考文献的报告（大白话：加了"参考资料"后的报告）
        """
        return add_references(report_markdown, visited_urls)

    def extract_headers(self, markdown_text: str) -> list[dict]:
        """
        提取 Markdown 标题

        【正经注释】
        解析 Markdown 文本，提取所有标题层级和内容。
        返回按出现顺序排列的标题字典列表。

        【大白话注释】
        把报告里所有的标题挑出来——比如"一、概述"、"1.1 背景"这些。

        Args:
            markdown_text: Markdown 文本（大白话：报告内容）

        Returns:
            list[dict]: 标题字典列表（大白话：所有标题的信息）
        """
        return extract_headers(markdown_text)

    def extract_sections(self, markdown_text: str) -> list[dict]:
        """
        提取 Markdown 章节

        【正经注释】
        解析 Markdown 文本，按标题拆分为独立章节。
        每个章节包含标题和对应的内容。

        【大白话注释】
        把报告按标题切成一段一段的——每段包含标题和下面的内容。

        Args:
            markdown_text: Markdown 文本（大白话：报告内容）

        Returns:
            list[dict]: 章节字典列表（大白话：切成一段段的内容）
        """
        return extract_sections(markdown_text)

    def table_of_contents(self, markdown_text: str) -> str:
        """
        生成目录

        【正经注释】
        从 Markdown 报告中提取标题层级，生成带缩进的目录（TOC）。
        支持多级标题嵌套显示。

        【大白话注释】
        自动给报告生成一个"目录"——就是报告开头那种"一、xxx ... 1"的东西。

        Args:
            markdown_text: Markdown 文本（大白话：报告内容）

        Returns:
            str: 目录 Markdown 文本（大白话：生成的目录）
        """
        return table_of_contents(markdown_text)

    def get_source_urls(self) -> list:
        """
        获取所有访问过的来源 URL

        【正经注释】
        返回研究过程中访问过的所有网页 URL 列表。
        用于报告引用和来源追溯。

        【大白话注释】
        把研究中看过的所有网页链接列出来。

        Returns:
            list: URL 字符串列表（大白话：所有看过的网页链接）
        """
        return list(self.visited_urls)

    def get_research_context(self) -> list:
        """
        获取累积的研究上下文

        【正经注释】
        返回研究过程中积累的所有上下文数据。
        上下文由 ResearchConductor 在搜索和抓取过程中填充。

        【大白话注释】
        把搜集到的所有研究素材拿出来。

        Returns:
            list: 上下文条目列表（大白话：所有搜集到的素材）
        """
        return self.context

    def get_costs(self) -> float:
        """
        获取 API 调用总费用

        【正经注释】
        返回研究过程中所有 API 调用的累计费用（美元）。
        包括 LLM 调用、Embedding 计算、搜索 API 等所有成本。

        【大白话注释】
        看看这次研究总共花了多少钱。

        Returns:
            float: 总费用（美元）（大白话：花了多少美元）
        """
        return self.research_costs

    def get_step_costs(self) -> dict[str, float]:
        """
        获取各步骤的费用明细

        【正经注释】
        返回按研究步骤分类的费用明细字典。
        键为步骤名称（如 "agent_selection"、"research"、"report_writing"），值为该步骤的费用。

        【大白话注释】
        看看每一步分别花了多少钱——选研究员花了多少、搜资料花了多少、写报告花了多少。

        Returns:
            dict: 步骤名称到费用的映射（大白话：每一步的花费明细）
        """
        return dict(self.step_costs)

    def set_verbose(self, verbose: bool) -> None:
        """
        设置详细日志模式

        【正经注释】
        控制是否输出详细的研究过程日志。
        同步更新 Config 对象和实例属性。

        【大白话注释】
        决定要不要打印详细的运行过程。开 verbose 就像开了"字幕"，每一步都告诉你。

        Args:
            verbose: 是否启用详细输出（大白话：True=开字幕，False=关字幕）
        """
        self.verbose = verbose

    def add_costs(self, cost: float) -> None:
        """
        累加 API 调用费用

        【正经注释】
        将本次 API 调用的费用累加到总成本和当前步骤成本中。
        通过 _current_step 属性确定费用归属的研究步骤。
        如果配置了 log_handler，会触发 cost_update 日志事件。

        【大白话注释】
        记一笔账——"这次调 AI 接口花了 X 美元"。
        总账和当前步骤的账本都会更新。
        如果有人"监听"的话，还会通知他"又花了多少钱"。

        Args:
            cost: 费用金额（美元）（大白话：花了多少美元）

        Raises:
            ValueError: 如果 cost 不是数字（大白话：传入的不是数字就报错）
        """
        # 正经注释：类型校验，防止非数字值导致后续计算异常
        # 大白话注释：先检查传入的值是不是数字，不是就报错
        if not isinstance(cost, (float, int)):
            raise ValueError("Cost must be an integer or float")

        # 正经注释：累加到总成本
        # 大白话注释：更新总账本
        self.research_costs += cost

        # 正经注释：将费用归属到当前步骤
        # 大白话注释：更新当前步骤的账本
        step = self._current_step
        self.step_costs[step] = self.step_costs.get(step, 0.0) + cost

        # 正经注释：如果配置了日志处理器，记录费用更新事件
        # 大白话注释：如果有人在"监听"，就通知他费用变了
        if self.log_handler:
            self._log_event("research", step="cost_update", details={
                "cost": cost,
                "total_cost": self.research_costs,
                "step_name": step,
            })
if __name__ == '__main__':
    """
    【调试/测试入口】

    正经注释：用于本地调试 GPTResearcher 的完整研究流程。
    包含：环境加载 → 配置检查 → 研究执行 → 报告生成 → 费用统计。
    自动从项目根目录的 .env 文件加载环境变量。

    大白话注释：直接跑这个文件，就能看到整个研究过程是咋跑的。
    会自动读取 .env 文件里的 API Key，不用手动设环境变量。
    从项目根目录运行：python -m gpt_researcher.agent
    """
    import asyncio
    import time

    # 正经注释：使用 python-dotenv 自动加载 .env 文件
    # 大白话注释：一行搞定，从 .env 读 API Key
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    # ==================== 分隔线 ====================
    print("=" * 60)
    print("  🧪 GPT Researcher 调试模式")
    print("=" * 60)

    # -------------------- 第一步：配置检查 --------------------
    print("\n📌 第一步：检查环境变量和 API Key...")

    # 正经注释：检查必要的 API Key 是否已配置
    # 大白话注释：看看你有没有配好 API Key
    api_keys = {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY"),
    }
    for key_name, key_value in api_keys.items():
        status = "✅ 已配置" if key_value else "❌ 未配置"
        masked = key_value[:8] + "..." if key_value else "无"
        print(f"  {key_name}: {status} ({masked})")

    missing_keys = [k for k, v in api_keys.items() if not v]
    if missing_keys:
        print(f"\n⚠️  缺少必要的环境变量: {', '.join(missing_keys)}")
        print("  请先设置环境变量后再运行，例如：")
        print("  export OPENAI_API_KEY=sk-xxxxx")
        print("  export TAVILY_API_KEY=tvly-xxxxx")
        print("\n  提示：你也可以在 .env 文件或 config.json 中配置。")
        exit(1)

    # -------------------- 第二步：创建 GPTResearcher 实例 --------------------
    print("\n📌 第二步：创建 GPTResearcher 实例...")

    # 正经注释：设置研究查询，可按需修改
    # 大白话注释：你想研究什么？改下面这个字符串就行
    test_query = "Python 和 JavaScript 在 2025 年的发展趋势对比"

    researcher = GPTResearcher(
        query=test_query,
        report_type=ReportType.ResearchReport.value,  # 正经注释：完整研究报告 / 大白话注释：最详细的报告类型
        report_format="markdown",
        report_source=ReportSource.Web.value,          # 正经注释：从网络搜索 / 大白话注释：上网搜资料
        tone=Tone.Objective,                            # 正经注释：客观语气 / 大白话注释：不偏不倚
        verbose=True,
    )

    # 正经注释：打印实例的关键属性，验证初始化是否正确
    # 大白话注释：看看"总指挥"准备好了没有
    print(f"  研究问题: {researcher.query}")
    print(f"  报告类型: {researcher.report_type}")
    print(f"  报告来源: {researcher.report_source}")
    print(f"  报告格式: {researcher.report_format}")
    print(f"  语气: {researcher.tone}")
    print(f"  检索器数量: {len(researcher.retrievers) if researcher.retrievers else 0}")
    print(f"  MCP 策略: {researcher.mcp_strategy}")
    print(f"  配置文件中的模型: {researcher.cfg.smart_llm_model}")
    print(f"  ✅ GPTResearcher 实例创建成功！")

    # -------------------- 第三步：执行研究 --------------------
    print(f"\n📌 第三步：开始执行研究... (查询: \"{test_query}\")")
    print("-" * 60)

    async def run_research():
        """正经注释：异步执行完整研究流程 / 大白话注释：开始干活！"""
        start_time = time.time()

        # 3.1 正经注释：执行研究，收集上下文
        # 3.1 大白话注释：让研究员去搜资料
        print("\n  🔍 [阶段1] 正在选择代理并执行研究...")
        context = await researcher.conduct_research()

        elapsed_research = time.time() - start_time
        print(f"\n  ✅ [阶段1] 研究完成！耗时: {elapsed_research:.2f} 秒")
        print(f"  📊 收集到的上下文数量: {len(context)}")
        print(f"  📊 访问过的 URL 数量: {len(researcher.visited_urls)}")

        # 打印上下文摘要（只打印前几条，避免刷屏）
        if context:
            print("\n  📄 上下文内容预览（前 3 条）:")
            for i, ctx in enumerate(context[:3]):
                preview = str(ctx)[:150].replace("\n", " ")
                print(f"    [{i+1}] {preview}...")

        # 3.2 正经注释：生成研究报告
        # 3.2 大白话注释：让写手开始写报告
        print(f"\n  ✍️  [阶段2] 正在生成研究报告...")
        report = await researcher.write_report()

        elapsed_total = time.time() - start_time
        print(f"\n  ✅ [阶段2] 报告生成完成！")

        # 3.3 正经注释：生成引言和结论
        # 3.3 大白话注释：写开头和结尾
        print(f"\n  📝 [阶段3] 正在生成引言和结论...")
        introduction = await researcher.write_introduction()
        conclusion = await researcher.write_report_conclusion(report)

        # -------------------- 第四步：输出结果 --------------------
        print("\n" + "=" * 60)
        print("  📋 研究结果")
        print("=" * 60)

        print(f"\n  ⏱️  总耗时: {elapsed_total:.2f} 秒")
        print(f"  💰 总费用: ${researcher.get_costs():.6f}")

        # 打印费用明细
        step_costs = researcher.get_step_costs()
        if step_costs:
            print("\n  💰 费用明细:")
            for step_name, cost in step_costs.items():
                print(f"    - {step_name}: ${cost:.6f}")

        # 打印报告预览
        print(f"\n  📝 报告预览（前 500 字符）:")
        print("  " + "-" * 50)
        preview = report[:500] if len(report) > 500 else report
        for line in preview.split("\n"):
            print(f"  {line}")
        if len(report) > 500:
            print(f"  ... (共 {len(report)} 字符)")

        # 打印引言和结论预览
        if introduction:
            print(f"\n  📝 引言预览（前 200 字符）:")
            intro_preview = introduction[:200].replace("\n", " ")
            print(f"  {intro_preview}...")
        if conclusion:
            print(f"\n  📝 结论预览（前 200 字符）:")
            concl_preview = conclusion[:200].replace("\n", " ")
            print(f"  {concl_preview}...")

        # 打印来源 URL
        source_urls = researcher.get_source_urls()
        if source_urls:
            print(f"\n  🔗 参考来源 ({len(source_urls)} 个):")
            for i, url in enumerate(source_urls[:10], 1):
                print(f"    [{i}] {url}")
            if len(source_urls) > 10:
                print(f"    ... 还有 {len(source_urls) - 10} 个")

        print("\n" + "=" * 60)
        print("  🏁 调试运行结束！")
        print("=" * 60)

        return report

    # 正经注释：通过 asyncio.run 启动异步研究流程
    # 大白话注释：启动异步任务，开始跑！
    report_result = asyncio.run(run_research())
"""
【正经注释】
GPT Researcher 配置枚举类型定义模块。定义了报告类型（ReportType）、
数据来源（ReportSource）、写作语气（Tone）和提示词族（PromptFamily）等核心枚举，
为系统各模块提供统一的配置选项。

【大白话注释】
这个文件定义了一堆"选项"给你选——比如你要生成什么类型的报告、
从哪里找资料、用什么语气写、用哪套提示词模板，全在这里定义好了。
"""

from enum import Enum  # 正经注释：导入 Python 标准枚举基类 / 大白话注释：Python 自带的枚举工具，用来定义一组固定的选项


class ReportType(Enum):
    """
    【正经注释】
    研究报告输出类型枚举。定义了 GPT Researcher 代理可以生成的不同报告类型，
    每种类型对应不同的输出格式和分析深度。

    【大白话注释】
    报告类型的选择菜单。你要写什么样的报告，就选哪一个。

    Attributes:
        ResearchReport: 标准研究报告，包含全面分析。
        ResourceReport: 资源报告，侧重于列出和描述资源。
        OutlineReport: 大纲报告，提供主题的结构化大纲。
        CustomReport: 用户自定义报告格式。
        DetailedReport: 深度详细分析报告。
        SubtopicReport: 子主题报告，聚焦于特定子主题。
        DeepResearch: 深度研究模式，进行广泛深入的分析。
    """
    ResearchReport = "research_report"  # 正经注释：标准研究报告 / 大白话注释：普通的研究报告
    ResourceReport = "resource_report"  # 正经注释：资源报告 / 大白话注释：主要列资源的报告
    OutlineReport = "outline_report"  # 正经注释：大纲报告 / 大白话注释：只有大纲的报告
    CustomReport = "custom_report"  # 正经注释：自定义报告 / 大白话注释：随你怎么写的报告
    DetailedReport = "detailed_report"  # 正经注释：详细报告 / 大白话注释：特别详细的研究报告
    SubtopicReport = "subtopic_report"  # 正经注释：子主题报告 / 大白话注释：只写某个小话题的报告
    DeepResearch = "deep"  # 正经注释：深度研究 / 大白话注释：挖得很深很深的研究


class ReportSource(Enum):
    """
    【正经注释】
    研究数据来源枚举。定义了研究人员可以从中收集信息以生成报告的不同来源渠道，
    支持网络搜索、本地文件、云存储、向量数据库等多种数据源。

    【大白话注释】
    报告资料的来源选项。你要从哪里找材料，就选哪一个。

    Attributes:
        Web: 从网络搜索和抓取内容。
        Local: 使用本地文档和文件。
        Azure: 使用 Azure Blob 存储文档。
        LangChainDocuments: 使用 LangChain 文档对象。
        LangChainVectorStore: 使用 LangChain 向量存储进行检索。
        Static: 使用预定义的静态内容。
        Hybrid: 组合多种来源类型。
    """
    Web = "web"  # 正经注释：网络搜索 / 大白话注释：从网上搜
    Local = "local"  # 正经注释：本地文件 / 大白话注释：从你电脑上的文件里找
    Azure = "azure"  # 正经注释：Azure 存储 / 大白话注释：从微软云上找
    LangChainDocuments = "langchain_documents"  # 正经注释：LangChain 文档 / 大白话注释：用 LangChain 的文档对象
    LangChainVectorStore = "langchain_vectorstore"  # 正经注释：LangChain 向量存储 / 大白话注释：用向量数据库找
    Static = "static"  # 正经注释：静态内容 / 大白话注释：用写死的内容
    Hybrid = "hybrid"  # 正经注释：混合来源 / 大白话注释：什么来源都用一点


class Tone(Enum):
    """
    【正经注释】
    报告写作语气枚举。定义了生成研究报告时可使用的不同写作风格，
    以匹配目标受众和内容需求。每个枚举值包含对该写作风格的详细描述。

    【大白话注释】
    写报告用什么"腔调"。比如正式的、轻松的、搞笑的、严肃的……随你选。
    每个选项后面都有一段描述，告诉你这个语气是什么样的。
    """
    Objective = "Objective (impartial and unbiased presentation of facts and findings)"  # 正经注释：客观语气 / 大白话注释：就事论事，不带偏见
    Formal = "Formal (adheres to academic standards with sophisticated language and structure)"  # 正经注释：正式语气 / 大白话注释：学术范儿，高大上
    Analytical = (
        "Analytical (critical evaluation and detailed examination of data and theories)"
    )  # 正经注释：分析语气 / 大白话注释：条分缕析，刨根问底
    Persuasive = (
        "Persuasive (convincing the audience of a particular viewpoint or argument)"
    )  # 正经注释：说服语气 / 大白话注释：使劲说服你信某个观点
    Informative = (
        "Informative (providing clear and comprehensive information on a topic)"
    )  # 正经注释：信息语气 / 大白话注释：给你讲清楚讲全面
    Explanatory = "Explanatory (clarifying complex concepts and processes)"  # 正经注释：解释语气 / 大白话注释：把复杂的东西讲明白
    Descriptive = (
        "Descriptive (detailed depiction of phenomena, experiments, or case studies)"
    )  # 正经注释：描述语气 / 大白话注释：详细描述现象和案例
    Critical = "Critical (judging the validity and relevance of the research and its conclusions)"  # 正经注释：批判语气 / 大白话注释：鸡蛋里挑骨头，评判研究成果
    Comparative = "Comparative (juxtaposing different theories, data, or methods to highlight differences and similarities)"  # 正经注释：比较语气 / 大白话注释：把不同的东西放在一起比一比
    Speculative = "Speculative (exploring hypotheses and potential implications or future research directions)"  # 正经注释：推测语气 / 大白话注释：大胆猜测，探索可能性
    Reflective = "Reflective (considering the research process and personal insights or experiences)"  # 正经注释：反思语气 / 大白话注释：回顾研究过程，谈谈感受
    Narrative = (
        "Narrative (telling a story to illustrate research findings or methodologies)"
    )  # 正经注释：叙事语气 / 大白话注释：像讲故事一样写
    Humorous = "Humorous (light-hearted and engaging, usually to make the content more relatable)"  # 正经注释：幽默语气 / 大白话注释：搞笑一点的写法
    Optimistic = "Optimistic (highlighting positive findings and potential benefits)"  # 正经注释：乐观语气 / 大白话注释：往好的方面说
    Pessimistic = (
        "Pessimistic (focusing on limitations, challenges, or negative outcomes)"
    )  # 正经注释：悲观语气 / 大白话注释：往坏的方面说
    Simple = "Simple (written for young readers, using basic vocabulary and clear explanations)"  # 正经注释：简单语气 / 大白话注释：小孩子也能看懂的那种
    Casual = "Casual (conversational and relaxed style for easy, everyday reading)"  # 正经注释：随意语气 / 大白话注释：聊天式的，轻松愉快


class PromptFamily(Enum):
    """
    【正经注释】
    支持的提示词族枚举。不同的提示词族对应不同风格的提示词模板，
    适配不同的模型架构和推理能力。

    【大白话注释】
    提示词模板"套餐"。不同的套餐适合不同的模型，比如默认的、Granite系列的。
    每个套餐里的提示词风格都不一样。
    """
    Default = "default"  # 正经注释：默认提示词族 / 大白话注释：最普通的提示词模板
    Granite = "granite"  # 正经注释：Granite 提示词族 / 大白话注释：IBM Granite 模型的提示词
    Granite3 = "granite3"  # 正经注释：Granite 3 提示词族 / 大白话注释：Granite 第三版
    Granite31 = "granite3.1"  # 正经注释：Granite 3.1 提示词族 / 大白话注释：Granite 3.1 版
    Granite32 = "granite3.2"  # 正经注释：Granite 3.2 提示词族 / 大白话注释：Granite 3.2 版
    Granite33 = "granite3.3"  # 正经注释：Granite 3.3 提示词族 / 大白话注释：Granite 3.3 版

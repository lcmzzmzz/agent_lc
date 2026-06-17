"""
GPT Researcher 的配置管理模块。

【正经注释】
本模块提供 Config 类，用于管理 GPT Researcher 的全部配置项，
包括 LLM 提供商、嵌入模型、检索器以及其他运行参数。
支持从 JSON 配置文件、环境变量和默认值三种来源加载配置，
优先级为：环境变量 > JSON 配置文件 > 默认值。

【大白话注释】
这个文件就是整个项目的"设置中心"，管着用什么模型、怎么搜索、
报告怎么生成等等所有配置。你可以通过环境变量或配置文件来改设置，
环境变量说了算，配置文件次之，啥都不设就用默认的"出厂设置"。
"""

import json  # 正经注释：JSON 解析库，用于读取配置文件 / 大白话注释：用来读 JSON 格式的配置文件
import os  # 正经注释：操作系统接口，用于读取环境变量和文件路径 / 大白话注释：用来读系统的环境变量和拼路径
import warnings  # 正经注释：警告控制模块，用于发出弃用警告 / 大白话注释：用来提醒用户某个配置项快要废掉了
from typing import Any, Dict, List, Type, Union, get_args, get_origin  # 正经注释：类型提示工具，用于类型注解和运行时类型解析 / 大白话注释：帮代码搞清楚类型信息的工具箱

from gpt_researcher.llm_provider.generic.base import ReasoningEfforts  # 正经注释：导入推理努力程度枚举类型 / 大白话注释：导入"模型思考深度"的选项列表（低/中/高）

from .variables.base import BaseConfig  # 正经注释：导入基础配置类型定义 / 大白话注释：导入配置字段的"字段表"
from .variables.default import DEFAULT_CONFIG  # 正经注释：导入默认配置字典 / 大白话注释：导入"出厂默认设置"


class Config:
    """GPT Researcher 的配置管理器。

    【正经注释】
    负责从文件、环境变量和默认值中加载、解析和管理所有配置项。
    提供配置项的类型转换、弃用属性处理以及 LLM/嵌入模型的解析功能。

    Attributes:
        CONFIG_DIR: 配置文件所在目录。
        config_path: 配置文件的路径。
        llm_kwargs: 传递给 LLM 的额外关键字参数。
        embedding_kwargs: 传递给嵌入模型的额外关键字参数。

    【大白话注释】
    这个类就是项目的"大管家"，管着所有设置。
    它会先看看有没有配置文件，再看看有没有环境变量，都没有就用默认值。
    """

    CONFIG_DIR = os.path.join(os.path.dirname(__file__), "variables")  # 正经注释：配置文件目录，位于当前模块下的 variables 子目录 / 大白话注释：告诉程序配置文件放在哪个文件夹里

    def __init__(self, config_path: str | None = None):
        """初始化配置管理器。

        【正经注释】
        加载指定路径的配置文件（可选），依次设置属性、嵌入模型属性、
        LLM 属性，并处理已弃用的配置项。若报告来源非 web，则验证文档路径。

        Args:
            config_path: 可选的 JSON 配置文件路径。

        【大白话注释】
        构造函数，创建配置对象。你可以传一个配置文件路径，
        也可以不传，不传就用默认设置。它会按顺序初始化各种设置。
        """
        self.config_path = config_path  # 正经注释：保存配置文件路径 / 大白话注释：记住用户传进来的配置文件路径
        self.llm_kwargs: Dict[str, Any] = {}  # 正经注释：LLM 额外参数字典 / 大白话注释：给大模型传的额外参数，一开始是空的
        self.embedding_kwargs: Dict[str, Any] = {}  # 正经注释：嵌入模型额外参数字典 / 大白话注释：给向量模型传的额外参数，一开始也是空的

        config_to_use = self.load_config(config_path)  # 正经注释：加载配置，合并默认值 / 大白话注释：去加载配置，看看配置文件里写了啥
        self._set_attributes(config_to_use)  # 正经注释：将配置字典设置为实例属性 / 大白话注释：把配置项一个个挂到 self 上
        self._set_embedding_attributes()  # 正经注释：解析并设置嵌入模型属性 / 大白话注释：解析"用哪个向量模型"
        self._set_llm_attributes()  # 正经注释：解析并设置 LLM 模型属性 / 大白话注释：解析"用哪个大模型"
        self._handle_deprecated_attributes()  # 正经注释：处理已弃用的配置属性 / 大白话注释：兼容旧版的配置方式，提醒用户迁移
        if config_to_use['REPORT_SOURCE'] != 'web':  # 正经注释：若报告来源非 web，则设置文档路径 / 大白话注释：如果要从本地文件生成报告，就需要设置文档目录
          self._set_doc_path(config_to_use)

        # MCP support configuration
        self.mcp_servers = []  # List of MCP server configurations  # 正经注释：MCP 服务器配置列表 / 大白话注释：MCP（工具调用协议）的服务器列表
        self.mcp_allowed_root_paths = []  # Allowed root paths for MCP servers  # 正经注释：MCP 服务器允许访问的根路径列表 / 大白话注释：MCP 服务器能访问哪些本地目录

        # Read from config
        if hasattr(self, 'mcp_servers'):  # 正经注释：从已设置的属性中读取 MCP 配置 / 大白话注释：如果之前已经设了 MCP 配置，就用之前的
            self.mcp_servers = self.mcp_servers
        if hasattr(self, 'mcp_allowed_root_paths'):
            self.mcp_allowed_root_paths = self.mcp_allowed_root_paths

    def _set_attributes(self, config: Dict[str, Any]) -> None:
        """从配置字典设置实例属性。

        【正经注释】
        遍历配置字典，环境变量优先于配置文件值。将所有键转为小写
        后设置为实例属性，以便通过 self.xxx 访问。

        Args:
            config: 配置键值对字典。

        【大白话注释】
        把配置字典里的每一项都挂到 self 上，键名全变小写。
        如果环境变量里也有这个配置，环境变量说了算。
        """
        for key, value in config.items():  # 正经注释：遍历配置字典中的每个键值对 / 大白话注释：一个一个配置项地处理
            env_value = os.getenv(key)  # 正经注释：检查环境变量中是否存在同名配置 / 大白话注释：看看环境变量里有没有设置这个项
            if env_value is not None:  # 正经注释：若环境变量存在，则用环境变量值覆盖 / 大白话注释：环境变量有的话，就用环境变量的值，它优先级最高
                value = self.convert_env_value(key, env_value, BaseConfig.__annotations__[key])
            setattr(self, key.lower(), value)  # 正经注释：将键名转小写后设置为实例属性 / 大白话注释：配置名全变小写，挂到 self 上，比如 RETRIEVER 变成 self.retriever

        # Handle RETRIEVER with default value
        retriever_env = os.environ.get("RETRIEVER", config.get("RETRIEVER", "tavily"))  # 正经注释：获取检索器配置，支持逗号分隔的多个检索器 / 大白话注释：看看用哪个搜索引擎，默认是 tavily
        try:
            self.retrievers = self.parse_retrievers(retriever_env)  # 正经注释：解析检索器字符串为列表 / 大白话注释：把"tavily,google"这样的字符串拆成列表
        except ValueError as e:
            print(f"Warning: {str(e)}. Defaulting to 'tavily' retriever.")  # 正经注释：解析失败时回退到默认检索器 / 大白话注释：搜索引擎名字写错了就用默认的 tavily
            self.retrievers = ["tavily"]

    def _set_embedding_attributes(self) -> None:
        """解析并设置嵌入模型提供商和模型名称。

        【正经注释】
        将 embedding 配置字符串（格式为 "provider:model"）解析为
        独立的提供商和模型名称属性。

        【大白话注释】
        把类似 "openai:text-embedding-3-small" 这样的字符串拆开，
        一个是"谁提供的"（openai），一个是"具体哪个模型"。
        """
        self.embedding_provider, self.embedding_model = self.parse_embedding(
            self.embedding
        )

    def _set_llm_attributes(self) -> None:
        """解析并设置所有 LLM 类型的提供商和模型属性。

        【正经注释】
        分别解析快速 LLM、智能 LLM 和策略 LLM 的配置字符串，
        并设置对应的提供商、模型名称以及推理努力程度。

        【大白话注释】
        项目用三个档位的大模型：快速的（干杂活）、聪明的（写报告）、
        策略的（做规划）。这个方法就是把它们的配置都解析好。
        """
        self.fast_llm_provider, self.fast_llm_model = self.parse_llm(self.fast_llm)  # 正经注释：解析快速 LLM 的提供商和模型 / 大白话注释：解析"干杂活"用的模型
        self.smart_llm_provider, self.smart_llm_model = self.parse_llm(self.smart_llm)  # 正经注释：解析智能 LLM 的提供商和模型 / 大白话注释：解析"写报告"用的聪明模型
        self.strategic_llm_provider, self.strategic_llm_model = self.parse_llm(self.strategic_llm)  # 正经注释：解析策略 LLM 的提供商和模型 / 大白话注释：解析"做规划"用的策略模型
        self.reasoning_effort = self.parse_reasoning_effort(os.getenv("REASONING_EFFORT"))  # 正经注释：解析推理努力程度 / 大白话注释：看看让模型想多深，默认中等

    def _handle_deprecated_attributes(self) -> None:
        """处理已弃用的配置属性并发出警告。

        【正经注释】
        检测并处理旧版配置项（如 EMBEDDING_PROVIDER、LLM_PROVIDER、
        FAST_LLM_MODEL、SMART_LLM_MODEL），发出 FutureWarning 提示
        用户迁移到新的配置方式。

        【大白话注释】
        以前配置模型的方式和现在不一样，这个方法就是兼容老配置的。
        如果你还在用老方式，它会提醒你该换新方式了，但不会直接报错。
        """
        if os.getenv("EMBEDDING_PROVIDER") is not None:  # 正经注释：检测旧的嵌入提供商配置 / 大白话注释：看看有没有用老方式设置向量模型
            warnings.warn(
                "EMBEDDING_PROVIDER is deprecated and will be removed soon. Use EMBEDDING instead.",
                FutureWarning,
                stacklevel=2,
            )
            self.embedding_provider = (
                os.environ["EMBEDDING_PROVIDER"] or self.embedding_provider
            )  # 正经注释：用旧配置覆盖嵌入提供商 / 大白话注释：老方式设置的提供商优先

            embedding_provider = os.environ["EMBEDDING_PROVIDER"]
            if embedding_provider == "ollama":  # 正经注释：Ollama 本地模型 / 大白话注释：用本地部署的 Ollama
                self.embedding_model = os.environ["OLLAMA_EMBEDDING_MODEL"]
            elif embedding_provider == "custom":  # 正经注释：自定义兼容 API / 大白话注释：自己搭的模型服务
                self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "custom")
            elif embedding_provider == "openai":  # 正经注释：OpenAI 官方 / 大白话注释：用 OpenAI 的向量模型
                self.embedding_model = "text-embedding-3-large"
            elif embedding_provider == "azure_openai":  # 正经注释：Azure 托管的 OpenAI / 大白话注释：微软云上的 OpenAI
                self.embedding_model = "text-embedding-3-large"
            elif embedding_provider == "huggingface":  # 正经注释：HuggingFace 开源模型 / 大白话注释：用 HuggingFace 上的开源模型
                self.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
            elif embedding_provider == "gigachat":  # 正经注释：GigaChat 模型 / 大白话注释：俄罗斯的 GigaChat
                self.embedding_model = "Embeddings"
            elif embedding_provider == "google_genai":  # 正经注释：Google Generative AI / 大白话注释：谷歌的 AI 服务
                self.embedding_model = "text-embedding-004"
            else:
                raise Exception("Embedding provider not found.")  # 正经注释：不支持的嵌入提供商 / 大白话注释：这个向量模型服务商没见过，报错

        _deprecation_warning = (
            "LLM_PROVIDER, FAST_LLM_MODEL and SMART_LLM_MODEL are deprecated and "
            "will be removed soon. Use FAST_LLM and SMART_LLM instead."
        )  # 正经注释：统一的弃用警告信息 / 大白话注释：提醒信息——"这些老配置快废了，赶紧换新的"
        if os.getenv("LLM_PROVIDER") is not None:  # 正经注释：检测旧的 LLM 提供商配置 / 大白话注释：看看有没有用老方式设置大模型提供商
            warnings.warn(_deprecation_warning, FutureWarning, stacklevel=2)
            self.fast_llm_provider = (
                os.environ["LLM_PROVIDER"] or self.fast_llm_provider
            )  # 正经注释：用旧配置覆盖快速 LLM 提供商 / 大白话注释：老方式统一设置快速模型提供商
            self.smart_llm_provider = (
                os.environ["LLM_PROVIDER"] or self.smart_llm_provider
            )  # 正经注释：用旧配置覆盖智能 LLM 提供商 / 大白话注释：老方式统一设置智能模型提供商
        if os.getenv("FAST_LLM_MODEL") is not None:  # 正经注释：检测旧的快速 LLM 模型名配置 / 大白话注释：看看有没有用老方式指定快速模型名字
            warnings.warn(_deprecation_warning, FutureWarning, stacklevel=2)
            self.fast_llm_model = os.environ["FAST_LLM_MODEL"] or self.fast_llm_model
        if os.getenv("SMART_LLM_MODEL") is not None:  # 正经注释：检测旧的智能 LLM 模型名配置 / 大白话注释：看看有没有用老方式指定智能模型名字
            warnings.warn(_deprecation_warning, FutureWarning, stacklevel=2)
            self.smart_llm_model = os.environ["SMART_LLM_MODEL"] or self.smart_llm_model

    def _set_doc_path(self, config: Dict[str, Any]) -> None:
        """设置并验证文档路径。

        【正经注释】
        从配置中提取文档路径，并尝试验证路径的有效性。
        验证失败时回退到默认路径。

        Args:
            config: 包含 DOC_PATH 键的配置字典。

        【大白话注释】
        设置本地文档的存放目录。如果路径有问题就用默认的 ./my-docs。
        """
        self.doc_path = config['DOC_PATH']  # 正经注释：从配置字典中获取文档路径 / 大白话注释：拿到文档目录的设置
        if self.doc_path:  # 正经注释：路径非空时进行验证 / 大白话注释：如果设了路径就去检查一下
            try:
                self.validate_doc_path()
            except Exception as e:
                print(f"Warning: Error validating doc_path: {str(e)}. Using default doc_path.")  # 正经注释：验证失败时使用默认路径 / 大白话注释：路径有问题就回退到默认值
                self.doc_path = DEFAULT_CONFIG['DOC_PATH']

    @classmethod
    def load_config(cls, config_path: str | None) -> Dict[str, Any]:
        """按名称加载配置。

        【正经注释】
        从指定路径加载 JSON 配置文件，并与默认配置合并以确保所有键都存在。
        若未指定路径或文件不存在，则返回默认配置。

        Args:
            config_path: 配置文件路径，可为 None。

        Returns:
            合并后的配置字典。

        【大白话注释】
        加载配置文件。如果没有指定文件路径，或者文件找不到，
        就用默认设置。找到了的话，就把自定义设置和默认设置合在一起，
        自定义的覆盖默认的。
        """
        config_path = config_path or os.environ.get("CONFIG_PATH")  # 正经注释：优先使用参数路径，其次从环境变量获取 / 大白话注释：看看有没有传配置文件路径，没传就从环境变量找
        if not config_path:  # 正经注释：无路径时返回默认配置 / 大白话注释：啥都没设就用出厂设置
            return DEFAULT_CONFIG

        # config_path = os.path.join(cls.CONFIG_DIR, config_path)
        if not os.path.exists(config_path):  # 正经注释：文件不存在时回退到默认配置 / 大白话注释：配置文件找不到就用默认的
            if config_path and config_path != "default":
                print(f"Warning: Configuration not found at '{config_path}'. Using default configuration.")  # 正经注释：打印配置文件不存在的警告 / 大白话注释：提醒你配置文件找不到
                if not config_path.endswith(".json"):
                    print(f"Do you mean '{config_path}.json'?")  # 正经注释：提示可能缺少 .json 后缀 / 大白话注释：你是不是忘加 .json 后缀了？
            return DEFAULT_CONFIG

        with open(config_path, "r") as f:  # 正经注释：读取并解析 JSON 配置文件 / 大白话注释：打开配置文件读内容
            custom_config = json.load(f)

        # Merge with default config to ensure all keys are present
        merged_config = DEFAULT_CONFIG.copy()  # 正经注释：复制默认配置作为基础 / 大白话注释：先复制一份默认设置
        merged_config.update(custom_config)  # 正经注释：用自定义配置覆盖默认值 / 大白话注释：再用自定义设置覆盖，确保所有配置项都有值
        return merged_config

    @classmethod
    def list_available_configs(cls) -> List[str]:
        """列出所有可用的配置名称。

        【正经注释】
        扫描配置目录下的 JSON 文件，返回包含 "default" 和
        所有已发现配置名称的列表。

        Returns:
            可用配置名称的列表。

        【大白话注释】
        看看配置目录里有哪些配置文件，把名字都列出来。
        """
        configs = ["default"]  # 正经注释：默认配置始终可用 / 大白话注释：出厂设置肯定有
        for file in os.listdir(cls.CONFIG_DIR):  # 正经注释：遍历配置目录中的文件 / 大白话注释：扫一遍配置文件夹
            if file.endswith(".json"):  # 正经注释：只关注 JSON 配置文件 / 大白话注释：只看 .json 文件
                configs.append(file[:-5])  # Remove .json extension  # 正经注释：去掉 .json 后缀作为配置名 / 大白话注释：把 .json 后缀去掉，比如 my_config.json 变成 my_config
        return configs

    def parse_retrievers(self, retriever_str: str) -> List[str]:
        """解析检索器字符串并验证其有效性。

        【正经注释】
        将逗号分隔的检索器字符串解析为列表，并逐一验证是否为
        已注册的合法检索器名称。

        Args:
            retriever_str: 逗号分隔的检索器名称字符串。

        Returns:
            检索器名称列表。

        Raises:
            ValueError: 包含无效检索器名称时抛出。

        【大白话注释】
        把 "tavily,google,bing" 这样的字符串拆成列表，
        然后检查每个搜索引擎名字是不是合法的，不合法就报错。
        """
        from ..retrievers.utils import get_all_retriever_names  # 正经注释：导入获取所有检索器名称的函数 / 大白话注释：拿一份"合法搜索引擎名单"

        retrievers = [retriever.strip()
                      for retriever in retriever_str.split(",")]  # 正经注释：按逗号分割并去除空白 / 大白话注释：用逗号切开，去掉多余空格
        valid_retrievers = get_all_retriever_names() or []  # 正经注释：获取所有合法检索器名称 / 大白话注释：拿到合法名单
        invalid_retrievers = [r for r in retrievers if r not in valid_retrievers]  # 正经注释：筛选出不合法的检索器 / 大白话注释：找出不在名单里的
        if invalid_retrievers:  # 正经注释：如果存在不合法的检索器则报错 / 大白话注释：有非法名字就报错
            raise ValueError(
                f"Invalid retriever(s) found: {', '.join(invalid_retrievers)}. "
                f"Valid options are: {', '.join(valid_retrievers)}."
            )
        return retrievers

    @staticmethod
    def parse_llm(llm_str: str | None) -> tuple[str | None, str | None]:
        """解析 LLM 字符串为提供商和模型名称。

        【正经注释】
        将 "provider:model" 格式的字符串拆分为 (llm_provider, llm_model) 元组，
        并验证提供商是否受支持。

        Args:
            llm_str: LLM 配置字符串，格式为 "provider:model"。

        Returns:
            (提供商, 模型名称) 元组。

        Raises:
            ValueError: 格式错误或不支持的提供商时抛出。

        【大白话注释】
        把 "openai:gpt-4o-mini" 拆成 ("openai", "gpt-4o-mini")。
        如果冒号前面那个服务商不在支持列表里，或者格式不对，就报错。
        """
        from gpt_researcher.llm_provider.generic.base import _SUPPORTED_PROVIDERS  # 正经注释：导入支持的 LLM 提供商列表 / 大白话注释：拿一份"支持的大模型服务商名单"

        if llm_str is None:  # 正经注释：输入为空时返回空元组 / 大白话注释：啥都没设就返回空
            return None, None
        try:
            llm_provider, llm_model = llm_str.split(":", 1)  # 正经注释：按第一个冒号分割字符串 / 大白话注释：在冒号处切开，"openai:gpt-4o" 变成两部分
            assert llm_provider in _SUPPORTED_PROVIDERS, (  # 正经注释：验证提供商是否受支持 / 大白话注释：检查这个服务商在不在名单里
                f"Unsupported {llm_provider}.\nSupported llm providers are: "
                + ", ".join(_SUPPORTED_PROVIDERS)
            )
            return llm_provider, llm_model
        except ValueError:
            raise ValueError(
                "Set SMART_LLM or FAST_LLM = '<llm_provider>:<llm_model>' "
                "Eg 'openai:gpt-4o-mini'"
            )  # 正经注释：格式错误时提供正确的配置示例 / 大白话注释：格式不对，告诉你正确的写法

    @staticmethod
    def parse_reasoning_effort(reasoning_effort_str: str | None) -> str | None:
        """解析推理努力程度字符串。

        【正经注释】
        验证推理努力程度是否为合法值（如 low/medium/high），
        未指定时默认为 Medium。

        Args:
            reasoning_effort_str: 推理努力程度字符串。

        Returns:
            合法的推理努力程度值。

        Raises:
            ValueError: 非法的推理努力程度时抛出。

        【大白话注释】
        看看推理深度设的是不是合法值（比如 low、medium、high）。
        没设的话默认中等。设了个不认识的就报错。
        """
        if reasoning_effort_str is None:  # 正经注释：未设置时返回默认中等程度 / 大白话注释：没设就默认中等
            return ReasoningEfforts.Medium.value
        if reasoning_effort_str not in [effort.value for effort in ReasoningEfforts]:  # 正经注释：验证是否为合法值 / 大白话注释：检查是不是合法选项
            raise ValueError(f"Invalid reasoning effort: {reasoning_effort_str}. Valid options are: {', '.join([effort.value for effort in ReasoningEfforts])}")
        return reasoning_effort_str

    @staticmethod
    def parse_embedding(embedding_str: str | None) -> tuple[str | None, str | None]:
        """解析嵌入模型字符串为提供商和模型名称。

        【正经注释】
        将 "provider:model" 格式的嵌入配置字符串拆分为
        (embedding_provider, embedding_model) 元组，并验证提供商。

        Args:
            embedding_str: 嵌入配置字符串，格式为 "provider:model"。

        Returns:
            (提供商, 模型名称) 元组。

        Raises:
            ValueError: 格式错误或不支持的提供商时抛出。

        【大白话注释】
        跟 parse_llm 类似，把 "openai:text-embedding-3-small" 拆开，
        检查服务商合不合法。
        """
        from gpt_researcher.memory.embeddings import _SUPPORTED_PROVIDERS  # 正经注释：导入支持的嵌入提供商列表 / 大白话注释：拿一份"支持的向量模型服务商名单"

        if embedding_str is None:  # 正经注释：输入为空时返回空元组 / 大白话注释：啥都没设就返回空
            return None, None
        try:
            embedding_provider, embedding_model = embedding_str.split(":", 1)  # 正经注释：按第一个冒号分割 / 大白话注释：在冒号处切开
            assert embedding_provider in _SUPPORTED_PROVIDERS, (  # 正经注释：验证嵌入提供商 / 大白话注释：看看这个向量模型服务商在不在名单里
                f"Unsupported {embedding_provider}.\nSupported embedding providers are: "
                + ", ".join(_SUPPORTED_PROVIDERS)
            )
            return embedding_provider, embedding_model
        except ValueError:
            raise ValueError(
                "Set EMBEDDING = '<embedding_provider>:<embedding_model>' "
                "Eg 'openai:text-embedding-3-large'"
            )  # 正经注释：格式错误时提供正确的配置示例 / 大白话注释：格式不对，告诉你正确写法

    def validate_doc_path(self):
        """验证文档路径是否存在，不存在则创建。

        【正经注释】
        确保指定路径的文件夹存在，若不存在则递归创建。

        【大白话注释】
        检查文档目录在不在，不在就自动建一个。
        """
        os.makedirs(self.doc_path, exist_ok=True)  # 正经注释：递归创建目录，已存在时不报错 / 大白话注释：创建文件夹，有了就不重复建

    @staticmethod
    def convert_env_value(key: str, env_value: str, type_hint: Type) -> Any:
        """根据类型提示将环境变量值转换为正确的类型。

        【正经注释】
        根据 BaseConfig 中定义的类型注解，将字符串形式的环境变量值
        转换为对应的 Python 类型（bool、int、float、str、list、dict、Union 等）。

        Args:
            key: 配置键名。
            env_value: 环境变量的字符串值。
            type_hint: 期望的 Python 类型。

        Returns:
            类型转换后的值。

        Raises:
            ValueError: 类型不支持或转换失败时抛出。

        【大白话注释】
        环境变量的值都是字符串，但配置项有的是数字、有的是布尔值。
        这个方法就是根据配置表里定义的类型，把字符串变成对应的类型。
        比如把 "true" 变成 True，把 "3" 变成 3。
        """
        origin = get_origin(type_hint)  # 正经注释：获取类型的原始类型（如 Union、List 等） / 大白话注释：看看这个类型是不是 Union、List 之类的"组合类型"
        args = get_args(type_hint)  # 正经注释：获取类型参数（如 Union[str, None] 中的 str 和 None） / 大白话注释：把组合类型拆开看看里面有什么

        if origin is Union:  # 正经注释：处理 Union 联合类型 / 大白话注释：处理"可能是A也可能是B"的类型
            # Handle Union types (e.g., Union[str, None])
            for arg in args:  # 正经注释：逐一尝试每个子类型 / 大白话注释：挨个试试能不能转换
                if arg is type(None):
                    if env_value.lower() in ("none", "null", ""):  # 正经注释：识别 None 值的字符串表示 / 大白话注释：如果值是 "none" 或 "null" 就当空值处理
                        return None
                else:
                    try:
                        return Config.convert_env_value(key, env_value, arg)  # 正经注释：递归尝试转换 / 大白话注释：用子类型再试一次
                    except ValueError:
                        continue
            raise ValueError(f"Cannot convert {env_value} to any of {args}")  # 正经注释：所有子类型都转换失败 / 大白话注释：怎么转都不行，报错

        if type_hint is bool:  # 正经注释：布尔类型转换 / 大白话注释：转布尔值，"true"/"1"/"yes"/"on" 都是 True
            return env_value.lower() in ("true", "1", "yes", "on")
        elif type_hint is int:  # 正经注释：整数类型转换 / 大白话注释：转整数
            return int(env_value)
        elif type_hint is float:  # 正经注释：浮点数类型转换 / 大白话注释：转小数
            return float(env_value)
        elif type_hint in (str, Any):  # 正经注释：字符串或任意类型直接返回 / 大白话注释：字符串就不用转了，原样返回
            return env_value
        elif origin is list or origin is List:  # 正经注释：列表类型，从 JSON 解析 / 大白话注释：列表类型，把 JSON 字符串解析成列表
            return json.loads(env_value)
        elif type_hint is dict:  # 正经注释：字典类型，从 JSON 解析 / 大白话注释：字典类型，把 JSON 字符串解析成字典
            return json.loads(env_value)
        else:
            raise ValueError(f"Unsupported type {type_hint} for key {key}")  # 正经注释：不支持的类型 / 大白话注释：不认识的类型，报错


    def set_verbose(self, verbose: bool) -> None:
        """设置详细输出模式。

        【正经注释】
        控制是否输出详细的运行日志信息。

        Args:
            verbose: 是否启用详细模式。

        【大白话注释】
        控制要不要打印更多运行信息。开了的话你能看到模型在干啥。
        """
        self.llm_kwargs["verbose"] = verbose  # 正经注释：将 verbose 标志写入 LLM 参数字典 / 大白话注释：把"啰嗦模式"开关写到参数里

    def get_mcp_server_config(self, name: str) -> dict:
        """获取指定 MCP 服务器的配置。

        【正经注释】
        根据服务器名称在已配置的 MCP 服务器列表中查找对应的配置信息。

        Args:
            name (str): 要查找的 MCP 服务器名称。

        Returns:
            dict: 服务器配置字典，未找到时返回空字典。

        【大白话注释】
        按名字找一个 MCP 服务器的配置信息。找不到就返回空的。
        """
        if not name or not self.mcp_servers:  # 正经注释：名称为空或无 MCP 服务器时返回空字典 / 大白话注释：名字没给或者没有服务器，直接返回空
            return {}

        for server in self.mcp_servers:  # 正经注释：遍历所有 MCP 服务器配置 / 大白话注释：逐个服务器看
            if isinstance(server, dict) and server.get("name") == name:  # 正经注释：匹配名称 / 大白话注释：找到名字对的那个
                return server

        return {}  # 正经注释：未找到匹配的服务器 / 大白话注释：找了一圈没找到，返回空

"""
GPT Researcher 的嵌入向量提供商管理模块。

【正经注释】
本模块提供 Memory 类，统一管理多种嵌入向量提供商的模型加载和向量生成。
支持 OpenAI、Azure OpenAI、Cohere、Google、Ollama、HuggingFace 等
多种提供商，通过惰性加载按需导入提供商的依赖库。

Supported providers:
    - openai: OpenAI embeddings
    - azure_openai: Azure OpenAI embeddings
    - cohere: Cohere embeddings
    - google_vertexai: Google Vertex AI embeddings
    - google_genai: Google Generative AI embeddings
    - fireworks: Fireworks AI embeddings
    - ollama: Local Ollama embeddings
    - together: Together AI embeddings
    - mistralai: Mistral AI embeddings
    - huggingface: HuggingFace embeddings
    - nomic: Nomic embeddings
    - voyageai: Voyage AI embeddings
    - dashscope: DashScope embeddings
    - bedrock: AWS Bedrock embeddings
    - aimlapi: AIML API embeddings
    - custom: Custom OpenAI-compatible API

【大白话注释】
这个模块负责把文字变成"向量"（一串数字），这样就能比较两段文字有多像。
它支持很多家服务商（OpenAI、谷歌、本地 Ollama 等），你选哪家它就加载哪家。
只有真正要用的时候才会导入对应的库，省得装一堆用不到的东西。
"""

import os  # 正经注释：操作系统接口，用于读取环境变量 / 大白话注释：读环境变量用的
from typing import Any  # 正经注释：任意类型提示 / 大白话注释：类型标注用的

OPENAI_EMBEDDING_MODEL = os.environ.get(
    "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
)  # 正经注释：OpenAI 嵌入模型名称，优先从环境变量读取 / 大白话注释：默认用 OpenAI 的小型向量模型，环境变量里设了就用设的

_SUPPORTED_PROVIDERS = {  # 正经注释：所有受支持的嵌入提供商名称集合 / 大白话注释：支持的向量模型服务商"白名单"
    "openai",
    "azure_openai",
    "cohere",
    "gigachat",
    "google_vertexai",
    "google_genai",
    "fireworks",
    "ollama",
    "together",
    "mistralai",
    "huggingface",
    "nomic",
    "voyageai",
    "dashscope",
    "custom",
    "bedrock",
    "aimlapi",
    "netmind",
    "openrouter",
    "minimax",
}


class Memory:
    """管理嵌入向量生成，用于文档相似度计算和检索。

    【正经注释】
    提供统一的嵌入向量生成接口，支持多种提供商。
    采用惰性加载策略，仅在初始化时导入所需提供商的依赖库。

    Attributes:
        _embeddings: 底层的 LangChain 嵌入模型实例。

    Example:
        ```python
        memory = Memory("openai", "text-embedding-3-small")
        embeddings = memory.get_embeddings()
        ```

    【大白话注释】
    这个类就是"文字变数字"的转换器。你告诉它用哪个服务商、哪个模型，
    它就帮你把文字变成一串数字（向量），这样就能算两段文字有多像了。
    """

    def __init__(self, embedding_provider: str, model: str, **embedding_kwargs: Any):
        """使用指定的嵌入提供商初始化 Memory。

        【正经注释】
        根据提供商名称选择对应的 LangChain 嵌入模型实现，
        按需导入提供商特定的依赖库，并配置 API 密钥和端点。

        Args:
            embedding_provider: 嵌入提供商名称（如 openai、cohere 等）。
            model: 嵌入模型的名称/ID。
            **embedding_kwargs: 传递给嵌入提供商构造函数的额外参数。

        Raises:
            Exception: 嵌入提供商不支持时抛出异常。

        【大白话注释】
        创建"文字变数字"的工具。你要指定用哪家服务（比如 openai）
        和具体模型名，它会自动加载对应的库和配置。
        """
        _embeddings = None  # 正经注释：初始化嵌入实例为空 / 大白话注释：先设为空，等匹配到对应服务商再赋值
        match embedding_provider:
            case "custom":  # 正经注释：自定义 OpenAI 兼容 API（如 LMStudio） / 大白话注释：自己搭的模型服务，兼容 OpenAI 接口
                from langchain_openai import OpenAIEmbeddings

                _embeddings = OpenAIEmbeddings(
                    model=model,
                    openai_api_key=os.getenv("OPENAI_API_KEY", "custom"),
                    openai_api_base=os.getenv(
                        "OPENAI_BASE_URL", "http://localhost:1234/v1"
                    ),  # default for lmstudio  # 正经注释：默认使用 LMStudio 本地地址 / 大白话注释：默认连本地 LMStudio 服务
                    check_embedding_ctx_length=False,
                    **embedding_kwargs,
                )  # quick fix for lmstudio
            case "openai":  # 正经注释：OpenAI 官方嵌入服务 / 大白话注释：用 OpenAI 官方的向量模型
                from langchain_openai import OpenAIEmbeddings

                # Support custom OpenAI-compatible APIs via OPENAI_BASE_URL
                if "openai_api_base" not in embedding_kwargs and os.environ.get("OPENAI_BASE_URL"):  # 正经注释：支持通过环境变量自定义 OpenAI 兼容 API 端点 / 大白话注释：如果设了自定义地址就走自定义地址
                    embedding_kwargs["openai_api_base"] = os.environ["OPENAI_BASE_URL"]

                _embeddings = OpenAIEmbeddings(model=model, **embedding_kwargs)
            case "azure_openai":  # 正经注释：Azure 托管的 OpenAI 嵌入服务 / 大白话注释：用微软云上的 OpenAI 向量模型
                from langchain_openai import AzureOpenAIEmbeddings

                _embeddings = AzureOpenAIEmbeddings(
                    model=model,
                    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                    openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
                    openai_api_version=os.environ.get(
                        "AZURE_OPENAI_API_VERSION",
                        os.environ.get("OPENAI_API_VERSION"),
                    ),
                    **embedding_kwargs,
                )
            case "cohere":  # 正经注释：Cohere 嵌入服务 / 大白话注释：用 Cohere 的向量模型
                from langchain_cohere import CohereEmbeddings

                _embeddings = CohereEmbeddings(model=model, **embedding_kwargs)
            case "google_vertexai":  # 正经注释：Google Vertex AI 嵌入服务 / 大白话注释：用谷歌云 AI 平台的向量模型
                from langchain_google_vertexai import VertexAIEmbeddings

                _embeddings = VertexAIEmbeddings(model=model, **embedding_kwargs)
            case "google_genai":  # 正经注释：Google Generative AI 嵌入服务 / 大白话注释：用谷歌 AI 的向量模型
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                _embeddings = GoogleGenerativeAIEmbeddings(
                    model=model, **embedding_kwargs
                )
            case "fireworks":  # 正经注释：Fireworks AI 嵌入服务 / 大白话注释：用 Fireworks 的向量模型
                from langchain_fireworks import FireworksEmbeddings

                _embeddings = FireworksEmbeddings(model=model, **embedding_kwargs)
            case "gigachat":  # 正经注释：GigaChat 嵌入服务 / 大白话注释：用俄罗斯的 GigaChat 向量模型
                from langchain_gigachat import GigaChatEmbeddings

                _embeddings = GigaChatEmbeddings(model=model, **embedding_kwargs)
            case "ollama":  # 正经注释：Ollama 本地嵌入服务 / 大白话注释：用本地部署的 Ollama 向量模型
                from langchain_ollama import OllamaEmbeddings

                _embeddings = OllamaEmbeddings(
                    model=model,
                    base_url=os.environ["OLLAMA_BASE_URL"],
                    **embedding_kwargs,
                )
            case "together":  # 正经注释：Together AI 嵌入服务 / 大白话注释：用 Together AI 的向量模型
                from langchain_together import TogetherEmbeddings

                _embeddings = TogetherEmbeddings(model=model, **embedding_kwargs)
            case "netmind":  # 正经注释：Netmind 嵌入服务 / 大白话注释：用 Netmind 的向量模型
                from langchain_netmind import NetmindEmbeddings

                _embeddings = NetmindEmbeddings(model=model, **embedding_kwargs)
            case "mistralai":  # 正经注释：Mistral AI 嵌入服务 / 大白话注释：用 Mistral 的向量模型
                from langchain_mistralai import MistralAIEmbeddings

                _embeddings = MistralAIEmbeddings(model=model, **embedding_kwargs)
            case "huggingface":  # 正经注释：HuggingFace 开源嵌入模型 / 大白话注释：用 HuggingFace 上的开源向量模型
                from langchain_huggingface import HuggingFaceEmbeddings

                _embeddings = HuggingFaceEmbeddings(model_name=model, **embedding_kwargs)
            case "nomic":  # 正经注释：Nomic 嵌入服务 / 大白话注释：用 Nomic 的向量模型
                from langchain_nomic import NomicEmbeddings

                _embeddings = NomicEmbeddings(model=model, **embedding_kwargs)
            case "voyageai":  # 正经注释：Voyage AI 嵌入服务 / 大白话注释：用 Voyage AI 的向量模型
                from langchain_voyageai import VoyageAIEmbeddings

                _embeddings = VoyageAIEmbeddings(
                    voyage_api_key=os.environ["VOYAGE_API_KEY"],
                    model=model,
                    **embedding_kwargs,
                )
            case "dashscope":  # 正经注释：阿里云 DashScope 嵌入服务 / 大白话注释：用阿里云的向量模型
                from langchain_community.embeddings import DashScopeEmbeddings

                _embeddings = DashScopeEmbeddings(model=model, **embedding_kwargs)
            case "bedrock":  # 正经注释：AWS Bedrock 嵌入服务 / 大白话注释：用亚马逊云的向量模型
                from langchain_aws.embeddings import BedrockEmbeddings

                _embeddings = BedrockEmbeddings(model_id=model, **embedding_kwargs)
            case "aimlapi":  # 正经注释：AIML API 嵌入服务 / 大白话注释：用 AIML API 的向量模型
                from langchain_openai import OpenAIEmbeddings

                _embeddings = OpenAIEmbeddings(
                    model=model,
                    openai_api_key=os.getenv("AIMLAPI_API_KEY"),
                    openai_api_base=os.getenv("AIMLAPI_BASE_URL", "https://api.aimlapi.com/v1"),
                    **embedding_kwargs,
                )
            case "openrouter":  # 正经注释：OpenRouter 嵌入服务 / 大白话注释：用 OpenRouter 的向量模型
                from langchain_openai import OpenAIEmbeddings

                _embeddings = OpenAIEmbeddings(
                    model=model,
                    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
                    openai_api_base="https://openrouter.ai/api/v1",
                    **embedding_kwargs,
                )
            case "minimax":  # 正经注释：MiniMax 嵌入服务 / 大白话注释：用 MiniMax 的向量模型
                from langchain_openai import OpenAIEmbeddings

                _embeddings = OpenAIEmbeddings(
                    model=model,
                    openai_api_key=os.getenv("MINIMAX_API_KEY"),
                    openai_api_base="https://api.minimax.io/v1",
                    **embedding_kwargs,
                )
            case _:  # 正经注释：未匹配任何已知提供商 / 大白话注释：上面的都不认识，报错
                raise Exception("Embedding not found.")

        self._embeddings = _embeddings  # 正经注释：保存创建的嵌入模型实例 / 大白话注释：把初始化好的向量模型存起来

    def get_embeddings(self):
        """获取已配置的嵌入模型实例。

        【正经注释】
        返回在初始化时创建的 LangChain 嵌入模型实例，
        可用于后续的向量生成和相似度计算。

        Returns:
            LangChain 嵌入模型实例。

        【大白话注释】
        把之前创建好的向量模型返回给你，拿来用就行。
        """
        return self._embeddings

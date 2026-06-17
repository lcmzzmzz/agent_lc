"""
GPT Researcher 的上下文压缩工具模块。

【正经注释】
本模块提供基于嵌入向量相似度的文档压缩和检索功能。
压缩流程：1. 将文档切分为块  2. 按与查询的嵌入相似度过滤  3. 返回最相关的块。
包含三个核心类：VectorstoreCompressor、ContextCompressor、WrittenContentCompressor。

Classes:
    VectorstoreCompressor: 从向量存储中检索上下文。
    ContextCompressor: 使用嵌入相似度压缩原始文档。
    WrittenContentCompressor: 压缩已写过的报告内容段落。

【大白话注释】
这个模块干的事情就是"从一大堆文字里挑出最有用的"。
搜索出来一大堆网页内容，不可能全塞给模型，所以要先过滤：
把文字切成小段，算算每段跟你的问题有多相关，只留最相关的那些。
"""

import asyncio  # 正经注释：异步编程库，用于并发执行压缩操作 / 大白话注释：用来做异步操作，让压缩不阻塞主程序
import os  # 正经注释：操作系统接口，用于读取环境变量 / 大白话注释：用来读环境变量
from typing import Optional  # 正经注释：可选类型提示 / 大白话注释：标注某个参数可以不传

from langchain_classic.retrievers import ContextualCompressionRetriever  # 正经注释：LangChain 上下文压缩检索器 / 大白话注释：LangChain 提供的"边检索边压缩"工具
from langchain_classic.retrievers.document_compressors import (
    DocumentCompressorPipeline,  # 正经注释：文档压缩管道，串联多个压缩步骤 / 大白话注释：把多个过滤步骤串起来的管道
    EmbeddingsFilter,  # 正经注释：基于嵌入相似度的文档过滤器 / 大白话注释：用向量相似度来过滤文档的工具
)
from langchain_core.documents import Document  # 正经注释：LangChain 文档类型 / 大白话注释：LangChain 里的"文档"数据结构
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 正经注释：递归字符文本分割器 / 大白话注释：把长文本按字符数切成小段

from ..memory.embeddings import OPENAI_EMBEDDING_MODEL  # 正经注释：导入 OpenAI 嵌入模型名称 / 大白话注释：导入默认向量模型的名字
from ..prompts import PromptFamily  # 正经注释：导入提示词模板族 / 大白话注释：导入格式化输出的工具
from ..utils.costs import estimate_embedding_cost  # 正经注释：导入嵌入成本估算函数 / 大白话注释：算算用向量模型要花多少钱
from ..vector_store import VectorStoreWrapper  # 正经注释：导入向量存储包装器 / 大白话注释：导入向量数据库的包装工具
from .retriever import SearchAPIRetriever, SectionRetriever  # 正经注释：导入搜索检索器和段落检索器 / 大白话注释：导入两种"数据转换器"


class VectorstoreCompressor:
    """从向量存储中检索和压缩上下文。

    【正经注释】
    使用向量存储的相似度搜索功能，查找与查询最相关的文档，
    适用于已有预构建向量索引的场景。

    Attributes:
        vector_store: 向量存储包装器实例。
        max_results: 最大返回结果数。
        filter: 可选的向量存储查询过滤器。

    【大白话注释】
    这个类从向量数据库里找跟问题最相关的文档。
    就像在图书馆的电子目录里搜关键词，找到最相关的几本书。
    """

    def __init__(
        self,
        vector_store: VectorStoreWrapper,
        max_results: int = 7,
        filter: Optional[dict] = None,
        prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
        **kwargs,
    ):
        """初始化 VectorstoreCompressor。

        【正经注释】
        配置向量存储检索器的基本参数。

        Args:
            vector_store: 要搜索的向量存储实例。
            max_results: 最大返回结果数。
            filter: 可选的查询过滤字典。
            prompt_family: 用于格式化输出的提示词模板族。
            **kwargs: 其他关键字参数。

        【大白话注释】
        创建向量存储检索器，告诉它去哪搜、最多拿几条结果。
        """
        self.vector_store = vector_store  # 正经注释：保存向量存储引用 / 大白话注释：记住要去哪个向量库搜
        self.max_results = max_results  # 正经注释：保存最大结果数 / 大白话注释：最多拿几条
        self.filter = filter  # 正经注释：保存过滤条件 / 大白话注释：有没有筛选条件
        self.kwargs = kwargs  # 正经注释：保存额外参数 / 大白话注释：其他杂七杂八的参数
        self.prompt_family = prompt_family  # 正经注释：保存提示词模板族 / 大白话注释：记住用什么格式输出

    async def async_get_context(self, query: str, max_results: int = 5) -> str:
        """从向量存储中异步获取相关上下文。

        【正经注释】
        对向量存储执行异步相似度搜索，返回格式化后的文档内容字符串。

        Args:
            query: 搜索查询字符串。
            max_results: 最大返回结果数。

        Returns:
            格式化后的相关文档内容字符串。

        【大白话注释】
        拿着你的问题去向量库里搜，找到最相关的几条结果，
        然后格式化成好看的文本返回。
        """
        results = await self.vector_store.asimilarity_search(query=query, k=max_results, filter=self.filter)  # 正经注释：执行异步相似度搜索 / 大白话注释：去向量库里搜相关内容
        return self.prompt_family.pretty_print_docs(results)  # 正经注释：格式化搜索结果 / 大白话注释：把结果排版好看一点返回


class ContextCompressor:
    """压缩原始文档以提取相关上下文。

    【正经注释】
    使用嵌入相似度过滤文档块，仅返回与查询最相关的内容。
    支持快速路径优化：当文档数量少且内容短时跳过压缩流程。

    Attributes:
        documents: 待压缩的文档列表。
        embeddings: 用于相似度计算的嵌入模型。
        max_results: 最大返回结果数。
        similarity_threshold: 包含的最小相似度分数。

    【大白话注释】
    这个类是"内容提炼器"。给它一堆文档和一个问题，
    它会把文档切碎，计算每块跟问题的相关度，只留最相关的。
    文档少的时候直接全部返回，不走费时的压缩流程。
    """

    def __init__(
        self,
        documents,
        embeddings,
        max_results: int = 5,
        prompt_family: type[PromptFamily] | PromptFamily = PromptFamily,
        **kwargs,
    ):
        """初始化 ContextCompressor。

        【正经注释】
        配置文档压缩器的基本参数，包括文档列表、嵌入模型和相似度阈值。

        Args:
            documents: 待压缩的文档列表。
            embeddings: 嵌入模型实例。
            max_results: 最大返回结果数。
            prompt_family: 用于格式化输出的提示词模板族。
            **kwargs: 其他关键字参数。

        【大白话注释】
        创建压缩器，告诉它要处理哪些文档、用什么向量模型、最多返回几条。
        """
        self.max_results = max_results  # 正经注释：保存最大结果数 / 大白话注释：最多要几条结果
        self.documents = documents  # 正经注释：保存文档列表 / 大白话注释：要处理的文档们
        self.kwargs = kwargs  # 正经注释：保存额外参数 / 大白话注释：其他参数
        self.embeddings = embeddings  # 正经注释：保存嵌入模型实例 / 大白话注释：用来算相似度的向量模型
        self.similarity_threshold = os.environ.get("SIMILARITY_THRESHOLD", 0.35)  # 正经注释：从环境变量读取相似度阈值，默认 0.35 / 大白话注释：相关度低于这个数的就不要了
        self.prompt_family = prompt_family  # 正经注释：保存提示词模板族 / 大白话注释：输出格式工具

    def __get_contextual_retriever(self):
        """构建上下文压缩检索管道。

        【正经注释】
        创建包含文本分割器和嵌入过滤器的压缩管道，
        并与搜索检索器组合为上下文压缩检索器。

        Returns:
            配置好的 ContextualCompressionRetriever 实例。

        【大白话注释】
        搭建"文字切割 -> 相似度过滤"的处理流水线。
        把长文章切成小块，然后只留跟问题相关的块。
        """
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)  # 正经注释：文本分割器，每块 1000 字符，重叠 100 字符 / 大白话注释：把文章切成1000字一块，相邻块有100字重叠防止断句
        relevance_filter = EmbeddingsFilter(embeddings=self.embeddings,
                                            similarity_threshold=self.similarity_threshold)  # 正经注释：基于嵌入的相似度过滤器 / 大白话注释：用向量模型算相关度，不达标的扔掉
        pipeline_compressor = DocumentCompressorPipeline(
            transformers=[splitter, relevance_filter]
        )  # 正经注释：将分割和过滤串联为管道 / 大白话注释：先切再过滤，串成流水线
        base_retriever = SearchAPIRetriever(
            pages=self.documents
        )  # 正经注释：使用搜索检索器作为基础检索器 / 大白话注释：把文档包装成检索器能用的格式
        contextual_retriever = ContextualCompressionRetriever(
            base_compressor=pipeline_compressor, base_retriever=base_retriever
        )  # 正经注释：创建上下文压缩检索器 / 大白话注释：把检索和压缩组合起来
        return contextual_retriever

    async def async_get_context(self, query: str, max_results: int = 5, cost_callback=None) -> str:
        """异步获取文档中的相关上下文。

        【正经注释】
        优化策略：对于小文档集跳过耗时的压缩管道，直接使用原始文档。
        仅在文档量大时执行完整的切割-过滤流程。

        Args:
            query: 搜索查询字符串。
            max_results: 最大返回结果数。
            cost_callback: 可选的嵌入成本跟踪回调函数。

        Returns:
            格式化后的相关文档内容字符串。

        【大白话注释】
        拿着问题从文档里找相关内容。如果文档不多内容也不长，
        就直接全部返回（省得花时间算向量）；如果文档多内容长，
        就走完整的切割+过滤流程。
        """
        # Optimization: Calculate total content size
        total_chars = sum(len(str(doc.get('raw_content', ''))) for doc in self.documents)  # 正经注释：计算所有文档内容的总字符数 / 大白话注释：看看总共有多少字要处理
        chunk_threshold = int(os.environ.get("COMPRESSION_THRESHOLD", "8000"))  # 正经注释：从环境变量获取压缩阈值，默认 8000 字符 / 大白话注释：低于这个字数就不压缩了

        # If total content is small, skip expensive compression and return directly
        if total_chars < chunk_threshold and len(self.documents) <= max_results:  # 正经注释：内容少且文档不多时走快速路径 / 大白话注释：内容少文档也不多，直接用，不压缩
            # Fast path: no compression needed
            direct_docs = [
                Document(
                    page_content=doc.get('raw_content', ''),
                    metadata=doc
                )
                for doc in self.documents[:max_results]
            ]  # 正经注释：直接将原始文档转为 LangChain Document / 大白话注释：把原始数据直接包装成文档对象
            return self.prompt_family.pretty_print_docs(direct_docs, max_results)

        # Standard path: use compression for large content
        compressed_docs = self.__get_contextual_retriever()  # 正经注释：获取压缩检索管道 / 大白话注释：走完整的压缩流程
        if cost_callback:  # 正经注释：如果有成本回调，估算嵌入费用 / 大白话注释：算算这次处理要花多少钱
            cost_callback(estimate_embedding_cost(model=OPENAI_EMBEDDING_MODEL, docs=self.documents))
        relevant_docs = await asyncio.to_thread(compressed_docs.invoke, query, **self.kwargs)  # 正经注释：在线程池中执行压缩检索 / 大白话注释：在后台线程跑压缩，不阻塞主程序
        return self.prompt_family.pretty_print_docs(relevant_docs, max_results)


class WrittenContentCompressor:
    """压缩已写过的报告内容段落。

    【正经注释】
    专用于从已生成的报告内容中查找相关段落的压缩器，
    保留段落标题和结构信息，用于避免报告内容重复。

    Attributes:
        documents: 已写内容段落列表。
        embeddings: 用于相似度计算的嵌入模型。
        similarity_threshold: 包含的最小相似度分数。

    【大白话注释】
    这个类专门处理"已经写过的内容"。比如报告写了一半，
    想看看之前写过哪些跟新问题相关的内容，避免重复。
    """

    def __init__(self, documents, embeddings, similarity_threshold: float, **kwargs):
        """初始化 WrittenContentCompressor。

        【正经注释】
        配置已写内容压缩器的基本参数。

        Args:
            documents: 已写内容段落列表。
            embeddings: 嵌入模型实例。
            similarity_threshold: 最小相似度分数。
            **kwargs: 其他关键字参数。

        【大白话注释】
        创建已写内容压缩器，传入之前写的段落和向量模型。
        """
        self.documents = documents  # 正经注释：保存已写内容段落 / 大白话注释：之前写过的内容列表
        self.kwargs = kwargs  # 正经注释：保存额外参数 / 大白话注释：其他参数
        self.embeddings = embeddings  # 正经注释：保存嵌入模型 / 大白话注释：用来算相关度的向量模型
        self.similarity_threshold = similarity_threshold  # 正经注释：保存相似度阈值 / 大白话注释：相关度低于这个数的不要

    def __get_contextual_retriever(self):
        """构建段落级别的上下文压缩检索管道。

        【正经注释】
        创建适用于段落检索的压缩管道，使用 SectionRetriever
        作为基础检索器。

        Returns:
            配置好的 ContextualCompressionRetriever 实例。

        【大白话注释】
        跟 ContextCompressor 的管道类似，但用的是段落检索器。
        专门处理有标题和正文结构的段落内容。
        """
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)  # 正经注释：文本分割器 / 大白话注释：把长段落切成小块
        relevance_filter = EmbeddingsFilter(embeddings=self.embeddings,
                                            similarity_threshold=self.similarity_threshold)  # 正经注释：相似度过滤器 / 大白话注释：只留相关的
        pipeline_compressor = DocumentCompressorPipeline(
            transformers=[splitter, relevance_filter]
        )  # 正经注释：串联分割和过滤管道 / 大白话注释：切割+过滤流水线
        base_retriever = SectionRetriever(
            sections=self.documents
        )  # 正经注释：使用段落检索器 / 大白话注释：用段落格式的检索器
        contextual_retriever = ContextualCompressionRetriever(
            base_compressor=pipeline_compressor, base_retriever=base_retriever
        )  # 正经注释：创建上下文压缩检索器 / 大白话注释：检索+压缩组合
        return contextual_retriever

    def __pretty_docs_list(self, docs, top_n: int) -> list[str]:
        """将文档格式化为标题+内容的字符串列表。

        【正经注释】
        提取每个文档的段落标题和正文内容，格式化为字符串列表。

        Args:
            docs: 待格式化的文档列表。
            top_n: 最大包含文档数。

        Returns:
            格式化后的文档字符串列表。

        【大白话注释】
        把文档整理成 "标题: xxx\n内容: xxx" 的格式，方便查看。
        """
        return [f"Title: {d.metadata.get('section_title')}\nContent: {d.page_content}\n" for i, d in enumerate(docs) if i < top_n]  # 正经注释：提取前 top_n 个文档的标题和内容 / 大白话注释：取前几条，拼成"标题+内容"的格式

    async def async_get_context(self, query: str, max_results: int = 5, cost_callback=None) -> list[str]:
        """异步获取相关的已写内容段落。

        【正经注释】
        对已写内容执行压缩检索，返回与查询最相关的段落列表。

        Args:
            query: 搜索查询字符串。
            max_results: 最大返回结果数。
            cost_callback: 可选的嵌入成本跟踪回调函数。

        Returns:
            格式化后的段落字符串列表。

        【大白话注释】
        拿着新问题去之前写的内容里找相关的段落。
        返回的是标题+内容的字符串列表。
        """
        compressed_docs = self.__get_contextual_retriever()  # 正经注释：获取压缩检索管道 / 大白话注释：拿到处理流水线
        if cost_callback:  # 正经注释：估算嵌入成本 / 大白话注释：算算花多少钱
            cost_callback(estimate_embedding_cost(model=OPENAI_EMBEDDING_MODEL, docs=self.documents))
        relevant_docs = await asyncio.to_thread(compressed_docs.invoke, query, **self.kwargs)  # 正经注释：在线程池中执行压缩检索 / 大白话注释：后台跑压缩，找相关内容
        return self.__pretty_docs_list(relevant_docs, max_results)  # 正经注释：格式化并返回结果 / 大白话注释：整理好格式返回

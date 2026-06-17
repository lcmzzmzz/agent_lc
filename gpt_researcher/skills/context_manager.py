"""上下文管理技能模块（Context Manager Skill）
【正经注释】
本模块提供 ContextManager 类，负责研究上下文的检索、压缩和相似度匹配。
支持三种压缩模式：基于文档的压缩、基于向量库的压缩、基于已写内容的压缩。
【大白话注释】
这个文件就是"编辑"——负责从一堆素材里找出跟问题最相关的内容：
- 从网页内容里找相关的 → "从搜到的网页里挑有用的"
- 从向量库里找相关的 → "从智能搜索库里找"
- 从已经写过的内容里找相似的 → "之前写过什么相关的？"
"""
import asyncio														# 正经注释：异步 I/O 库 / 大白话注释：异步工具
from typing import Dict, List, Optional, Set						# 正经注释：类型提示 / 大白话注释：类型标记

from ..actions.utils import stream_output								# 正经注释：WebSocket 输出流 / 大白话注释：给前端发消息
from ..context.compression import (									# 正经注释：导入三种压缩器 / 大白话注释：导入三种"从素材里挑东西"的工具
    ContextCompressor,												# 正经注释：文档上下文压缩器 / 大白话注释：从网页内容里挑相关的
    VectorstoreCompressor,											# 正经注释：向量库压缩器 / 大白话注释：从智能搜索库里挑相关的
    WrittenContentCompressor,										# 正经注释：已写内容压缩器 / 大白话注释：从已写内容里找相似的
)


class ContextManager:
    """上下文管理器——负责研究内容的检索、压缩和相似度匹配

    【正经注释】
    提供三种上下文检索模式：
    1. 基于文档的语义检索（get_similar_content_by_query）
    2. 基于向量库的检索（get_similar_content_by_query_with_vectorstore）
    3. 基于已写内容的检索（get_similar_written_contents_by_draft_section_titles）

    【大白话注释】
    这个类就是"编辑"——帮你从一堆素材里找到跟问题最相关的内容。
    三种找法：从网页里找、从智能搜索库里找、从之前写过的东西里找。

    Attributes:
        researcher: 父级 GPTResearcher 实例（大白话：老板）
    """

    def __init__(self, researcher):
        """初始化上下文管理器
        【正经注释】绑定父级 researcher 实例。
        【大白话注释】记住"老板"是谁。
        Args:
            researcher: GPTResearcher 实例（大白话：老板）
        """
        self.researcher = researcher								# 正经注释：持有对父级实例的引用 / 大白话注释：记住老板

    async def get_similar_content_by_query(self, query: str, pages: list) -> str:
        """基于查询从文档中检索相关内容
        【正经注释】创建 ContextCompressor 实例，使用 Embedding 进行语义匹配，
        返回与查询最相关的压缩上下文。
        【大白话注释】从一堆网页内容里，找出跟问题最相关的部分，整理成一段文字。
        Args:
            query: 搜索查询（大白话：要找什么）
            pages: 页面内容列表（大白话：一堆网页内容）
        Returns:
            str: 压缩后的相关上下文（大白话：整理好的相关内容）
        """
        if self.researcher.verbose:									# 正经注释：详细模式下推送进度 / 大白话注释：开了字幕就告诉用户
            await stream_output(
                "logs",
                "fetching_query_content",
                f"📚 Getting relevant content based on query: {query}...",
                self.researcher.websocket,
            )

        context_compressor = ContextCompressor(						# 正经注释：创建上下文压缩器 / 大白话注释：创建"内容筛选器"
            documents=pages,										# 正经注释：传入待筛选的文档 / 大白话注释：一堆素材
            embeddings=self.researcher.memory.get_embeddings(),		# 正经注释：传入 Embedding 模型用于语义匹配 / 大白话注释：用 AI 来理解含义
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )
        return await context_compressor.async_get_context(			# 正经注释：异步获取压缩后的上下文 / 大白话注释：开始筛选，返回最相关的内容
            query=query, max_results=10, cost_callback=self.researcher.add_costs	# 正经注释：最多返回 10 条结果 / 大白话注释：最多找 10 条
        )

    async def get_similar_content_by_query_with_vectorstore(self, query: str, filter: dict | None) -> str:
        """基于查询从向量库中检索相关内容
        【正经注释】创建 VectorstoreCompressor 实例，直接在向量库中进行语义检索。
        【大白话注释】从"智能搜索库"里找跟问题相关的内容。
        Args:
            query: 搜索查询（大白话：要找什么）
            filter: 向量库过滤条件（大白话：搜索时的筛选条件）
        Returns:
            str: 压缩后的相关上下文（大白话：找到的相关内容）
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "fetching_query_format",
                f" Getting relevant content based on query: {query}...",
                self.researcher.websocket,
                )
        vectorstore_compressor = VectorstoreCompressor(				# 正经注释：创建向量库压缩器 / 大白话注释：创建"智能搜索库筛选器"
            self.researcher.vector_store, filter=filter, prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )
        return await vectorstore_compressor.async_get_context(query=query, max_results=8)	# 正经注释：最多返回 8 条结果 / 大白话注释：最多找 8 条

    async def get_similar_written_contents_by_draft_section_titles(
        self,
        current_subtopic: str,
        draft_section_titles: List[str],
        written_contents: List[Dict],
        max_results: int = 10
    ) -> List[str]:
        """基于草稿章节标题查找已写过的相似内容
        【正经注释】将当前子课题和所有章节标题作为查询，并行搜索已写内容，
        合并去重后返回最相关的已写段落。用于 DetailedReport 避免重复写作。
        【大白话注释】写报告前先看看之前写过什么相关的，避免"车轱辘话来回说"：
        1. 把当前话题和所有章节标题都拿去搜索
        2. 同时搜索（不用排队等）
        3. 合并去重
        4. 最多返回 max_results 条
        Args:
            current_subtopic: 当前子课题（大白话：正在写的小话题）
            draft_section_titles: 章节标题列表（大白话：这节打算叫什么）
            written_contents: 已写内容列表（大白话：之前已经写好的段落）
            max_results: 最大返回数量（大白话：最多找几条）
        Returns:
            List[str]: 相似已写内容列表（大白话：之前写过的相关段落）
        """
        all_queries = [current_subtopic] + draft_section_titles		# 正经注释：组合子课题和章节标题作为查询列表 / 大白话注释：把话题和标题都拿去搜

        async def process_query(query: str) -> Set[str]:				# 正经注释：对单个查询搜索已写内容 / 大白话注释：拿一个标题去搜
            return set(await self.__get_similar_written_contents_by_query(query, written_contents, **self.researcher.kwargs))

        results = await asyncio.gather(*[process_query(query) for query in all_queries])	# 正经注释：并行搜索所有查询 / 大白话注释：同时搜所有标题
        relevant_contents = set().union(*results)					# 正经注释：合并所有查询结果并去重 / 大白话注释：把所有搜到的结果合在一起，去掉重复
        relevant_contents = list(relevant_contents)[:max_results]	# 正经注释：转为列表并截断到最大数量 / 大白话注释：最多留这么多条

        return relevant_contents									# 正经注释：返回去重后的相似内容 / 大白话注释：交出去

    async def __get_similar_written_contents_by_query(
        self,
        query: str,
        written_contents: List[Dict],
        similarity_threshold: float = 0.5,
        max_results: int = 10
    ) -> List[str]:
        """对单个查询搜索已写内容（内部方法）
        【正经注释】创建 WrittenContentCompressor 实例，按相似度阈值筛选已写内容。
        【大白话注释】拿一个问题去之前写过的内容里搜，只留相似度够高的。
        Args:
            query: 查询文本（大白话：搜什么）
            written_contents: 已写内容列表（大白话：之前写的东西）
            similarity_threshold: 相似度阈值（大白话：至少多相似才要）
            max_results: 最大返回数（大白话：最多找几条）
        Returns:
            List[str]: 相似的已写内容（大白话：之前写过的相关段落）
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "fetching_relevant_written_content",
                f"🔎 Getting relevant written content based on query: {query}...",
                self.researcher.websocket,
            )

        written_content_compressor = WrittenContentCompressor(		# 正经注释：创建已写内容压缩器 / 大白话注释：创建"已写内容筛选器"
            documents=written_contents,
            embeddings=self.researcher.memory.get_embeddings(),
            similarity_threshold=similarity_threshold,				# 正经注释：相似度阈值，低于此值的内容被过滤 / 大白话注释：太不像的不要
            **self.researcher.kwargs
        )
        return await written_content_compressor.async_get_context(	# 正经注释：异步获取筛选结果 / 大白话注释：开始筛选，交出去
            query=query, max_results=max_results, cost_callback=self.researcher.add_costs
        )

"""
搜索结果检索器模块。

【正经注释】
本模块提供将搜索结果和报告段落转换为 LangChain Document 对象的检索器类。
SearchAPIRetriever 处理网页搜索结果，SectionRetriever 处理已写报告的段落。
两者均继承自 LangChain 的 BaseRetriever，可嵌入压缩检索管道使用。

【大白话注释】
这个模块负责把"原始数据"变成 LangChain 能处理的"文档对象"。
搜索出来的是网页结果，写报告出来的是段落，它们格式不一样，
这个模块统一把它们转成同一种格式，方便后面处理。
"""
import os  # 正经注释：操作系统接口，用于读取环境变量 / 大白话注释：读环境变量用的
from enum import Enum  # 正经注释：枚举类型基类 / 大白话注释：定义常量选项用的（本文件暂未使用）
from typing import Any, Dict, List, Optional  # 正经注释：类型提示工具 / 大白话注释：类型标注工具箱

from langchain_core.callbacks import CallbackManagerForRetrieverRun  # 正经注释：LangChain 检索器运行回调管理器 / 大白话注释：LangChain 用来跟踪检索过程的工具
from langchain_core.documents import Document  # 正经注释：LangChain 文档数据类型 / 大白话注释：LangChain 的"文档"数据结构
from langchain_core.retrievers import BaseRetriever  # 正经注释：LangChain 检索器基类 / 大白话注释：LangChain 的检索器"模板"，新的检索器要继承它

# Maximum characters of raw_content to embed per document.
# Large documents (e.g. scraped PDFs) can exceed embedding API token limits
# (e.g. OpenAI's 300 000 token-per-request cap) when all chunks are sent at once.
# Defaults to 50 000 chars (~12 500 tokens); override with MAX_CONTENT_CHARS env var.
_MAX_CONTENT_CHARS = int(os.environ.get("MAX_CONTENT_CHARS", 50000))  # 正经注释：每个文档最大嵌入字符数，防止超大文档超出 API 限制 / 大白话注释：每篇文档最多取50000字符，太长的话向量模型处理不了


class SearchAPIRetriever(BaseRetriever):
    """
    搜索 API 检索器。

    【正经注释】
    将搜索 API 返回的网页结果列表转换为 LangChain Document 对象列表。
    每个网页的 raw_content 截断到最大字符限制，保留标题和 URL 元数据。

    Attributes:
        pages: 搜索结果的字典列表，每个字典包含 raw_content、title、url 等键。

    【大白话注释】
    把搜索到的网页结果变成统一的文档格式。每个网页的内容截取到一定长度，
    附上标题和网址信息，方便后面处理。
    """
    pages: List[Dict] = []  # 正经注释：存储搜索结果页面列表 / 大白话注释：搜索出来的网页结果，一开始是空的

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        将搜索结果转换为 Document 对象列表。

        【正经注释】
        实现 BaseRetriever 的抽象方法，遍历所有搜索结果页面，
        提取内容、标题和来源 URL，构建 Document 对象。

        Args:
            query: 搜索查询字符串（本检索器不使用查询进行过滤）。
            run_manager: LangChain 运行回调管理器。

        Returns:
            LangChain Document 对象列表。

        【大白话注释】
        把每个网页的内容、标题、网址都取出来，包装成标准文档对象。
        注意这个方法不做搜索过滤，直接把所有页面都转成文档。
        """

        docs = [
            Document(
                page_content=page.get("raw_content", "")[:_MAX_CONTENT_CHARS],  # 正经注释：截取内容到最大字符限制 / 大白话注释：内容太长就截掉，只取前面的
                metadata={
                    "title": page.get("title", ""),  # 正经注释：提取页面标题 / 大白话注释：把网页标题存到元数据里
                    "source": page.get("url", ""),  # 正经注释：提取页面 URL / 大白话注释：把网址存到元数据里
                },
            )
            for page in self.pages  # 正经注释：遍历所有搜索结果页面 / 大白话注释：一个一个网页地处理
        ]

        return docs

class SectionRetriever(BaseRetriever):
    """
    段落检索器，用于从已写内容中检索段落，避免子主题重复。

    【正经注释】
    将已写报告的段落列表转换为 LangChain Document 对象。
    每个段落包含 section_title 和 written_content 两个字段。

    Attributes:
        sections: 段落字典列表，每个字典包含 section_title 和 written_content。

    【大白话注释】
    跟 SearchAPIRetriever 类似，但处理的是"已经写好的报告段落"。
    每个段落有标题和正文，用来检查新写的内容跟之前有没有重复。

    sections 示例:
    [
        {
            "section_title": "示例标题",
            "written_content": "示例内容"
        },
        ...
    ]
    """
    sections: List[Dict] = []  # 正经注释：存储段落列表 / 大白话注释：已写的段落列表，一开始是空的

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        将已写段落转换为 Document 对象列表。

        【正经注释】
        实现 BaseRetriever 的抽象方法，遍历所有段落，
        提取正文内容和段落标题，构建 Document 对象。

        Args:
            query: 搜索查询字符串（本检索器不使用查询进行过滤）。
            run_manager: LangChain 运行回调管理器。

        Returns:
            LangChain Document 对象列表。

        【大白话注释】
        把每个段落的标题和正文取出来，包装成标准文档对象。
        跟 SearchAPIRetriever 做的事情差不多，只是数据来源不同。
        """

        docs = [
            Document(
                page_content=page.get("written_content", ""),  # 正经注释：提取段落正文 / 大白话注释：取段落的正文内容
                metadata={
                    "section_title": page.get("section_title", ""),  # 正经注释：提取段落标题 / 大白话注释：取段落标题存到元数据里
                },
            )
            for page in self.sections  # Changed 'self.pages' to 'self.sections'  # 正经注释：遍历所有段落 / 大白话注释：一个一个段落地处理
        ]

        return docs
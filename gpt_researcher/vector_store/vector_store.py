"""
LangChain 向量存储封装模块。

【正经注释】
本模块提供 VectorStoreWrapper 类，封装 LangChain 的向量存储接口，
将 GPT Researcher 的文档格式转换为 LangChain Document 格式，
支持文档加载、自动分块和异步相似度搜索。

【大白话注释】
这个文件就是给向量数据库套了一层"适配器"，让 GPT Researcher 的数据格式
能被 LangChain 的向量库识别。主要功能：把文档存进去、切成小块、按相似度搜。
"""
from typing import List, Dict  # 正经注释：列表和字典类型提示 / 大白话注释：类型标注工具

from langchain_core.documents import Document  # 正经注释：LangChain 文档数据类型 / 大白话注释：LangChain 的标准文档结构
from langchain_community.vectorstores import VectorStore  # 正经注释：LangChain 向量存储抽象基类 / 大白话注释：LangChain 的向量数据库"模板"
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 正经注释：递归字符文本分割器 / 大白话注释：把长文本切成小段的工具

class VectorStoreWrapper:
    """
    LangChain 向量存储的封装器，处理 GPT Researcher 文档类型转换。

    【正经注释】
    将 GPT Researcher 的文档字典列表转换为 LangChain Document 格式，
    自动进行文本分块后加载到向量存储中，并提供异步相似度搜索功能。

    【大白话注释】
    这个类就是"翻译官"，把 GPT Researcher 的文档数据翻译成
    LangChain 向量库能懂的格式，然后存进去、搜索。
    """
    def __init__(self, vector_store : VectorStore):
        """初始化向量存储包装器。

        【正经注释】
        接收一个 LangChain VectorStore 实例作为底层存储后端。

        Args:
            vector_store: LangChain 向量存储实例。

        【大白话注释】
        传入一个向量数据库实例，后面所有的操作都通过它来执行。
        """
        self.vector_store = vector_store  # 正经注释：保存向量存储引用 / 大白话注释：记住这个向量数据库

    def load(self, documents):
        """
        加载文档到向量存储中。

        【正经注释】
        将 GPT Researcher 格式的文档列表转换为 LangChain Document，
        按递归字符分割策略分块后加载到向量存储中。

        Args:
            documents: GPT Researcher 文档字典列表。

        【大白话注释】
        把一堆文档存进向量数据库。先转格式，再切成小块，最后存进去。
        """
        langchain_documents = self._create_langchain_documents(documents)  # 正经注释：转换为 LangChain 文档格式 / 大白话注释：先把格式转对
        splitted_documents = self._split_documents(langchain_documents)  # 正经注释：对文档进行分块 / 大白话注释：把长文档切成小段
        self.vector_store.add_documents(splitted_documents)  # 正经注释：将分块后的文档添加到向量存储 / 大白话注释：把切好的小段存进向量库

    def _create_langchain_documents(self, data: List[Dict[str, str]]) -> List[Document]:
        """将 GPT Researcher 文档转换为 LangChain Document。

        【正经注释】
        从每个文档字典中提取 raw_content 作为页面内容，
        url 作为来源元数据，构建 LangChain Document 对象。

        Args:
            data: GPT Researcher 文档字典列表，包含 raw_content 和 url 键。

        Returns:
            LangChain Document 对象列表。

        【大白话注释】
        把 GPT Researcher 的数据格式变成 LangChain 认识的格式。
        正文变成 page_content，网址变成 metadata。
        """
        return [Document(page_content=item["raw_content"], metadata={"source": item["url"]}) for item in data]  # 正经注释：逐个转换文档格式 / 大白话注释：一个一个转

    def _split_documents(self, documents: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
        """
        将文档分割为更小的块。

        【正经注释】
        使用递归字符分割策略，按指定块大小和重叠长度切分文档，
        确保语义连贯性不因分块而完全断裂。

        Args:
            documents: 待分割的 LangChain Document 列表。
            chunk_size: 每块的最大字符数，默认 1000。
            chunk_overlap: 相邻块之间的重叠字符数，默认 200。

        Returns:
            分割后的 LangChain Document 列表。

        【大白话注释】
        把长文档切成小块，每块最多1000字，相邻块有200字重叠，
        这样不会把一句话从中间切断。
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,  # 正经注释：块大小 / 大白话注释：每块最多多少字
            chunk_overlap=chunk_overlap,  # 正经注释：块重叠 / 大白话注释：相邻块重叠多少字
        )
        return text_splitter.split_documents(documents)  # 正经注释：执行分割 / 大白话注释：开切

    async def asimilarity_search(self, query, k, filter):
        """异步执行相似度搜索。

        【正经注释】
        在向量存储中搜索与查询最相似的 k 个文档，
        支持通过 filter 参数过滤搜索结果。

        Args:
            query: 搜索查询字符串。
            k: 返回的最大结果数。
            filter: 元数据过滤条件。

        Returns:
            相似文档列表。

        【大白话注释】
        拿着你的问题去向量库里搜最像的几条结果。
        可以设过滤条件，比如只搜某个来源的文档。
        """
        results = await self.vector_store.asimilarity_search(query=query, k=k, filter=filter)  # 正经注释：调用底层向量存储的异步搜索方法 / 大白话注释：在向量库里异步搜索
        return results

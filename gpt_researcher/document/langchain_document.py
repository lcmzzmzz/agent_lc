"""
langchain_document 模块 —— LangChain 文档格式加载器

【正经注释】
本模块实现了 LangChainDocumentLoader 类，用于将 LangChain 框架中的 Document 对象
转换为项目内部统一的 {"raw_content": ..., "url": ...} 字典格式。
该加载器兼容 LangChain 核心库的 Document 类，实现了从外部数据源到内部数据格式的桥接。

【大白话注释】
这个文件专门处理 LangChain 格式的文档数据。LangChain 有自己的一套文档格式（Document），
但咱们项目用的是自己的格式，这个类就是负责把 LangChain 的格式"翻译"成咱们能用的格式。
"""

import asyncio  # 正经注释：异步 IO 库，当前模块未直接使用异步特性但保持导入一致性 / 大白话注释：异步库，虽然这里没怎么用但先备着
import os  # 正经注释：操作系统接口模块，当前模块未直接使用但保持导入一致性 / 大白话注释：系统库，先备着万一要用

from langchain_core.documents import Document  # 正经注释：从 LangChain 核心库导入 Document 基类，表示一个包含内容和元数据的文档单元 / 大白话注释：引入 LangChain 的文档类型定义，它的文档就是这个格式
from typing import List, Dict  # 正经注释：类型注解工具，提供列表和字典的类型提示 / 大白话注释：标注类型用的，告诉别人这里用的是什么类型


# Supports the base Document class from langchain
# - https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/documents/base.py
class LangChainDocumentLoader:
    """
    LangChain 文档格式加载器

    【正经注释】
    该类接收 LangChain Document 对象列表，并将其转换为项目内部统一格式的字典列表。
    主要用于对接已有的 LangChain 数据管道或向量化存储系统，
    将其中的文档内容无缝接入本项目的文档处理流程。

    【大白话注释】
    LangChain 有它自己的文档格式，咱们项目也有自己的格式。
    这个类就像一个翻译官，把 LangChain 的文档变成咱们能看懂的格式。
    """

    def __init__(self, documents: List[Document]):
        """
        初始化 LangChain 文档加载器

        【正经注释】
        接收一个 LangChain Document 对象列表，作为待转换的数据源。

        【大白话注释】
        把 LangChain 的文档列表传进来存好，后面要用。
        """
        self.documents = documents  # 正经注释：保存传入的 Document 对象列表 / 大白话注释：把 LangChain 文档存起来

    async def load(self, metadata_source_index="title") -> List[Dict[str, str]]:
        """
        将 LangChain Document 列表转换为内部格式

        【正经注释】
        遍历所有 Document 对象，提取 page_content 作为原始文本内容，
        并从 metadata 中根据 metadata_source_index 键提取来源标识作为 url 字段。
        返回统一格式的字典列表，每个字典包含 raw_content 和 url 两个键。

        参数:
            metadata_source_index: 元数据中用作 url 标识的键名，默认为 "title"

        【大白话注释】
        把 LangChain 格式的文档挨个转成咱们自己的格式。
        每个文档的文字内容变成 raw_content，元数据里的某个字段变成 url。
        默认用 title（标题）当作来源标识。
        """
        docs = []  # 正经注释：初始化结果列表 / 大白话注释：准备空列表装转换结果
        for document in self.documents:  # 正经注释：遍历所有 Document 对象 / 大白话注释：一个一个文档来处理
            docs.append(
                {
                    "raw_content": document.page_content,  # 正经注释：提取文档的页面文本内容作为 raw_content / 大白话注释：把文档正文取出来
                    "url": document.metadata.get(metadata_source_index, ""),  # 正经注释：从元数据中提取指定键的值作为 url，不存在则为空字符串 / 大白话注释：从文档的附加信息里找来源标识，找不到就留空
                }
            )
        return docs  # 正经注释：返回转换后的字典列表 / 大白话注释：把转换好的结果交出去

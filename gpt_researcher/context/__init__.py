"""
上下文处理模块初始化文件。

【正经注释】
本模块导出上下文压缩和检索的核心组件。ContextCompressor 负责对原始文档
进行相似度过滤和压缩，SearchAPIRetriever 负责将搜索结果转化为
LangChain Document 格式供后续处理。

【大白话注释】
这个模块负责"从一堆资料里挑出最有用的部分"。
把搜索结果压缩、过滤，只保留跟问题最相关的内容。
"""
from .compression import ContextCompressor  # 正经注释：导入上下文压缩器 / 大白话注释：导入"内容压缩器"，用来过滤不相关内容
from .retriever import SearchAPIRetriever  # 正经注释：导入搜索 API 检索器 / 大白话注释：导入"搜索结果转换器"，把搜索结果变成统一格式

__all__ = ['ContextCompressor', 'SearchAPIRetriever']  # 正经注释：模块公开 API 列表 / 大白话注释：告诉外面这个模块提供两个工具

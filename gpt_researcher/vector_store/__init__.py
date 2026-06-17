"""
向量存储模块初始化文件。

【正经注释】
本模块导出 VectorStoreWrapper 类，提供对 LangChain 向量存储的
封装接口，支持文档加载、分块和相似度搜索。

【大白话注释】
这个模块就是向量数据库的"遥控器"，把文档存进去、按相似度搜出来。
"""
from .vector_store import VectorStoreWrapper  # 正经注释：导入向量存储包装器类 / 大白话注释：导入向量数据库的操作工具

__all__ = ['VectorStoreWrapper']  # 正经注释：模块公开 API / 大白话注释：对外提供 VectorStoreWrapper 这个工具
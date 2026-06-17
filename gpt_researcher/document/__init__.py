"""
document 模块 —— 文档加载器集合

【正经注释】
本模块作为 document 包的入口，负责导出三种文档加载器：
本地文件加载器（DocumentLoader）、在线文档加载器（OnlineDocumentLoader）、
以及 LangChain 文档加载器（LangChainDocumentLoader）。
统一管理各类文档的加载与解析能力，为上层研究流程提供结构化的文档内容。

【大白话注释】
这个文件就是 document 文件夹的"总管"，把三个能加载文档的工具都亮出来，
告诉大家：我这个文件夹里有本地文件加载器、网络文档加载器、还有 LangChain 文档加载器，
需要哪个自己拿去用就行。
"""

from .document import DocumentLoader  # 正经注释：从本地文件加载模块导入 DocumentLoader 类 / 大白话注释：把本地文档加载器引进来
from .online_document import OnlineDocumentLoader  # 正经注释：从在线文档加载模块导入 OnlineDocumentLoader 类 / 大白话注释：把网络文档下载加载器引进来
from .langchain_document import LangChainDocumentLoader  # 正经注释：从 LangChain 文档加载模块导入 LangChainDocumentLoader 类 / 大白话注释：把 LangChain 格式的文档加载器引进来

# 正经注释：定义模块公开 API 列表，控制 from document import * 的导出范围 / 大白话注释：告诉别人这个文件夹对外暴露哪三个类，别的不给
__all__ = ['DocumentLoader', 'OnlineDocumentLoader', 'LangChainDocumentLoader']

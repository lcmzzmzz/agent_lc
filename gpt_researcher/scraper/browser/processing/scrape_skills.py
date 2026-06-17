"""
【正经注释】PDF 和 Arxiv 论文抓取辅助技能模块，提供使用 PyMuPDF 和 ArxivRetriever
从 PDF 链接和 Arxiv 论文 ID 中提取文本内容的快捷函数。

【大白话注释】这个文件里有两个小工具：一个是从 PDF 网址直接提取文字，
另一个是从 Arxiv 论文编号搜索并提取论文内容。是浏览器爬虫的"辅助技能"。
"""
from langchain_community.document_loaders import PyMuPDFLoader  # 正经注释：LangChain 提供的 PyMuPDF 文档加载器 / 大白话注释：LangChain 里用来解析 PDF 的工具
from langchain_community.retrievers import ArxivRetriever  # 正经注释：LangChain 提供的 Arxiv 论文检索器 / 大白话注释：LangChain 里用来搜 Arxiv 论文的工具


def scrape_pdf_with_pymupdf(url) -> str:
    """
    【正经注释】使用 PyMuPDFLoader 从 PDF URL 加载文档并提取全部文本内容。

    Args:
        url (str): PDF 文件的 URL 地址

    Returns:
        str: 从 PDF 中提取的文本内容字符串

    【大白话注释】给一个 PDF 的网址，把里面的文字全抠出来。用的是 PyMuPDF 这个库。
    """
    loader = PyMuPDFLoader(url)  # 正经注释：创建 PDF 加载器实例 / 大白话注释：准备好解析 PDF 的工具
    doc = loader.load()  # 正经注释：加载 PDF 文档内容 / 大白话注释：把 PDF 内容读进来
    return str(doc)  # 正经注释：将文档对象转为字符串返回 / 大白话注释：变成文字返回


def scrape_pdf_with_arxiv(query) -> str:
    """
    【正经注释】使用 ArxivRetriever 根据查询条件搜索 Arxiv 论文，
    默认最多加载 2 篇文档且不限制字符数，返回第一篇的正文内容。

    Args:
        query (str): Arxiv 搜索查询（通常为论文 ID）

    Returns:
        str: 第一篇论文的正文内容

    【大白话注释】给一个论文编号，去 Arxiv 上搜一下，把第一篇论文的内容拿出来。
    最多拿 2 篇，内容不截断，只返回第一篇的文字。
    """
    retriever = ArxivRetriever(load_max_docs=2, doc_content_chars_max=None)  # 正经注释：创建检索器，最多 2 篇，不限字符 / 大白话注释：准备搜索，最多拿 2 篇论文，内容不截断
    docs = retriever.get_relevant_documents(query=query)  # 正经注释：执行搜索获取相关文档 / 大白话注释：拿着编号去搜论文
    return docs[0].page_content  # 正经注释：返回第一篇文档的正文内容 / 大白话注释：把第一篇论文的内容拿出来

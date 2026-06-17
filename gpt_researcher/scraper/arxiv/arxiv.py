"""
【正经注释】Arxiv 学术论文爬虫模块，通过 LangChain 的 ArxivRetriever 从 Arxiv 平台
检索并提取学术论文的标题、作者、发布日期和正文内容。

【大白话注释】这个文件专门用来抓 Arxiv 上的学术论文，输入一个 Arxiv 链接，
它就能把论文的标题、作者、发表日期和内容都给你拿回来。
"""
from langchain_community.retrievers import ArxivRetriever  # 正经注释：导入 LangChain 社区版提供的 Arxiv 检索器 / 大白话注释：LangChain 里现成的 Arxiv 论文获取工具


class ArxivScraper:
    """
    【正经注释】Arxiv 学术论文爬虫类，从 Arxiv 链接中提取论文的完整信息，
    包括发布日期、作者、标题和正文内容。

    【大白话注释】专门抓 Arxiv 论文的爬虫，给它一个论文链接，它就把论文内容给你抠出来。
    """

    def __init__(self, link, session=None):
        self.link = link  # 正经注释：存储 Arxiv 论文链接 / 大白话注释：记住论文的网址
        self.session = session  # 正经注释：存储 HTTP 会话对象（Arxiv 爬虫不需要） / 大白话注释：HTTP 会话（这个爬虫其实用不到，但统一接口得有）

    def scrape(self):
        """
        【正经注释】从 Arxiv 链接中提取论文内容。通过解析链接中的论文 ID 作为查询条件，
        使用 ArxivRetriever 获取最多 2 篇相关文档，返回第一篇的发布日期、作者、标题和正文。
        输出格式遵循 APA 引用风格。

        Returns:
            tuple: (context, image_list, title) 其中 context 包含发布日期、作者和正文内容

        【大白话注释】开始抓论文！从链接里抠出论文编号，去 Arxiv 搜一下，
        返回第一篇论文的发布日期、作者和内容。图片列表是空的，因为论文没有图片 URL。
        """
        query = self.link.split("/")[-1]  # 正经注释：从 URL 路径中提取论文 ID / 大白话注释：从网址最后一段抠出论文编号
        retriever = ArxivRetriever(load_max_docs=2, doc_content_chars_max=None)  # 正经注释：创建检索器，最多加载 2 篇文档，不限制字符数 / 大白话注释：准备去 Arxiv 搜论文，最多拿 2 篇，内容不截断
        docs = retriever.invoke(query)  # 正经注释：执行检索获取相关文档 / 大白话注释：拿着论文编号去搜

        # Include the published date and author to provide additional context,
        # aligning with APA-style formatting in the report.
        # 正经注释：将发布日期、作者和正文组合为上下文，符合 APA 引用格式 / 大白话注释：把论文的发表日期、作者、正文拼在一起，方便写报告时引用
        context = f"Published: {docs[0].metadata['Published']}; Author: {docs[0].metadata['Authors']}; Content: {docs[0].page_content}"
        image = []  # 正经注释：学术论文不提取图片 URL / 大白话注释：图片列表是空的，PDF 论文里没法直接拿图片 URL

        return context, image, docs[0].metadata["Title"]  # 正经注释：返回论文上下文、空图片列表和标题 / 大白话注释：把结果打包返回——论文内容、空的图片列表、论文标题

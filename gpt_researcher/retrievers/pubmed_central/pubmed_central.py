"""
PubMed Central 生物医学文献全文检索器。

【正经注释】本模块实现了基于NCBI E-utilities API的PubMed Central全文文献搜索功能。
采用两步搜索策略：先通过esearch获取文章ID列表，再通过efetch获取全文XML内容。
支持PubMed和PMC两种数据库，自动解析XML提取标题、摘要和正文。

【大白话注释】这个文件是用来搜PubMed Central的，这是一个生物医学论文数据库。
搜索分两步走：先搜到论文编号，再根据编号去拿全文内容。
拿到的全文会从XML格式里把标题、摘要和正文都提取出来。
"""

from typing import List, Dict, Any, Optional  # 正经注释：类型提示相关导入 / 大白话注释：类型标注用的
import os  # 正经注释：操作系统接口模块 / 大白话注释：读环境变量用的
import xml.etree.ElementTree as ET  # 正经注释：XML解析库，用于解析PMC返回的XML格式全文 / 大白话注释：解析XML用的，把论文内容从XML里抠出来
import requests  # 正经注释：HTTP请求库 / 大白话注释：发网络请求用的工具


class PubMedCentralSearch:
    """
    PubMed Central 全文文献检索器。

    【正经注释】
    通过NCBI E-utilities API实现的PubMed Central全文搜索类。
    采用esearch+efetch两步策略获取文献全文内容，
    支持通过PUBMED_ARG_前缀环境变量自定义搜索参数。

    【大白话注释】
    这个类就是帮你搜PubMed生物医学论文的。它不光搜标题和摘要，
    还能把论文全文都拿回来。需要设置NCBI_API_KEY环境变量才能用。
    """

    def __init__(self, query: str, query_domains=None):
        """
        初始化PubMedCentralSearch检索器。

        【正经注释】
        设置NCBI E-utilities API端点URL，从环境变量获取API密钥，
        确定数据库类型（PMC或PubMed），收集自定义参数。

        【大白话注释】
        准备工作——设好PubMed的API地址，找好钥匙（API密钥），
        确定搜哪个数据库（默认搜PMC全文库）。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表（PubMed不支持此参数）
        """
        self.base_search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"  # 正经注释：NCBI文章搜索API端点 / 大白话注释：用来搜论文编号的网址
        self.base_fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"  # 正经注释：NCBI文章获取API端点 / 大白话注释：用来拿论文全文的网址

        # Get API key from environment
        self.api_key = os.getenv('NCBI_API_KEY')  # 正经注释：从环境变量获取NCBI API密钥 / 大白话注释：去系统里找NCBI的钥匙
        if not self.api_key:  # 正经注释：API密钥不存在时发出警告 / 大白话注释：没钥匙就提醒你"速度会变慢哦"
            print("Warning: NCBI_API_KEY not set. Requests will be rate-limited.")

        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.db_type = os.getenv('PUBMED_DB', 'pmc')  # Default to PMC for full text  # 正经注释：从环境变量获取数据库类型，默认为PMC（全文库） / 大白话注释：默认搜PMC全文库，也可以改成搜PubMed摘要库

        # Optional parameters from environment
        self.params = self._populate_params()  # 正经注释：收集自定义搜索参数 / 大白话注释：把额外参数也收集起来

    def _populate_params(self) -> Dict[str, Any]:
        """
        从环境变量中收集PUBMED_ARG_前缀的自定义参数。

        【正经注释】
        扫描所有以PUBMED_ARG_为前缀的环境变量，去除前缀并转小写后
        作为API请求参数，设置默认的排序和返回模式。

        【大白话注释】
        把环境变量里所有以PUBMED_ARG_开头的变量找出来，
        去掉前缀变成小写参数名。还会设一些默认值。

        Returns:
            Dict[str, Any]: 参数字典
        """
        params = {
            key[len('PUBMED_ARG_'):].lower(): value
            for key, value in os.environ.items()
            if key.startswith('PUBMED_ARG_')
        }

        # Set defaults if not provided
        params.setdefault('sort', 'relevance')  # 正经注释：默认按相关度排序 / 大白话注释：没指定排序就按最相关的排
        params.setdefault('retmode', 'json')  # 正经注释：默认返回JSON格式 / 大白话注释：没指定格式就用JSON
        return params

    def _search_articles(self, max_results: int) -> Optional[List[str]]:
        """
        搜索文章并返回文章ID列表。

        【正经注释】
        通过NCBI esearch API搜索符合条件的文章，
        对于PubMed数据库自动添加全文可用性过滤器，
        返回匹配的文章ID列表。

        【大白话注释】
        第一步：去PubMed搜论文编号。如果搜的是PubMed（摘要库），
        会自动加上"只搜有全文的"这个过滤条件。

        Args:
            max_results: 最大返回结果数

        Returns:
            文章ID列表，失败时返回None
        """
        # Build search query with filters for full text
        if self.db_type == 'pubmed':  # 正经注释：PubMed数据库需要添加全文可用性过滤 / 大白话注释：搜摘要库时要加过滤条件只要有全文的
            search_term = f"{self.query} AND (ffrft[filter] OR pmc[filter])"
        else:  # PMC always has full text  # 正经注释：PMC数据库本身就是全文库，无需额外过滤 / 大白话注释：PMC本来就是全文库，不用过滤
            search_term = self.query

        search_params = {
            "db": self.db_type,  # 正经注释：数据库类型 / 大白话注释：搜哪个库
            "term": search_term,  # 正经注释：搜索条件 / 大白话注释：搜什么
            "retmax": max_results,  # 正经注释：最大返回数量 / 大白话注释：要几条
            "api_key": self.api_key,  # 正经注释：API密钥 / 大白话注释：钥匙
            **self.params  # Include custom params  # 正经注释：包含自定义参数 / 大白话注释：加上额外参数
        }

        try:
            response = requests.get(self.base_search_url, params=search_params)  # 正经注释：发送搜索请求 / 大白话注释：正式发搜索请求
            response.raise_for_status()  # 正经注释：检查HTTP状态码 / 大白话注释：看看请求有没有成功
            data = response.json()  # 正经注释：解析JSON响应 / 大白话注释：把返回数据解析出来

            id_list = data.get('esearchresult', {}).get('idlist', [])  # 正经注释：从响应中提取文章ID列表 / 大白话注释：把论文编号拿出来
            print(f"Found {len(id_list)} articles with full text available")  # 正经注释：输出找到的文章数量 / 大白话注释：告诉你找到了几篇
            return id_list

        except requests.RequestException as e:  # 正经注释：捕获请求异常 / 大白话注释：出错了就告诉你
            print(f"Failed to search articles: {e}")
            return None

    def _fetch_full_text(self, article_id: str) -> Optional[Dict[str, str]]:
        """
        获取单篇文章的全文内容。

        【正经注释】
        通过NCBI efetch API获取指定文章的XML格式全文，
        解析XML提取标题、摘要和正文内容，构建完整的内容字典返回。

        【大白话注释】
        第二步：根据论文编号去拿全文。PubMed返回的是XML格式，
        这个函数会把标题、摘要和正文从XML里提取出来。

        Args:
            article_id: 文章ID

        Returns:
            包含全文信息的字典，失败时返回None
        """
        fetch_params = {
            "db": "pmc" if self.db_type == "pmc" else "pmc",  # Always fetch from PMC for full text  # 正经注释：始终从PMC获取全文 / 大白话注释：全文都从PMC拿
            "id": article_id,  # 正经注释：文章ID / 大白话注释：哪篇论文
            "rettype": "full",  # 正经注释：获取完整内容 / 大白话注释：要全部内容
            "retmode": "xml",  # 正经注释：返回XML格式 / 大白话注释：用XML格式返回
            "api_key": self.api_key  # 正经注释：API密钥 / 大白话注释：钥匙
        }

        try:
            response = requests.get(self.base_fetch_url, params=fetch_params)  # 正经注释：发送全文获取请求 / 大白话注释：去拿论文全文
            response.raise_for_status()  # 正经注释：检查HTTP状态码 / 大白话注释：看看请求有没有成功

            # Parse XML content
            try:
                root = ET.fromstring(response.text)  # 正经注释：解析XML响应 / 大白话注释：把XML解析成树状结构

                # Extract title
                title = root.find('.//article-title')  # 正经注释：从XML中查找标题元素 / 大白话注释：找到论文标题
                title_text = title.text if title is not None else ""  # 正经注释：提取标题文本 / 大白话注释：把标题拿出来

                # Extract abstract
                abstract = root.find('.//abstract')  # 正经注释：从XML中查找摘要元素 / 大白话注释：找到论文摘要
                abstract_text = " ".join(abstract.itertext()) if abstract is not None else ""  # 正经注释：提取摘要全部文本 / 大白话注释：把摘要文字全部拿出来

                # Extract body text
                body = root.find('.//body')  # 正经注释：从XML中查找正文元素 / 大白话注释：找到论文正文
                body_text = " ".join(body.itertext()) if body is not None else ""  # 正经注释：提取正文全部文本 / 大白话注释：把正文文字全部拿出来

                # Combine all text content
                full_content = f"Title: {title_text}\n\nAbstract: {abstract_text}\n\nBody: {body_text}"  # 正经注释：拼接完整的文本内容 / 大白话注释：把标题、摘要、正文拼在一起

                # Build URL
                if self.db_type == "pmc" or article_id.startswith("PMC"):  # 正经注释：构建PMC文章URL / 大白话注释：拼出论文的网页链接
                    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article_id}/"
                else:
                    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{article_id}/"

                return {
                    "href": url,  # 正经注释：文章URL / 大白话注释：论文链接
                    "url": url,  # 正经注释：文章URL（冗余字段，兼容性保留） / 大白话注释：论文链接（留个备份）
                    "body": full_content,  # 正经注释：完整文本内容 / 大白话注释：论文全文
                    "raw_content": full_content,  # 正经注释：原始文本内容 / 大白话注释：原始全文
                    "title": title_text  # 正经注释：文章标题 / 大白话注释：论文标题
                }

            except ET.ParseError as e:  # 正经注释：XML解析错误时返回None / 大白话注释：XML解析出错了就放弃这篇
                return None

        except requests.RequestException as e:  # 正经注释：请求异常时返回None / 大白话注释：请求出错了就放弃这篇
            return None

    def search(self, max_results: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        执行PubMed Central搜索并获取全文内容。

        【正经注释】
        执行完整的两步搜索流程：
        1. 通过esearch搜索文章ID列表
        2. 通过efetch获取每篇文章的全文内容

        【大白话注释】
        完整的搜索流程：先搜论文编号，再逐个拿全文。
        两步走，把结果整理好还给你。

        :param max_results: 最大返回结果数
        :return: 包含全文信息的搜索结果列表
        """
        # Step 1: Search for article IDs
        article_ids = self._search_articles(max_results)  # 正经注释：第一步搜索文章ID / 大白话注释：先找到论文编号
        if not article_ids:  # 正经注释：无搜索结果时返回None / 大白话注释：没找到论文就返回空
            return None

        # Step 2: Fetch full text for each article
        results = []  # 正经注释：初始化结果列表 / 大白话注释：准备箱子装结果
        for article_id in article_ids:  # 正经注释：遍历每个文章ID获取全文 / 大白话注释：一篇一篇地拿全文
            article_content = self._fetch_full_text(article_id)
            if article_content:  # 正经注释：成功获取全文的结果才添加 / 大白话注释：拿到了才放进箱子里
                results.append(article_content)

        return results  # 正经注释：返回搜索结果 / 大白话注释：把整理好的结果交出去

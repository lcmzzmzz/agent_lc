"""
Xquik X/Twitter 社交媒体检索器。

【正经注释】本模块实现了基于Xquik REST API的X（Twitter）推文搜索功能。
Xquik提供低成本（$0.00015/推文）的推文搜索服务，比官方X API便宜约33倍。
支持搜索实时观点、开发者讨论、产品反馈、突发新闻和专家意见。

【大白话注释】这个文件是用来搜推特（X）的。用的是Xquik这个第三方服务，
比推特官方API便宜得多（33倍）。你给它关键词，它帮你搜推特上的推文，
搜完把推文内容、作者信息和互动数据（点赞、转发、浏览量）整理好给你。
"""

# Xquik X/Twitter Retriever
#
# Searches X (Twitter) for real-time perspectives, dev discussions,
# product feedback, breaking news, and expert opinions.
# $0.00015 per tweet — 33x cheaper than the official X API.

import json  # 正经注释：JSON解析库 / 大白话注释：解析JSON数据用的
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：读系统里存的API密钥
import urllib.parse  # 正经注释：URL编码工具 / 大白话注释：拼网址参数用的
import urllib.request  # 正经注释：URL请求工具，用于发送HTTP请求 / 大白话注释：发网络请求用的（标准库版本）


class XquikSearch:
    """
    Xquik X/Twitter 推文搜索检索器。

    【正经注释】
    通过Xquik REST API v1实现的推文搜索类。
    返回标准的{title, href, body}格式，title包含作者和推文摘要，
    body包含推文全文和互动数据（点赞、转发、浏览量）。

    【大白话注释】
    这个类就是帮你搜推特推文的。搜到的每条推文都会告诉你：
    谁发的、发了什么内容、多少人点赞/转发/看了。
    比推特官方API便宜很多。

    需要设置的环境变量：
    - XQUIK_API_KEY: Xquik的API密钥（在 https://xquik.com 获取）
    """

    def __init__(self, query, query_domains=None, **kwargs):
        """
        初始化XquikSearch对象。

        【正经注释】
        接收搜索查询语句，从环境变量加载Xquik API密钥。

        【大白话注释】
        准备工作——记下要搜什么关键词，去找Xquik的钥匙。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表（Twitter搜索不支持此参数）
            **kwargs: 额外参数（用于兼容性）
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.query_domains = query_domains  # 正经注释：保存域名过滤列表 / 大白话注释：记住域名（推特用不上）
        self.api_key = self.get_api_key()  # 正经注释：获取API密钥 / 大白话注释：去拿钥匙

    def get_api_key(self):
        """
        从环境变量获取Xquik API密钥。

        【正经注释】
        从系统环境变量中读取XQUIK_API_KEY，
        若未设置则抛出异常并提供获取指引。

        【大白话注释】
        去系统里找Xquik的钥匙。找不到就告诉你去哪申请。

        Returns:
            str: Xquik API密钥

        Raises:
            Exception: 环境变量未设置时抛出
        """
        try:
            api_key = os.environ["XQUIK_API_KEY"]  # 正经注释：从环境变量读取API密钥 / 大白话注释：去系统里找钥匙
        except KeyError:  # 正经注释：密钥不存在时抛出友好错误 / 大白话注释：没找到钥匙就报错
            raise Exception(
                "Xquik API key not found. Please set the XQUIK_API_KEY "
                "environment variable. Get a key at https://xquik.com"
            )
        return api_key  # 正经注释：返回API密钥 / 大白话注释：把钥匙交出去

    def search(self, max_results=10):
        """
        执行X/Twitter推文搜索。

        【正经注释】
        通过Xquik API搜索X/Twitter推文，返回标准化的搜索结果列表。
        异常时返回空列表而不中断程序。

        【大白话注释】
        真正去Xquik搜推特。搜完把推文整理好给你。
        出错了也不崩溃，返回空结果。

        Returns:
            list: 搜索结果列表，格式为[{title, href, body}, ...]
        """
        print(f"Searching X/Twitter with query: {self.query}...")  # 正经注释：输出搜索日志 / 大白话注释：打印正在搜什么

        try:
            results = self._search_tweets(max_results)  # 正经注释：调用内部推文搜索方法 / 大白话注释：去搜推文
            return results
        except Exception as e:  # 正经注释：捕获异常并返回空列表 / 大白话注释：出错了就记一下
            print(f"Error: {e}. Failed fetching X/Twitter sources. Resulting in empty response.")
            return []

    def _search_tweets(self, max_results):
        """
        内部方法：通过Xquik API搜索推文。

        【正经注释】
        构建搜索请求URL和参数，发送HTTP请求到Xquik API，
        解析返回的推文数据，提取作者、内容、互动数据等信息，
        转换为标准的{title, href, body}格式。

        【大白话注释】
        这是真正跟Xquik通信的方法。它会：
        1. 拼好搜索URL和参数
        2. 发HTTP请求
        3. 解析返回的推文数据
        4. 把每条推文的作者、内容、点赞/转发/浏览数整理好

        Args:
            max_results: 最大返回结果数

        Returns:
            list: 标准化的推文搜索结果列表
        """
        params = urllib.parse.urlencode({  # 正经注释：编码搜索参数 / 大白话注释：把参数拼成URL格式
            "q": self.query,  # 正经注释：搜索查询语句 / 大白话注释：搜什么关键词
            "limit": min(max_results, 200),  # 正经注释：结果数量限制，上限200 / 大白话注释：最多要200条
            "queryType": "Top",  # 正经注释：搜索类型为热门推文 / 大白话注释：搜热门的推文
        })
        url = f"https://xquik.com/api/v1/x/tweets/search?{params}"  # 正经注释：构建完整的搜索API URL / 大白话注释：拼出完整的搜索网址

        req = urllib.request.Request(url, headers={  # 正经注释：创建HTTP请求对象并设置请求头 / 大白话注释：准备好请求，带上钥匙和身份
            "X-API-Key": self.api_key,  # 正经注释：API密钥认证 / 大白话注释：带上钥匙
            "Accept": "application/json",  # 正经注释：接受JSON响应 / 大白话注释：告诉服务器我要JSON
            "User-Agent": "gpt-researcher/1.0",  # 正经注释：标识客户端身份 / 大白话注释：告诉对方"我是GPT Researcher"
        })

        with urllib.request.urlopen(req, timeout=15) as resp:  # 正经注释：发送请求并读取响应，15秒超时 / 大白话注释：正式发请求，等15秒
            data = json.loads(resp.read().decode("utf-8"))  # 正经注释：解析JSON响应 / 大白话注释：把返回的数据解析出来

        tweets = data.get("tweets", [])  # 正经注释：从响应中提取推文列表 / 大白话注释：把推文拿出来
        search_results = []  # 正经注释：初始化结果列表 / 大白话注释：准备箱子装结果

        for tweet in tweets[:max_results]:  # 正经注释：遍历推文列表，截取前max_results条 / 大白话注释：一条一条看，最多看要的条数
            author = tweet.get("author", {})  # 正经注释：获取推文作者信息 / 大白话注释：看看是谁发的
            username = author.get("username", "unknown")  # 正经注释：获取作者用户名 / 大白话注释：用户名叫什么
            text = tweet.get("text", "")  # 正经注释：获取推文文本内容 / 大白话注释：推文写了什么
            tweet_id = tweet.get("id", "")  # 正经注释：获取推文ID / 大白话注释：推文编号

            likes = tweet.get("likeCount", 0)  # 正经注释：获取点赞数 / 大白话注释：多少人点赞
            retweets = tweet.get("retweetCount", 0)  # 正经注释：获取转发数 / 大白话注释：多少人转发
            views = tweet.get("viewCount", 0)  # 正经注释：获取浏览数 / 大白话注释：多少人看了

            engagement = f"{likes} likes, {retweets} RTs"  # 正经注释：构建互动数据字符串 / 大白话注释：把点赞和转发数拼起来
            if views:  # 正经注释：有浏览量时追加到互动数据 / 大白话注释：有浏览数也加上
                engagement += f", {views} views"

            search_results.append({
                "title": f"@{username}: {text[:120]}{'...' if len(text) > 120 else ''}",  # 正经注释：标题包含作者和推文摘要（最多120字） / 大白话注释：标题显示"谁发的：推文前120字"
                "href": f"https://x.com/{username}/status/{tweet_id}",  # 正经注释：推文链接URL / 大白话注释：推文的网页链接
                "body": f"{text}\n\n[{engagement}]",  # 正经注释：正文包含推文全文和互动数据 / 大白话注释：推文全文加上互动数据
            })

        return search_results  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去

"""
GPT Researcher 检索器工具函数模块。

【正经注释】本模块提供检索器实现所需的通用辅助函数和常量定义，
包括流式输出、依赖包检查以及有效检索器名称列表等功能。

【大白话注释】这个文件是所有搜索器的"工具箱"，放了一些大家都会用到的
公共函数和常量。比如检查某个Python包装没装好、给前端推送实时消息、
列出所有可用的搜索引擎名字等等。
"""

import importlib.util  # 正经注释：用于动态检查Python包是否已安装 / 大白话注释：用来偷偷看看某个包装了没有
import logging  # 正经注释：日志记录模块 / 大白话注释：记日志用的，出问题了方便查
import os  # 正经注释：操作系统接口模块 / 大白话注释：跟文件系统打交道用的
import sys  # 正经注释：系统相关参数和函数模块 / 大白话注释：跟Python解释器打交道用的

logger = logging.getLogger(__name__)  # 正经注释：创建当前模块的日志记录器实例 / 大白话注释：给这个文件搞个专属的日志记录器

async def stream_output(log_type, step, content, websocket=None, with_data=False, data=None):
    """
    通过WebSocket向客户端流式输出日志信息。

    【正经注释】
    异步函数，将研究过程中的日志/步骤/内容通过WebSocket实时推送给前端客户端。
    支持可选的附加数据字段传输。若发送失败则记录错误日志但不中断流程。

    【大白话注释】
    这个函数就是个"传话筒"——把后台正在干的事实时告诉前端页面。
    比如搜索到第几步了、搜到了什么内容，都可以通过它传出去。
    如果网络断了传不出去，就悄悄记个日志，别让程序崩溃。

    Args:
        log_type (str): 日志类型标识
        step (str): 当前执行的步骤描述
        content (str): 要输出的内容
        websocket: WebSocket连接对象，可选
        with_data (bool): 是否携带附加数据字段，默认False
        data: 附加数据，可选
    """
    if websocket:  # 正经注释：仅在WebSocket连接存在时执行发送 / 大白话注释：有人在线听才说话
        try:
            if with_data:  # 正经注释：带附加数据的发送格式 / 大白话注释：捎带额外信息的发送方式
                await websocket.send_json({
                    "type": log_type,
                    "step": step,
                    "content": content,
                    "data": data
                })
            else:  # 正经注释：标准发送格式 / 大白话注释：普通发送方式
                await websocket.send_json({
                    "type": log_type,
                    "step": step,
                    "content": content
                })
        except Exception as e:  # 正经注释：捕获WebSocket发送异常并记录 / 大白话注释：发送失败了就记个错，别崩
            logger.error(f"Error streaming output: {e}")

def check_pkg(pkg: str) -> None:
    """
    检查指定的Python包是否已安装，未安装则抛出ImportError。

    【正经注释】
    通过importlib工具动态检测指定包名是否存在于当前Python环境中，
    若不存在则抛出ImportError并附带安装命令提示。

    【大白话注释】
    就是"查户口"——看看某个Python包装了没有。没装的话就报错，
    顺便告诉你该用什么命令去装。

    Args:
        pkg (str): 要检查的包名

    Raises:
        ImportError: 当包未安装时抛出
    """
    if not importlib.util.find_spec(pkg):  # 正经注释：利用importlib检查包的可导入性 / 大白话注释：去翻翻看这个包装了没
        pkg_kebab = pkg.replace("_", "-")  # 正经注释：将下划线格式转换为连字符格式以匹配pip包名 / 大白话注释：把包名的下划线换成横杠，因为pip安装用的是横杠
        raise ImportError(
            f"Unable to import {pkg_kebab}. Please install with "
            f"`pip install -U {pkg_kebab}`"
        )

# Valid retrievers for fallback  # 正经注释：有效检索器名称列表，用作回退方案 / 大白话注释：所有支持的搜索引擎名字，兜底用的
VALID_RETRIEVERS = [
    "tavily",  # 正经注释：Tavily搜索引擎 / 大白话注释：Tavily搜索
    "custom",  # 正经注释：自定义API检索器 / 大白话注释：自定义搜索
    "duckduckgo",  # 正经注释：DuckDuckGo搜索引擎 / 大白话注释：DuckDuckGo搜索
    "searchapi",  # 正经注释：SearchApi检索器 / 大白话注释：SearchApi搜索
    "serper",  # 正经注释：Serper检索器 / 大白话注释：Serper搜索
    "serpapi",  # 正经注释：SerpApi检索器 / 大白话注释：SerpApi搜索
    "google",  # 正经注释：Google自定义搜索 / 大白话注释：Google搜索
    "searx",  # 正经注释：SearxNG元搜索 / 大白话注释：Searx搜索
    "bing",  # 正经注释：Bing搜索引擎 / 大白话注释：Bing搜索
    "arxiv",  # 正经注释：Arxiv学术论文 / 大白话注释：Arxiv论文搜索
    "semantic_scholar",  # 正经注释：Semantic Scholar学术搜索 / 大白话注释：Semantic Scholar搜索
    "pubmed_central",  # 正经注释：PubMed Central文献搜索 / 大白话注释：PubMed搜索
    "exa",  # 正经注释：Exa AI搜索引擎 / 大白话注释：Exa搜索
    "mcp",  # 正经注释：MCP协议检索器 / 大白话注释：MCP搜索
    "xquik",  # 正经注释：Xquik X/Twitter搜索 / 大白话注释：推特搜索
    "openalex",  # 正经注释：OpenAlex学术文献 / 大白话注释：OpenAlex搜索
    "mock"  # 正经注释：模拟检索器（测试用） / 大白话注释：假搜索器，测试用的
]

def get_all_retriever_names():
    """
    获取所有可用的检索器名称列表。

    【正经注释】
    通过扫描当前目录下的子文件夹来自动发现所有已注册的检索器模块，
    排除__pycache__等特殊目录。若扫描失败则回退返回预设的VALID_RETRIEVERS列表。

    【大白话注释】
    这个函数会"数家珍"——翻翻当前文件夹下面有多少个子文件夹，
    每个子文件夹就代表一个搜索引擎。数完了把名字列表返回。
    万一翻文件夹出错了，就用上面那个硬编码的兜底列表。

    :return: 所有可用检索器的名称列表
    :rtype: list
    """
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))  # 正经注释：获取当前文件所在目录的绝对路径 / 大白话注释：看看自己在哪个文件夹里

        # Get all items in the current directory
        all_items = os.listdir(current_dir)  # 正经注释：列出当前目录下所有条目 / 大白话注释：看看这个文件夹里都有啥

        # Filter out only the directories, excluding __pycache__  # 正经注释：过滤出有效目录，排除以__开头的缓存目录 / 大白话注释：只要文件夹，不要缓存那些乱七八糟的东西
        retrievers = [
            item for item in all_items
            if os.path.isdir(os.path.join(current_dir, item)) and not item.startswith('__')
        ]

        return retrievers  # 正经注释：返回有效的检索器目录名列表 / 大白话注释：把找到的搜索引擎名字交出去
    except Exception as e:  # 正经注释：捕获异常并回退到预定义列表 / 大白话注释：出错了就用兜底方案
        logger.error(f"Error getting retrievers: {e}")
        return VALID_RETRIEVERS

"""
研究日志配置模块

【正经注释】
本模块提供 GPT Researcher 研究过程的日志记录与配置功能。包含基于 JSON 格式的研究日志处理器
（JSONResearchHandler），支持结构化地记录研究事件、来源、上下文、报告内容以及成本等数据。
同时提供研究日志系统的初始化函数，可同时生成文本日志文件和 JSON 格式日志文件。

【大白话注释】
这个模块专门管"记日志"这件事。做研究的时候，整个过程需要被记录下来——
什么时候开始查的、查了哪些资料、花了多少钱、最终结果是什么，
全都得一笔笔记下来。它会同时生成两种文件：一个是给人看的纯文本日志，
另一个是给程序看的 JSON 格式日志。
"""
import logging  # 正经注释：导入 Python 标准日志库 / 大白话注释：Python 自带的记日志工具
import json  # 正经注释：导入 JSON 序列化库 / 大白话注释：用来读写 JSON 文件的工具
import os  # 正经注释：导入操作系统接口模块 / 大白话注释：用来操作文件和目录的
from datetime import datetime  # 正经注释：导入日期时间类用于时间戳生成 / 大白话注释：用来获取当前时间
from pathlib import Path  # 正经注释：导入路径操作类 / 大白话注释：更方便地处理文件路径


class JSONResearchHandler:
    """
    基于 JSON 文件的研究日志处理器。

    【正经注释】
    该类将研究过程中的事件和内容数据以结构化 JSON 格式持久化到文件中。
    每次调用 log_event 或 update_content 时，都会立即将最新状态写入磁盘，
    确保即使程序异常退出也不会丢失已记录的数据。

    【大白话注释】
    这个类就是一个"记事本"，把研究过程中的各种信息按 JSON 格式写到文件里。
    每写一条就立刻存盘，不怕程序突然崩溃丢了数据。
    记的内容包括时间戳、各种事件、查询内容、数据来源、研究报告和花费等。

    Args:
        json_file: JSON 日志文件的保存路径
    """
    def __init__(self, json_file):
        """
        初始化 JSON 研究日志处理器。

        【正经注释】
        设置日志文件路径并初始化研究数据结构，包含时间戳、事件列表
        以及内容字段（query、sources、context、report、costs）。

        【大白话注释】
        准备好"记事本"：记住文件存在哪里，然后在里面写上初始信息——
        当前时间、空的事件列表、空的查询/来源/上下文/报告/花费。

        Args:
            json_file: JSON 日志文件的存储路径
        """
        self.json_file = json_file  # 正经注释：保存日志文件路径 / 大白话注释：记住日志文件存在哪个位置
        self.research_data = {  # 正经注释：初始化研究数据结构 / 大白话注释：准备好"记事本"的模板
            "timestamp": datetime.now().isoformat(),  # 正经注释：记录初始化时的 ISO 格式时间戳 / 大白话注释：记下现在几点几分
            "events": [],  # 正经注释：事件列表，初始为空 / 大白话注释：事件清单，暂时啥也没发生
            "content": {  # 正经注释：研究内容数据 / 大白话注释：研究的具体内容
                "query": "",  # 正经注释：查询关键词 / 大白话注释：搜的是啥
                "sources": [],  # 正经注释：来源列表 / 大白话注释：从哪些网站/文档找到的资料
                "context": [],  # 正经注释：上下文列表 / 大白话注释：相关的背景信息
                "report": "",  # 正经注释：研究报告文本 / 大白话注释：最终写出来的报告
                "costs": 0.0  # 正经注释：研究花费金额 / 大白话注释：花了多少钱
            }
        }

    def log_event(self, event_type: str, data: dict):
        """
        记录一条研究事件。

        【正经注释】
        向事件列表中追加一条带有时间戳、类型和数据的事件记录，并立即持久化到 JSON 文件。

        【大白话注释】
        在"记事本"里加一条新记录：几点几分发生了什么事，具体内容是啥，然后马上存盘。

        Args:
            event_type: 事件类型标识，如 "event"、"error" 等
            data: 事件相关的数据字典
        """
        self.research_data["events"].append({  # 正经注释：向事件列表追加新事件 / 大白话注释：往事件清单里加一条
            "timestamp": datetime.now().isoformat(),  # 正经注释：事件发生的时间戳 / 大白话注释：记下事件发生的时间
            "type": event_type,  # 正经注释：事件类型 / 大白话注释：这是什么类型的事件
            "data": data  # 正经注释：事件携带的数据 / 大白话注释：事件的具体内容
        })
        self._save_json()  # 正经注释：立即保存到文件 / 大白话注释：马上存盘

    def update_content(self, key: str, value):
        """
        更新研究内容的指定字段。

        【正经注释】
        修改 research_data["content"] 中指定键的值，并立即持久化到 JSON 文件。

        【大白话注释】
        更新研究内容里的某个字段（比如查询词、报告、花费等），改完马上存盘。

        Args:
            key: 要更新的字段名
            value: 新的字段值
        """
        self.research_data["content"][key] = value  # 正经注释：更新指定字段 / 大白话注释：把某个字段改成新值
        self._save_json()  # 正经注释：立即保存 / 大白话注释：存盘

    def _save_json(self):
        """
        将当前研究数据写入 JSON 文件。

        【正经注释】
        以缩进格式将 research_data 序列化并写入指定的 JSON 文件路径。

        【大白话注释】
        把"记事本"里的内容写到磁盘文件里去，排版好看一点方便以后查看。
        """
        with open(self.json_file, 'w') as f:  # 正经注释：打开文件进行写入 / 大白话注释：打开文件准备写东西
            json.dump(self.research_data, f, indent=2)  # 正经注释：以缩进格式写入 JSON 数据 / 大白话注释：把数据转成 JSON 格式写进去，缩进2格方便看


def setup_research_logging():
    """
    初始化研究日志系统。

    【正经注释】
    创建 logs 目录，生成带时间戳的日志文件路径，配置文件日志处理器和控制台日志处理器，
    设置日志格式，创建 JSONResearchHandler 实例。返回日志文件路径、JSON 文件路径、
    Logger 实例和 JSON Handler 实例的元组。

    【大白话注释】
    搭建整个日志系统的"基础设施"。它会：
    1. 建一个 logs 文件夹（没有的话）
    2. 用当前时间生成日志文件名
    3. 配置好文件日志（写到文件）和控制台日志（打印到屏幕）
    4. 准备好 JSON 格式的日志处理器
    最后把所有这些都交给你用。

    Returns:
        tuple: (log_file路径, json_file路径, research_logger, json_handler)
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")  # 正经注释：创建 logs 目录的 Path 对象 / 大白话注释：指定日志文件夹叫 "logs"
    logs_dir.mkdir(exist_ok=True)  # 正经注释：如果目录不存在则创建 / 大白话注释：文件夹不存在就建一个，存在就算了

    # Generate timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 正经注释：生成时间戳字符串用于文件名 / 大白话注释：拿到当前时间，格式化成年月日_时分秒

    # Create log file paths
    log_file = logs_dir / f"research_{timestamp}.log"  # 正经注释：构造文本日志文件路径 / 大白话注释：纯文本日志文件的名字
    json_file = logs_dir / f"research_{timestamp}.json"  # 正经注释：构造 JSON 日志文件路径 / 大白话注释：JSON 日志文件的名字

    # Configure file handler for research logs
    file_handler = logging.FileHandler(log_file)  # 正经注释：创建文件日志处理器 / 大白话注释：准备一个往文件里写日志的工具
    file_handler.setLevel(logging.INFO)  # 正经注释：设置日志级别为 INFO / 大白话注释：只记录 INFO 及以上级别的日志
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))  # 正经注释：设置日志格式 / 大白话注释：定义每条日志长啥样——时间 - 名字 - 级别 - 内容

    # Get research logger and configure it
    research_logger = logging.getLogger('research')  # 正经注释：获取名为 'research' 的 Logger 实例 / 大白话注释：拿一个专门给"研究"用的日志记录器
    research_logger.setLevel(logging.INFO)  # 正经注释：设置 Logger 级别为 INFO / 大白话注释：只处理 INFO 及以上级别的日志

    # Remove any existing handlers to avoid duplicates
    research_logger.handlers.clear()  # 正经注释：清除已有处理器防止重复记录 / 大白话注释：先把之前的处理器全清掉，免得日志重复

    # Add file handler
    research_logger.addHandler(file_handler)  # 正经注释：添加文件处理器 / 大白话注释：把文件处理器加上去

    # Add stream handler for console output
    console_handler = logging.StreamHandler()  # 正经注释：创建控制台流处理器 / 大白话注释：准备一个往屏幕上打印日志的工具
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))  # 正经注释：设置控制台日志格式 / 大白话注释：屏幕上显示的格式跟文件一样
    research_logger.addHandler(console_handler)  # 正经注释：添加控制台处理器 / 大白话注释：把屏幕处理器也加上去

    # Prevent propagation to root logger to avoid duplicate logs
    research_logger.propagate = False  # 正经注释：禁止向父 Logger 传播以避免重复 / 大白话注释：别把日志往上层的 logger 再传一遍了

    # Create JSON handler
    json_handler = JSONResearchHandler(json_file)  # 正经注释：创建 JSON 格式的研究日志处理器 / 大白话注释：准备 JSON 格式的"记事本"

    return str(log_file), str(json_file), research_logger, json_handler  # 正经注释：返回所有初始化好的日志组件 / 大白话注释：把文件路径、日志器、处理器全交出去

# Create a function to get the logger and JSON handler
def get_research_logger():
    """
    获取研究日志记录器实例。

    【正经注释】
    返回名为 'research' 的全局 Logger 实例，供其他模块使用。

    【大白话注释】
    拿到那个专门记研究日志的工具，哪里需要就在哪里拿。

    Returns:
        Logger: 名为 'research' 的日志记录器
    """
    return logging.getLogger('research')  # 正经注释：返回 'research' Logger / 大白话注释：交出那个叫"research"的日志记录器

def get_json_handler():
    """
    获取 JSON 研究日志处理器实例。

    【正经注释】
    尝试从 research Logger 上获取 json_handler 属性。
    注意：此方法依赖于 setup_research_logging() 中的初始化逻辑，
    如果未调用过初始化函数，则返回 None。

    【大白话注释】
    想拿那个 JSON 格式的"记事本"？试试看吧。
    要是还没初始化过日志系统，那就只能拿到 None（空值）。

    Returns:
        JSONResearchHandler | None: JSON 日志处理器，可能为 None
    """
    return getattr(logging.getLogger('research'), 'json_handler', None)  # 正经注释：安全获取 json_handler 属性 / 大白话注释：尝试拿 json_handler，没有就返回 None

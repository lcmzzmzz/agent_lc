"""
【正经注释】
研究过程日志配置模块。提供 JSON 格式的研究日志处理器（JSONResearchHandler）
和完整的日志系统初始化功能，支持同时输出到文件、控制台和 JSON 文件，
实现研究过程的完整记录与追踪。

【大白话注释】
这个文件帮你把研究过程中发生的所有事情都记录下来。
它会同时写两种日志：一种是给人看的文本日志，一种是给程序看的 JSON 日志。
研究过程中的查询、来源、上下文、报告、花费等全都记下来。
"""

import logging  # 正经注释：标准日志库 / 大白话注释：打日志用的
import json  # 正经注释：JSON 序列化库 / 大白话注释：把数据变成 JSON 格式用的
import os  # 正经注释：操作系统接口 / 大白话注释：跟操作系统打交道用的
from datetime import datetime  # 正经注释：日期时间类型 / 大白话注释：用来记录时间戳
from pathlib import Path  # 正经注释：路径操作库，面向对象的文件系统路径 / 大白话注释：更好用的文件路径工具

class JSONResearchHandler:
    """
    【正经注释】
    JSON 格式研究日志处理器。将研究过程中的事件和内容以 JSON 格式持久化到文件，
    支持记录时间戳、事件类型、查询内容、来源列表、上下文、报告和成本等信息。

    【大白话注释】
    这个类专门把研究过程的所有信息保存成 JSON 文件。
    每次有什么新事件或者内容更新，它都会立刻写到文件里，
    方便以后用程序来分析研究过程。
    """
    def __init__(self, json_file):
        """
        【正经注释】
        初始化 JSON 研究日志处理器。创建初始的研究数据结构，
        包含时间戳、事件列表和内容字段（查询、来源、上下文、报告、成本）。

        【大白话注释】
        初始化的时候准备好 JSON 文件的路径和一个空的数据框架，
        里面有事件列表和内容槽位（查询、来源、上下文、报告、花费）。

        Args:
            json_file: JSON 日志文件的路径。
        """
        self.json_file = json_file  # 正经注释：保存 JSON 文件路径 / 大白话注释：记住要把日志写到哪个文件
        self.research_data = {  # 正经注释：初始化研究数据结构 / 大白话注释：准备好一个空的数据模板
            "timestamp": datetime.now().isoformat(),  # 正经注释：记录初始化时间 / 大白话注释：记下是什么时候开始的
            "events": [],  # 正经注释：事件列表 / 大白话注释：用来存所有发生的事件
            "content": {
                "query": "",  # 正经注释：研究查询内容 / 大白话注释：用户问的什么问题
                "sources": [],  # 正经注释：信息来源列表 / 大白话注释：从哪里找的资料
                "context": [],  # 正经注释：上下文内容列表 / 大白话注释：收集到的背景信息
                "report": "",  # 正经注释：研究报告内容 / 大白话注释：最终生成的报告
                "costs": 0.0  # 正经注释：研究成本 / 大白话注释：花了多少钱
            }
        }

    def log_event(self, event_type: str, data: dict):
        """
        【正经注释】
        记录一个研究事件。将事件类型、时间戳和相关数据添加到事件列表，
        并立即持久化到 JSON 文件。

        【大白话注释】
        记下发生了一件什么事。比如"开始搜索"、"找到来源"之类的。
        记完就立刻写到文件里，不怕程序崩溃丢数据。

        Args:
            event_type: 事件类型标识符。
            data: 事件相关数据字典。
        """
        self.research_data["events"].append({  # 正经注释：追加新事件到事件列表 / 大白话注释：往事件列表里加一条记录
            "timestamp": datetime.now().isoformat(),  # 正经注释：记录事件发生时间 / 大白话注释：记下什么时候发生的
            "type": event_type,  # 正经注释：事件类型 / 大白话注释：发生了什么事
            "data": data  # 正经注释：事件数据 / 大白话注释：具体内容是什么
        })
        self._save_json()  # 正经注释：立即保存到文件 / 大白话注释：马上写到文件里

    def update_content(self, key: str, value):
        """
        【正经注释】
        更新研究内容的指定字段。修改内容字典中对应键的值，并立即持久化。

        【大白话注释】
        更新研究数据的某个字段。比如找到了新来源、生成了报告等，
        更新完就立刻写到文件里。

        Args:
            key: 内容字段的键名。
            value: 要更新的值。
        """
        self.research_data["content"][key] = value  # 正经注释：更新指定字段 / 大白话注释：把对应的值改掉
        self._save_json()  # 正经注释：立即保存到文件 / 大白话注释：马上写到文件里

    def _save_json(self):
        """
        【正经注释】
        将当前研究数据以缩进格式写入 JSON 文件。使用 UTF-8 编码，
        确保 JSON 文件的可读性。

        【大白话注释】
        把当前所有研究数据写到 JSON 文件里。用缩进格式写，让人也能看懂。
        """
        with open(self.json_file, 'w') as f:  # 正经注释：打开 JSON 文件准备写入 / 大白话注释：打开文件准备写
            json.dump(self.research_data, f, indent=2)  # 正经注释：以缩进格式写入 JSON 数据 / 大白话注释：用好看点的格式写进去

def setup_research_logging():
    """
    【正经注释】
    初始化研究日志系统。创建 logs 目录，生成带时间戳的日志文件名，
    配置文件处理器和控制台处理器，并创建 JSON 研究日志处理器。
    返回日志文件路径、JSON 文件路径、日志记录器和 JSON 处理器。

    【大白话注释】
    把研究用的日志系统整个搭好。创建日志目录，准备好文本日志和 JSON 日志两个文件，
    配置好日志格式，最后把所有东西都返回出去，方便其他地方使用。

    Returns:
        (log_file, json_file, research_logger, json_handler) 四元组。
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")  # 正经注释：创建 logs 目录路径对象 / 大白话注释：指定日志文件夹
    logs_dir.mkdir(exist_ok=True)  # 正经注释：如果目录不存在则创建 / 大白话注释：没有就建一个，有就不动

    # Generate timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 正经注释：生成时间戳用于日志文件名 / 大白话注释：用当前时间给日志文件起个独一无二的名字

    # Create log file paths
    log_file = logs_dir / f"research_{timestamp}.log"  # 正经注释：创建文本日志文件路径 / 大白话注释：文本日志的完整路径
    json_file = logs_dir / f"research_{timestamp}.json"  # 正经注释：创建 JSON 日志文件路径 / 大白话注释：JSON 日志的完整路径

    # Configure file handler for research logs
    file_handler = logging.FileHandler(log_file)  # 正经注释：创建文件日志处理器 / 大白话注释：创建一个往文件里写日志的处理器
    file_handler.setLevel(logging.INFO)  # 正经注释：设置文件日志级别为 INFO / 大白话注释：文件里只记 INFO 及以上级别的日志
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))  # 正经注释：设置文件日志格式 / 大白话注释：规定日志在文件里长什么样

    # Get research logger and configure it
    research_logger = logging.getLogger('research')  # 正经注释：获取研究日志记录器 / 大白话注释：拿一个专门给研究用的日志器
    research_logger.setLevel(logging.INFO)  # 正经注释：设置研究日志级别 / 大白话注释：只记 INFO 及以上的

    # Remove any existing handlers to avoid duplicates
    research_logger.handlers.clear()  # 正经注释：清除已有处理器避免重复 / 大白话注释：把之前的处理器都清掉，防止日志打印两遍

    # Add file handler
    research_logger.addHandler(file_handler)  # 正经注释：添加文件处理器 / 大白话注释：装上文件处理器，日志会写到文件里

    # Add stream handler for console output
    console_handler = logging.StreamHandler()  # 正经注释：创建控制台日志处理器 / 大白话注释：创建一个往终端输出日志的处理器
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))  # 正经注释：设置控制台日志格式 / 大白话注释：规定日志在终端里长什么样
    research_logger.addHandler(console_handler)  # 正经注释：添加控制台处理器 / 大白话注释：装上控制台处理器，日志会显示在终端里

    # Prevent propagation to root logger to avoid duplicate logs
    research_logger.propagate = False  # 正经注释：禁止向根日志记录器传播 / 大白话注释：不让日志往上传播，防止重复

    # Create JSON handler
    json_handler = JSONResearchHandler(json_file)  # 正经注释：创建 JSON 研究日志处理器 / 大白话注释：创建一个专门写 JSON 日志的处理器

    return str(log_file), str(json_file), research_logger, json_handler  # 正经注释：返回所有日志相关对象 / 大白话注释：把所有东西都返回出去

def get_research_logger():
    """
    【正经注释】
    获取研究日志记录器实例。返回名为 'research' 的 Logger 对象。

    【大白话注释】
    拿到研究专用的日志器。在其他地方想打研究相关的日志就调这个函数。

    Returns:
        名为 'research' 的 Logger 实例。
    """
    return logging.getLogger('research')  # 正经注释：获取并返回研究日志记录器 / 大白话注释：返回那个叫 'research' 的日志器

def get_json_handler():
    """
    【正经注释】
    获取研究日志记录器上关联的 JSON 处理器实例。如果不存在则返回 None。

    【大白话注释】
    试着拿到那个写 JSON 日志的处理器。如果没设置过就返回 None。

    Returns:
        JSONResearchHandler 实例或 None。
    """
    return getattr(logging.getLogger('research'), 'json_handler', None)  # 正经注释：安全地获取 json_handler 属性 / 大白话注释：有就拿，没有就返回 None

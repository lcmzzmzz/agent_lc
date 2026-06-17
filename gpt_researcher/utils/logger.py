"""
【正经注释】
日志格式化工具模块。提供带颜色编码的日志格式化器，支持按日志级别显示不同颜色，
以及自定义彩色消息功能。主要用于爬虫组件的日志输出美化。

【大白话注释】
这个文件让日志更好看。不同级别的日志（调试、信息、警告、错误）用不同的颜色显示，
在终端里一眼就能看出哪个是错误、哪个是普通信息。
"""

import logging  # 正经注释：标准日志库 / 大白话注释：打日志用的
import sys  # 正经注释：系统模块，用于检测终端类型 / 大白话注释：用来判断是不是在终端里运行
from copy import copy  # 正经注释：导入浅拷贝函数 / 大白话注释：复制日志记录用的，不改原来的
from typing import Literal  # 正经注释：导入字面量类型，用于精确类型标注 / 大白话注释：限制参数只能填指定的几个字符串

import click  # 正经注释：Click 库，用于终端颜色输出 / 大白话注释：让文字在终端里显示颜色的工具

TRACE_LOG_LEVEL = 5  # 正经注释：自定义的 TRACE 日志级别，数值低于 DEBUG(10) / 大白话注释：比调试还低的日志级别，超级详细的那种


def get_formatted_logger():
    """
    【正经注释】
    创建并返回一个配置好格式化器的爬虫日志记录器。使用 DefaultFormatter 设置
    彩色输出格式，包含日志级别前缀和时间戳。避免重复添加处理器。

    【大白话注释】
    给你一个好看的日志器。它会自动加上颜色和时间，让你在终端里看得更清楚。
    如果你已经拿过一个了，不会再重复添加。

    Returns:
        配置好的 Logger 实例。
    """
    logger = logging.getLogger("scraper")  # 正经注释：获取名为 'scraper' 的日志记录器 / 大白话注释：拿一个专门给爬虫用的日志器
    # Set the logging level
    logger.setLevel(logging.INFO)  # 正经注释：设置日志级别为 INFO / 大白话注释：只显示 INFO 及以上级别的日志

    # Check if the logger already has handlers to avoid duplicates
    if not logger.handlers:  # 正经注释：检查是否已有处理器，避免重复添加 / 大白话注释：如果已经有了就不重复加
        # Create a handler
        handler = logging.StreamHandler()  # 正经注释：创建标准错误流处理器 / 大白话注释：创建一个往终端输出的处理器

        # Create a formatter using DefaultFormatter
        formatter = DefaultFormatter(
            "%(levelprefix)s [%(asctime)s] %(message)s",
            datefmt="%H:%M:%S"
        )  # 正经注释：使用 DefaultFormatter 创建彩色格式化器 / 大白话注释：创建一个好看的颜色格式化器

        # Set the formatter for the handler
        handler.setFormatter(formatter)  # 正经注释：为处理器设置格式化器 / 大白话注释：让处理器用这个好看的格式

        # Add the handler to the logger
        logger.addHandler(handler)  # 正经注释：将处理器添加到日志记录器 / 大白话注释：给日志器装上这个处理器

    # Disable propagation to prevent duplicate logging from parent loggers
    logger.propagate = False  # 正经注释：禁止向父日志记录器传播，避免重复日志 / 大白话注释：不让日志往上传播，防止同样的日志打印两次

    return logger


class ColourizedFormatter(logging.Formatter):
    """
    【正经注释】
    自定义日志格式化器类，支持按日志级别进行颜色编码输出。
    如果日志调用包含 extras={"color_message": ...}，则使用彩色消息替代纯文本消息。

    【大白话注释】
    这是一个给日志上颜色的格式化器。不同级别的日志用不同的颜色，
    还支持自定义彩色消息。比如错误是红的，信息是绿的。
    """

    level_name_colors = {  # 正经注释：日志级别到颜色映射表 / 大白话注释：哪个级别用什么颜色，都在这里定义
        TRACE_LOG_LEVEL: lambda level_name: click.style(str(level_name), fg="blue"),  # 正经注释：TRACE 级别使用蓝色 / 大白话注释：超级详细的信息用蓝色
        logging.DEBUG: lambda level_name: click.style(str(level_name), fg="cyan"),  # 正经注释：DEBUG 级别使用青色 / 大白话注释：调试信息用青色
        logging.INFO: lambda level_name: click.style(str(level_name), fg="green"),  # 正经注释：INFO 级别使用绿色 / 大白话注释：普通信息用绿色
        logging.WARNING: lambda level_name: click.style(str(level_name), fg="yellow"),  # 正经注释：WARNING 级别使用黄色 / 大白话注释：警告用黄色
        logging.ERROR: lambda level_name: click.style(str(level_name), fg="red"),  # 正经注释：ERROR 级别使用红色 / 大白话注释：错误用红色
        logging.CRITICAL: lambda level_name: click.style(str(level_name), fg="bright_red"),  # 正经注释：CRITICAL 级别使用亮红色 / 大白话注释：严重错误用亮红色
    }

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        use_colors: bool | None = None,
    ):
        """
        【正经注释】
        初始化彩色格式化器。如果未明确指定 use_colors，则根据标准输出是否为终端自动决定。

        【大白话注释】
        创建格式化器的时候，你可以指定要不要颜色。如果不指定，
        它会自动判断：在终端里就用颜色，不在终端里（比如写到文件）就不用。

        Args:
            fmt: 格式字符串。
            datefmt: 日期格式字符串。
            style: 格式化风格（%、{、$）。
            use_colors: 是否使用颜色，None 表示自动检测。
        """
        if use_colors in (True, False):  # 正经注释：明确指定颜色设置 / 大白话注释：你说了算
            self.use_colors = use_colors
        else:  # 正经注释：自动检测是否在终端环境中 / 大白话注释：你不说就自动判断，在终端里就用颜色
            self.use_colors = sys.stdout.isatty()
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)  # 正经注释：调用父类初始化 / 大白话注释：让父类也初始化一下

    def color_level_name(self, level_name: str, level_no: int) -> str:
        """
        【正经注释】
        根据日志级别编号获取对应颜色的级别名称。如果级别不在预定义映射中，
        使用默认的无颜色输出。

        【大白话注释】
        给日志级别的名字上颜色。认识的颜色就上色，不认识的就保持原样。

        Args:
            level_name: 日志级别名称。
            level_no: 日志级别编号。

        Returns:
            带颜色的级别名称字符串。
        """
        def default(level_name: str) -> str:
            return str(level_name)  # pragma: no cover  # 正经注释：默认不应用颜色 / 大白话注释：不认识的级别就不上色

        func = self.level_name_colors.get(level_no, default)  # 正经注释：从映射表中获取颜色函数 / 大白话注释：查表看看这个级别用什么颜色
        return func(level_name)

    def should_use_colors(self) -> bool:
        """
        【正经注释】
        判断是否应使用颜色输出。子类可覆盖此方法以自定义颜色决策逻辑。

        【大白话注释】
        要不要用颜色？子类可以覆盖这个方法来改变决定。
        """
        return True  # pragma: no cover

    def formatMessage(self, record: logging.LogRecord) -> str:
        """
        【正经注释】
        格式化单条日志消息。根据日志级别添加颜色，支持通过 color_message 替换消息内容，
        并对齐级别前缀的宽度。

        【大白话注释】
        把一条日志打扮好看。给级别名字上颜色，把内容对齐，
        如果有自定义的彩色消息就替换掉原来的。

        Args:
            record: 日志记录对象。

        Returns:
            格式化后的日志字符串。
        """
        recordcopy = copy(record)  # 正经注释：浅拷贝日志记录，避免修改原始对象 / 大白话注释：复制一份，不改原来的
        levelname = recordcopy.levelname  # 正经注释：获取级别名称 / 大白话注释：拿到级别名字
        seperator = " " * (8 - len(recordcopy.levelname))  # 正经注释：计算对齐用的空格填充 / 大白话注释：算出要补多少空格让输出对齐
        if self.use_colors:  # 正经注释：启用颜色时处理 / 大白话注释：要上颜色的话
            levelname = self.color_level_name(levelname, recordcopy.levelno)  # 正经注释：给级别名称上色 / 大白话注释：给级别名字涂上颜色
            if "color_message" in recordcopy.__dict__:  # 正经注释：检查是否有自定义彩色消息 / 大白话注释：如果有特别指定要显示的彩色消息
                recordcopy.msg = recordcopy.__dict__["color_message"]  # 正经注释：替换消息内容 / 大白话注释：用彩色消息替换掉原来的
                recordcopy.__dict__["message"] = recordcopy.getMessage()  # 正经注释：更新格式化后的消息 / 大白话注释：更新一下消息内容
        recordcopy.__dict__["levelprefix"] = levelname + ":" + seperator  # 正经注释：设置带颜色的级别前缀 / 大白话注释：把级别名字和空格拼在一起
        return super().formatMessage(recordcopy)  # 正经注释：调用父类格式化方法 / 大白话注释：让父类完成最终的格式化


class DefaultFormatter(ColourizedFormatter):
    """
    【正经注释】
    默认日志格式化器，继承自 ColourizedFormatter。根据标准错误流是否为终端
    来决定是否使用颜色输出。

    【大白话注释】
    这是默认的格式化器。它会自动判断：如果你在终端里跑就用颜色，
    不在终端里（比如重定向到文件了）就不用颜色。
    """
    def should_use_colors(self) -> bool:
        """
        【正经注释】
        根据标准错误流是否连接到终端来决定颜色输出。

        【大白话注释】
        看看 stderr 是不是连着终端。是的话就用颜色，不是的话就不用。

        Returns:
            是否使用颜色的布尔值。
        """
        return sys.stderr.isatty()  # pragma: no cover  # 正经注释：检测 stderr 是否为终端 / 大白话注释：判断错误输出是不是在终端里

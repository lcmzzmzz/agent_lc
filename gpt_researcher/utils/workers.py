"""
【正经注释】
并发工作池模块。提供基于信号量和全局速率限制器的异步并发控制，
支持在多个 WorkerPool 实例之间共享全局速率限制，防止并发研究任务
压垮有速率限制的 API。

【大白话注释】
这个文件管理"干活的线程"。你可以指定最多几个线程同时干活，
还能设置全局的请求速度限制。不管你开了几个研究任务，
都不会超过你设定的请求速度上限。
"""

import asyncio  # 正经注释：异步 I/O 库，用于信号量和异步上下文管理 / 大白话注释：异步编程用的，管着"谁先谁后"
import time  # 正经注释：时间模块 / 大白话注释：用来计时
from concurrent.futures import ThreadPoolExecutor  # 正经注释：线程池执行器，用于管理并发线程 / 大白话注释：管理一群干活的线程
from contextlib import asynccontextmanager  # 正经注释：异步上下文管理器装饰器 / 大白话注释：让 async with 能用上自定义的清理逻辑
from .rate_limiter import get_global_rate_limiter  # 正经注释：导入全局速率限制器获取函数 / 大白话注释：导入那个管"别太快"的工具


class WorkerPool:
    """
    【正经注释】
    工作池类。结合信号量和全局速率限制器实现双重并发控制：
    信号量控制单个池内的并发操作数，全局速率限制器控制所有池的请求频率。

    【大白话注释】
    一个"工人管理器"。你告诉它最多几个工人同时干活（信号量控制），
    以及两次请求之间最少隔多久（全局速率限制）。
    它保证不管开几个研究任务，都不会把 API 搞崩。
    """
    def __init__(self, max_workers: int, rate_limit_delay: float = 0.0):
        """
        【正经注释】
        初始化工作池，配置并发数和速率限制。创建线程池执行器、异步信号量，
        并配置全局速率限制器的延迟参数。

        【大白话注释】
        创建工作池。你需要告诉它：
        1. 最多几个工人同时干活
        2. 两次请求之间至少要隔多少秒（全局生效）

        注意：速率限制是全局共享的。如果你有多个研究任务在跑，
        它们会共享同一个速率限制，防止请求太频繁。

        Args:
            max_workers: 最大并发工作者数量。
            rate_limit_delay: 全局请求间最小秒数（0 表示不限制）。
                             例如设 6.0 表示每分钟最多 10 次请求（Firecrawl 免费版）。
        """
        self.max_workers = max_workers  # 正经注释：保存最大并发数 / 大白话注释：记住最多几个工人
        self.rate_limit_delay = rate_limit_delay  # 正经注释：保存速率限制延迟 / 大白话注释：记住最小间隔时间
        self.executor = ThreadPoolExecutor(max_workers=max_workers)  # 正经注释：创建线程池执行器 / 大白话注释：创建线程池
        self.semaphore = asyncio.Semaphore(max_workers)  # 正经注释：创建异步信号量控制并发 / 大白话注释：创建信号量，用来限制同时干活的数量

        # Configure the global rate limiter
        # All WorkerPools share the same rate limiter instance
        global_limiter = get_global_rate_limiter()  # 正经注释：获取全局速率限制器单例 / 大白话注释：拿到那个全局唯一的速率管家
        global_limiter.configure(rate_limit_delay)  # 正经注释：配置全局速率限制 / 大白话注释：告诉管家最小间隔是多少

    @asynccontextmanager
    async def throttle(self):
        """
        【正经注释】
        节流上下文管理器。同时使用信号量和全局速率限制器实现双重控制：
        信号量控制当前池内的并发操作数，全局速率限制器控制所有池的请求频率。

        【大白话注释】
        用 async with 包裹你的代码，它会自动帮你控制速度：
        1. 信号量管着"同时干活的最多几个人"
        2. 全局速率限制器管着"什么时候才能发下一个请求"

        用法：
            async with pool.throttle():
                # 在这里发请求，不会太快也不会太多

        Note:
            即使有多个 GPTResearcher 实例同时运行（比如深度研究模式），
            总请求率也会保持在限制范围内。
        """
        async with self.semaphore:  # 正经注释：获取信号量，控制并发数 / 大白话注释：排队拿号，最多 max_workers 个人同时干活
            # Use global rate limiter (shared across all WorkerPools)
            global_limiter = get_global_rate_limiter()  # 正经注释：获取全局速率限制器 / 大白话注释：拿到那个全局管家
            await global_limiter.wait_if_needed()  # 正经注释：根据全局速率限制等待 / 大白话注释：管家说等就等，说走就走
            yield  # 正经注释：执行被管理的代码块 / 大白话注释：轮到你了，去干活吧

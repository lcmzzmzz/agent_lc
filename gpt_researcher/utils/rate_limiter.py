"""
【正经注释】
全局速率限制器模块。实现单例模式的全局速率限制器，确保 SCRAPER_RATE_LIMIT_DELAY
在所有 WorkerPool 实例之间全局生效，防止多个并发研究任务压垮有速率限制的 API（如 Firecrawl）。

【大白话注释】
这个文件管着"别太快"这件事。比如某个 API 说你每分钟最多请求 10 次，
这个速率限制器就帮你盯着，不管你开了几个研究任务，都不会超过限制。
用的是"全局单例"模式，整个程序就一个实例，大家共享。
"""
import asyncio  # 正经注释：异步 I/O 库，用于异步锁和异步等待 / 大白话注释：异步编程用的，让程序等待的时候不阻塞
import time  # 正经注释：时间模块，用于获取当前时间戳 / 大白话注释：用来获取现在是几点几分几秒
from typing import ClassVar  # 正经注释：类变量类型标注，表示该属性属于类而非实例 / 大白话注释：标记这个变量是整个类共享的，不是每个实例自己一份


class GlobalRateLimiter:
    """
    【正经注释】
    单例全局速率限制器。确保整个应用程序中所有爬虫请求之间的最小间隔，
    无论有多少个 WorkerPool 或 GPTResearcher 实例在运行。

    【大白话注释】
    全局唯一的"慢一点"管家。不管你开了几个研究任务、几个工作池，
    它都管着，确保请求不要太频繁，不会把 API 服务器搞崩溃。
    """

    _instance: ClassVar['GlobalRateLimiter'] = None  # 正经注释：单例实例引用 / 大白话注释：全局唯一的那个实例，谁调都是同一个
    _lock: ClassVar[asyncio.Lock] = None  # 正经注释：异步锁，保证并发安全 / 大白话注释：一把锁，防止好几个人同时改时间戳

    def __new__(cls):
        """
        【正经注释】
        实现__new__方法以支持单例模式。首次调用时创建实例，后续调用返回同一实例。

        【大白话注释】
        不管你new多少次，都只给你同一个对象。第一次才真正创建，后面都是返回那个老的。
        """
        if cls._instance is None:  # 正经注释：首次创建实例 / 大白话注释：还没有实例就建一个
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # 正经注释：标记未初始化 / 大白话注释：标记还没初始化好
        return cls._instance  # 正经注释：返回单例实例 / 大白话注释：把唯一的那个实例给你

    def __init__(self):
        """
        【正经注释】
        初始化全局速率限制器（仅执行一次）。设置上次请求时间、速率限制延迟和初始化标志。

        【大白话注释】
        初始化这个管家。记住上次请求是什么时候，限制间隔是多少秒。
        只会初始化一次，第二次开始就跳过了。

        Note:
            使用 _initialized 标志确保初始化逻辑仅在首次创建时执行。
        """
        if self._initialized:  # 正经注释：已初始化则跳过 / 大白话注释：已经初始化过了就别再来了
            return

        self.last_request_time = 0.0  # 正经注释：上次请求的时间戳 / 大白话注释：记着上次请求是什么时候
        self.rate_limit_delay = 0.0  # 正经注释：请求间隔限制（秒） / 大白话注释：两次请求之间最少隔多少秒
        self._initialized = True  # 正经注释：标记已完成初始化 / 大白话注释：标记已经初始化好了

        # Create lock at class level to ensure it's shared across all instances
        if GlobalRateLimiter._lock is None:  # 正经注释：在类级别创建共享锁 / 大白话注释：锁还没创建就先留着
            # Note: This will be properly initialized when first accessed in an async context
            GlobalRateLimiter._lock = None  # 正经注释：锁将在异步上下文中首次访问时初始化 / 大白话注释：等真正要用的时候再创建锁

    @classmethod
    def get_lock(cls):
        """
        【正经注释】
        获取或创建异步锁。必须在异步上下文中调用以确保锁的正确初始化。

        【大白话注释】
        拿到那把锁。如果锁还没创建就现场创建一个。
        注意：得在异步环境里调，不然可能出问题。

        Returns:
            asyncio.Lock 实例。
        """
        if cls._lock is None:  # 正经注释：锁不存在时创建 / 大白话注释：没锁就造一把
            cls._lock = asyncio.Lock()  # 正经注释：创建新的异步锁 / 大白话注释：造一把异步锁
        return cls._lock  # 正经注释：返回锁实例 / 大白话注释：把锁给你

    def configure(self, rate_limit_delay: float):
        """
        【正经注释】
        配置全局速率限制延迟。设置请求之间的最小间隔时间。

        【大白话注释】
        告诉管家"两次请求之间至少要隔多少秒"。设成 0 就是不限制。

        Args:
            rate_limit_delay: 请求间最小秒数（0 表示无限制）。
        """
        self.rate_limit_delay = rate_limit_delay  # 正经注释：设置速率限制延迟 / 大白话注释：记住最小间隔时间

    async def wait_if_needed(self):
        """
        【正经注释】
        根据速率限制配置，在必要时进行等待。使用异步锁确保并发安全，
        计算距离上次请求的时间差，如果未达到最小间隔则异步等待剩余时间。

        【大白话注释】
        在发请求之前调这个方法。它会看看距上次请求过了多久，
        如果还不够间隔时间就等一会儿，够了就直接放行。
        用了锁保证多个任务不会抢着发请求。

        Note:
            此方法确保无论有多少个 WorkerPool 在运行，
            SCRAPER_RATE_LIMIT_DELAY 都会被全局遵守。
        """
        if self.rate_limit_delay <= 0:  # 正经注释：无速率限制时直接返回 / 大白话注释：不限制就直接过
            return  # No rate limiting

        lock = self.get_lock()  # 正经注释：获取异步锁 / 大白话注释：拿锁
        async with lock:  # 正经注释：加锁保证同一时刻只有一个请求在判断间隔 / 大白话注释：锁上，一个一个来
            current_time = time.time()  # 正经注释：获取当前时间戳 / 大白话注释：现在几点了
            time_since_last = current_time - self.last_request_time  # 正经注释：计算距上次请求的时间差 / 大白话注释：距离上次请求过了多久

            if time_since_last < self.rate_limit_delay:  # 正经注释：未达到最小间隔，需要等待 / 大白话注释：时间还不够，得等一会
                sleep_time = self.rate_limit_delay - time_since_last  # 正经注释：计算需要等待的剩余时间 / 大白话注释：还要等多久
                await asyncio.sleep(sleep_time)  # 正经注释：异步等待 / 大白话注释：等着吧

            self.last_request_time = time.time()  # 正经注释：更新上次请求时间 / 大白话注释：记下这次请求是什么时候

    def reset(self):
        """
        【正经注释】
        重置速率限制器状态。将上次请求时间重置为 0，主要用于测试场景。

        【大白话注释】
        清零。把"上次请求时间"重置为 0，一般测试的时候用，
        这样就不会因为之前的时间戳影响测试结果。
        """
        self.last_request_time = 0.0  # 正经注释：重置上次请求时间 / 大白话注释：把时间清零


# Singleton instance
_global_rate_limiter = GlobalRateLimiter()  # 正经注释：创建全局单例实例 / 大白话注释：创建全局唯一的那个速率限制器


def get_global_rate_limiter() -> GlobalRateLimiter:
    """
    【正经注释】
    获取全局速率限制器单例实例。

    【大白话注释】
    拿到那个全局唯一的速率限制器。谁调都是同一个对象。

    Returns:
        GlobalRateLimiter 单例实例。
    """
    return _global_rate_limiter  # 正经注释：返回单例实例 / 大白话注释：把那个唯一的管家给你

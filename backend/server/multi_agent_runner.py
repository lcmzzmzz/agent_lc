"""
多代理运行器模块

【正经注释】
本模块负责解析和调度多代理（Multi-Agent）研究任务的执行。
它提供了自动发现并导入多代理系统（优先使用 LangGraph 版 multi_agents，
回退到 AG2 版 multi_agents_ag2）的能力，并通过统一的异步接口对外暴露
run_research_task 函数供上层调用。

【大白话注释】
这个模块是个"调度员"，专门负责把研究任务交给多代理系统去跑。
它会先试试用 LangGraph 版的多代理系统，要是没装就换 AG2 版的。
反正不管用哪个版本，对外都提供一个统一的接口，让上面的代码不用关心细节。
"""
import os  # 正经注释：导入操作系统接口模块 / 大白话注释：用来操作文件路径
import sys  # 正经注释：导入系统相关模块，用于修改模块搜索路径 / 大白话注释：用来改 Python 找模块的路径
from typing import Any, Awaitable, Callable  # 正经注释：导入类型提示相关 / 大白话注释：告诉 Python 这些变量是啥类型

RunResearchTask = Callable[..., Awaitable[Any]]  # 正经注释：定义研究任务函数的类型别名 / 大白话注释：给"跑研究任务的函数"取了个类型别名，方便后面用


def _ensure_repo_root_on_path() -> None:
    """
    确保项目根目录在 Python 模块搜索路径中。

    【正经注释】
    将项目顶层目录添加到 sys.path 中，使得多代理模块（如 multi_agents、multi_agents_ag2）
    可以被正确导入。仅在路径不存在时才添加，避免重复。

    【大白话注释】
    告诉 Python："除了默认的地方，还得去项目根目录找模块哦！"
    这样才能正确导入多代理系统的代码。不会重复添加同一个路径。
    """
    """Ensure top-level repo root is importable for multi-agent modules."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # 正经注释：计算项目根目录的绝对路径 / 大白话注释：往上跳两级目录，找到项目根目录
    if repo_root not in sys.path:  # 正经注释：检查路径是否已在搜索路径中 / 大白话注释：看看这个路径加过没有
        sys.path.insert(0, repo_root)  # 正经注释：将根目录插入到搜索路径最前面 / 大白话注释：加到最前面，优先从这里找


def _resolve_run_research_task() -> RunResearchTask:
    """
    解析并返回可用的多代理研究任务执行函数。

    【正经注释】
    依次尝试从 multi_agents.main 和 multi_agents_ag2.main 中导入 run_research_task 函数。
    优先使用 LangGraph 版本，若不可用则回退到 AG2 版本。两者均不可用时抛出 ImportError。

    【大白话注释】
    先试试 LangGraph 版的多代理系统有没有装，装了就用它。
    没装的话再试试 AG2 版的。
    两个都没装就报错："找不到可用的多代理系统！"

    Returns:
        RunResearchTask: 可用的研究任务执行函数

    Raises:
        ImportError: 当两个多代理系统模块均无法导入时
    """
    _ensure_repo_root_on_path()  # 正经注释：确保项目根目录在搜索路径中 / 大白话注释：先确保能找到模块

    try:
        from multi_agents.main import run_research_task  # 正经注释：尝试导入 LangGraph 版多代理系统 / 大白话注释：试试 LangGraph 版
        return run_research_task
    except Exception:
        try:
            from multi_agents_ag2.main import run_research_task  # 正经注释：尝试导入 AG2 版多代理系统 / 大白话注释：LangGraph 不行就试 AG2 版
            return run_research_task
        except Exception as ag2_error:
            raise ImportError(  # 正经注释：两个版本都无法导入时抛出异常 / 大白话注释：两个都不行，只能报错了
                "Could not import run_research_task from multi_agents or multi_agents_ag2"
            ) from ag2_error


async def run_multi_agent_task(*args, **kwargs) -> Any:
    """
    异步执行多代理研究任务。

    【正经注释】
    通过 _resolve_run_research_task() 获取可用的研究任务函数，
    并以异步方式调用该函数，将所有位置参数和关键字参数透传给它。

    【大白话注释】
    找到能用的多代理系统，然后把任务交给它去跑。
    你传什么参数进来，它就原封不动地传过去。

    Args:
        *args: 透传给底层研究任务函数的位置参数
        **kwargs: 透传给底层研究任务函数的关键字参数

    Returns:
        Any: 底层研究任务函数的返回值
    """
    run_research_task = _resolve_run_research_task()  # 正经注释：获取可用的研究任务函数 / 大白话注释：找到能用的多代理系统
    return await run_research_task(*args, **kwargs)  # 正经注释：异步调用研究任务函数并返回结果 / 大白话注释：让它跑起来，等着结果

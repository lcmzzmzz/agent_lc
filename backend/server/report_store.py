"""
报告存储模块

【正经注释】
本模块实现了基于 JSON 文件的报告持久化存储。通过异步文件 I/O 和 asyncio.Lock 实现并发安全的
报告增删改查操作。所有数据以 JSON 格式存储在单一文件中，使用临时文件+原子替换的方式确保
写入操作的原子性和数据完整性。

【大白话注释】
这个模块管的是"把研究报告存到磁盘上"这件事。
所有报告都存在一个 JSON 文件里，用"锁"来保证同时只有一个人在写，
免得大家同时写把文件搞坏了。写文件的时候会先写临时文件，再替换原文件，
这样就算写到一半断电了也不会丢数据。
"""
import asyncio  # 正经注释：导入异步 I/O 库 / 大白话注释：Python 的异步编程库
import json  # 正经注释：导入 JSON 序列化库 / 大白话注释：用来读写 JSON 的工具
from pathlib import Path  # 正经注释：导入路径操作类 / 大白话注释：处理文件路径的工具
from typing import Any, Dict, List  # 正经注释：导入类型提示相关 / 大白话注释：告诉 Python 这些变量是啥类型


class ReportStore:
    """
    基于 JSON 文件的异步报告存储管理器。

    【正经注释】
    提供线程安全（基于 asyncio.Lock）的报告 CRUD 操作。所有读写操作共享同一个异步锁，
    确保并发环境下数据一致性。数据以字典形式存储在 JSON 文件中，键为报告 ID，值为报告数据。

    【大白话注释】
    这就是个"报告仓库"，用 JSON 文件来存所有报告。
    有个"锁"机制，保证同一时间只有一个人在读或写，不会打架。
    你可以往里面放报告、查报告、改报告、删报告。

    Args:
        path: JSON 存储文件的路径
    """
    def __init__(self, path: Path):
        """
        初始化报告存储管理器。

        【正经注释】
        设置存储文件路径并创建异步锁实例。

        【大白话注释】
        记住文件存在哪里，准备一把"锁"。

        Args:
            path: JSON 存储文件的路径
        """
        self._path = path  # 正经注释：保存存储文件路径 / 大白话注释：记住文件在哪
        self._lock = asyncio.Lock()  # 正经注释：创建异步锁保证并发安全 / 大白话注释：准备一把"锁"，防止同时写文件打架

    async def _ensure_parent_dir(self) -> None:
        """
        确保存储文件的父目录存在。

        【正经注释】
        递归创建存储文件所在的所有父目录，如果目录已存在则不做任何操作。

        【大白话注释】
        检查一下文件夹在不在，不在就建一个，免得写文件时报错。
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)  # 正经注释：递归创建父目录 / 大白话注释：连上级目录一起建，有的话就不建

    async def _read_all_unlocked(self) -> Dict[str, Dict[str, Any]]:
        """
        读取 JSON 文件中的所有报告数据（不加锁）。

        【正经注释】
        从存储文件中读取并解析 JSON 数据。如果文件不存在、内容为空或解析失败，
        均返回空字典。此方法不获取锁，应由调用方在持锁状态下调用。

        【大白话注释】
        把文件里所有的报告都读出来。文件不存在或者内容有问题就返回空的。
        注意：这个方法不会自己加锁，得让调用它的人来加锁。

        Returns:
            Dict[str, Dict[str, Any]]: 以报告 ID 为键、报告数据为值的字典
        """
        if not self._path.exists():  # 正经注释：检查存储文件是否存在 / 大白话注释：文件在不在？
            return {}  # 正经注释：文件不存在返回空字典 / 大白话注释：不在就返回空的
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))  # 正经注释：读取并解析 JSON 文件 / 大白话注释：读文件内容，解析成 Python 字典
            if isinstance(data, dict):  # 正经注释：验证数据是否为字典类型 / 大白话注释：确认解析出来的是字典格式
                return data  # type: ignore[return-value]  # 正经注释：返回有效的字典数据 / 大白话注释：数据没问题，原样返回
        except Exception:  # 正经注释：捕获所有解析异常 / 大白话注释：出啥问题了（比如 JSON 格式不对）
            return {}  # 正经注释：解析失败返回空字典 / 大白话注释：有问题就返回空的
        return {}  # 正经注释：数据类型不正确时返回空字典 / 大白话注释：兜底返回空的

    async def _write_all_unlocked(self, data: Dict[str, Dict[str, Any]]) -> None:
        """
        将所有报告数据写入 JSON 文件（不加锁）。

        【正经注释】
        使用临时文件+原子替换的方式写入数据。先写入 .tmp 临时文件，
        再通过 replace 操作原子性地替换原文件，确保写入过程中即使发生故障
        也不会损坏原有数据。

        【大白话注释】
        把所有报告写到文件里去。为了安全，先写到临时文件，写好了再用"替换"的方式
        把临时文件变成正式文件。这样就算写到一半出问题了，原来的文件也不会坏。

        Args:
            data: 要写入的完整报告数据字典
        """
        await self._ensure_parent_dir()  # 正经注释：确保目标目录存在 / 大白话注释：先确保文件夹在
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")  # 正经注释：创建临时文件路径 / 大白话注释：生成一个临时文件名，比如 reports.json.tmp
        tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")  # 正经注释：将数据写入临时文件，保留非 ASCII 字符 / 大白话注释：把数据写到临时文件里，中文不会变乱码
        tmp_path.replace(self._path)  # 正经注释：原子替换，用临时文件覆盖原文件 / 大白话注释：用临时文件替换正式文件，一步到位

    async def list_reports(self, report_ids: List[str] | None = None) -> List[Dict[str, Any]]:
        """
        获取报告列表。

        【正经注释】
        在持锁状态下读取所有报告数据。如果指定了 report_ids，则仅返回对应 ID 的报告；
        否则返回所有报告。

        【大白话注释】
        查报告列表。你可以给一组 ID，只拿这几份报告；不给 ID 就全部都给你。
        操作的时候会先加锁，保证不会读到写到一半的数据。

        Args:
            report_ids: 可选的报告 ID 列表，用于过滤返回结果

        Returns:
            List[Dict[str, Any]]: 报告字典列表
        """
        async with self._lock:  # 正经注释：获取异步锁保证并发安全 / 大白话注释：先锁上，别人不许同时写
            data = await self._read_all_unlocked()  # 正经注释：读取所有数据 / 大白话注释：把所有报告读出来
            if report_ids is None:  # 正经注释：未指定 ID 则返回全部 / 大白话注释：没给 ID？那就全给你
                return list(data.values())  # 正经注释：返回所有报告值 / 大白话注释：返回所有报告
            return [data[report_id] for report_id in report_ids if report_id in data]  # 正经注释：仅返回存在的指定 ID 报告 / 大白话注释：只返回你要的那几份，找不到的就算了

    async def get_report(self, report_id: str) -> Dict[str, Any] | None:
        """
        获取指定 ID 的报告。

        【正经注释】
        在持锁状态下读取数据并返回指定 ID 的报告，不存在则返回 None。

        【大白话注释】
        根据报告 ID 找一份报告。找到了就给你，没找到就返回空。

        Args:
            report_id: 要获取的报告 ID

        Returns:
            Dict[str, Any] | None: 报告数据字典，不存在时为 None
        """
        async with self._lock:  # 正经注释：获取异步锁 / 大白话注释：先锁上
            data = await self._read_all_unlocked()  # 正经注释：读取所有数据 / 大白话注释：把所有报告读出来
            return data.get(report_id)  # 正经注释：返回指定 ID 的报告或 None / 大白话注释：找你要的那份，没有就返回 None

    async def upsert_report(self, report_id: str, report: Dict[str, Any]) -> None:
        """
        新增或更新报告。

        【正经注释】
        在持锁状态下读取所有数据，将指定 ID 的报告插入或替换，然后写回文件。
        如果报告 ID 已存在则更新，否则新增。

        【大白话注释】
        存一份报告。如果这个 ID 的报告已经有了，就覆盖更新；没有就新建一份。

        Args:
            report_id: 报告 ID
            report: 报告数据字典
        """
        async with self._lock:  # 正经注释：获取异步锁 / 大白话注释：先锁上
            data = await self._read_all_unlocked()  # 正经注释：读取当前所有数据 / 大白话注释：先看看现在有啥
            data[report_id] = report  # 正经注释：插入或更新指定报告 / 大白话注释：把报告放进去（有的话就覆盖）
            await self._write_all_unlocked(data)  # 正经注释：将更新后的数据写回文件 / 大白话注释：把所有报告写回文件

    async def delete_report(self, report_id: str) -> bool:
        """
        删除指定 ID 的报告。

        【正经注释】
        在持锁状态下删除指定 ID 的报告，并返回该报告是否存在的布尔值。
        如果报告存在则删除并返回 True，否则返回 False。

        【大白话注释】
        删一份报告。如果这报告存在就删了并返回 True，不存在就返回 False。

        Args:
            report_id: 要删除的报告 ID

        Returns:
            bool: 报告是否存在并被成功删除
        """
        async with self._lock:  # 正经注释：获取异步锁 / 大白话注释：先锁上
            data = await self._read_all_unlocked()  # 正经注释：读取当前所有数据 / 大白话注释：先看看现在有啥
            existed = report_id in data  # 正经注释：检查报告是否存在 / 大白话注释：看看这报告有没有
            if existed:  # 正经注释：报告存在则执行删除 / 大白话注释：有的话才删
                del data[report_id]  # 正经注释：从字典中删除报告 / 大白话注释：把这份报告删掉
                await self._write_all_unlocked(data)  # 正经注释：将更新后的数据写回文件 / 大白话注释：把删完之后的数据写回文件
            return existed  # 正经注释：返回报告是否曾存在 / 大白话注释：告诉调用者这报告原来在不在

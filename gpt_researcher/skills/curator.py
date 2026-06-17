"""来源精选技能模块（Source Curator Skill）
【正经注释】
本模块提供 SourceCurator 类，通过 LLM 评估研究来源的相关性、可信度和可靠性，
对来源进行排序和精选，选出最适合用于报告生成的来源。
【大白话注释】
这个文件就是"评审"——让 AI 看看搜到的资料哪些最靠谱、最相关，挑出最好的。
"""
import json															# 正经注释：JSON 解析库 / 大白话注释：解析 JSON
from typing import Dict, List, Optional								# 正经注释：类型提示 / 大白话注释：类型标记

from ..actions import stream_output									# 正经注释：WebSocket 输出流 / 大白话注释：给前端发消息
from ..config.config import Config									# 正经注释：配置类 / 大白话注释：读取设置
from ..utils.llm import create_chat_completion						# 正经注释：LLM 调用接口 / 大白话注释：跟 AI 对话的函数


class SourceCurator:
    """来源精选器——评估和排序研究来源

    【正经注释】
    使用 LLM 评估研究来源的质量，从相关性、可信度和可靠性三个维度打分，
    选出最适合报告生成的高质量来源。
    【大白话注释】
    这个类就是"评审"——让 AI 看看搜到的资料，挑出最靠谱的：
    - 这条来源跟问题相关吗？
    - 这个网站可信吗？
    - 内容可靠吗？

    Attributes:
        researcher: 父级 GPTResearcher 实例（大白话：老板）
    """

    def __init__(self, researcher):
        """初始化来源精选器
        【正经注释】绑定父级 researcher 实例。
        【大白话注释】记住"老板"是谁。
        Args:
            researcher: GPTResearcher 实例（大白话：老板）
        """
        self.researcher = researcher								# 正经注释：持有对父级实例的引用 / 大白话注释：记住老板

    async def curate_sources(										# 正经注释：精选研究来源——核心方法 / 大白话注释：让评审挑最好的资料
        self,
        source_data: List,
        max_results: int = 10,
    ) -> List:
        """评估和精选研究来源
        【正经注释】将所有来源数据发送给 LLM，由 LLM 从相关性、可信度和可靠性
        三个维度评估并排序，返回精选后的来源列表。失败时返回原始数据。
        【大白话注释】把搜到的资料都交给 AI 评审，让 AI 挑出最靠谱的。
        如果 AI 出错了，就用原始数据（不挑了，全要）。
        Args:
            source_data: 来源数据列表（大白话：搜到的所有资料）
            max_results: 最多保留几条（大白话：最多要几条好资料）
        Returns:
            List: 精选后的来源列表（大白话：挑出来的好资料）
        """
        print(f"\n\nCurating {len(source_data)} sources: {source_data}")	# 正经注释：打印来源数量用于调试 / 大白话注释：日志——正在评审几条资料
        if self.researcher.verbose:									# 正经注释：详细模式下推送进度 / 大白话注释：告诉用户"评审开始"
            await stream_output(
                "logs",
                "research_plan",
                f"⚖️ Evaluating and curating sources by credibility and relevance...",
                self.researcher.websocket,
            )

        response = ""												# 正经注释：初始化 LLM 响应变量 / 大白话注释：准备装 AI 的回答
        try:
            response = await create_chat_completion(					# 正经注释：调用 LLM 评估来源 / 大白话注释：让 AI 评审
                model=self.researcher.cfg.smart_llm_model,			# 正经注释：使用智能模型 / 大白话注释：用聪明但不太贵的 AI
                messages=[
                    {"role": "system", "content": f"{self.researcher.role}"},	# 正经注释：设置研究员角色 / 大白话注释：告诉 AI 用什么角色来评审
                    {"role": "user", "content": self.researcher.prompt_family.curate_sources(	# 正经注释：来源精选提示词 / 大白话注释："帮我挑最好的资料"
                        self.researcher.query, source_data, max_results)},
                ],
                temperature=0.2,										# 正经注释：低温度保证评估的稳定性和一致性 / 大白话注释：让 AI 评判尽量稳定
                max_tokens=8000,										# 正经注释：足够的 token 限制 / 大白话注释：给 AI 足够空间写评估结果
                llm_provider=self.researcher.cfg.smart_llm_provider,
                llm_kwargs=self.researcher.cfg.llm_kwargs,
                cost_callback=self.researcher.add_costs,
            )

            curated_sources = json.loads(response)					# 正经注释：解析 LLM 返回的精选结果 JSON / 大白话注释：把 AI 的回答变成列表
            print(f"\n\nFinal Curated sources {len(source_data)} sources: {curated_sources}")	# 正经注释：打印精选结果用于调试 / 大白话注释：日志——挑出了几条

            if self.researcher.verbose:								# 正经注释：推送精选完成信息 / 大白话注释：告诉用户"挑好了"
                await stream_output(
                    "logs",
                    "research_plan",
                    f"🏅 Verified and ranked top {len(curated_sources)} most reliable sources",
                    self.researcher.websocket,
                )

            return curated_sources									# 正经注释：返回精选后的来源 / 大白话注释：把挑好的交出去

        except Exception as e:										# 正经注释：LLM 调用或 JSON 解析失败 / 大白话注释：AI 出错了或者返回格式不对
            print(f"Error in curate_sources from LLM response: {response}")	# 正经注释：打印导致错误的原始响应 / 大白话注释：日志——出错了，AI 回答了什么
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "research_plan",
                    f"🚫 Source verification failed: {str(e)}",
                    self.researcher.websocket,
                )
            return source_data										# 正经注释：失败时返回原始未筛选的数据 / 大白话注释：挑不出来就全要

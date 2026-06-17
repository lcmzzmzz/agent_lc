"""报告生成器技能模块（Report Generator Skill）
【正经注释】
本模块提供 ReportGenerator 类，负责报告的完整生成流程：
- write_report: 生成完整报告（核心方法）
- write_report_conclusion: 生成结论
- write_introduction: 生成引言
- get_subtopics: 获取子课题
- get_draft_section_titles: 生成章节标题
【大白话注释】
这个文件就是"写手"——负责写报告的各个部分：开头、正文、结尾、提纲。
"""
import json															# 正经注释：JSON 解析库 / 大白话注释：解析 JSON
from typing import Dict, Optional									# 正经注释：类型提示 / 大白话注释：类型标记

from ..actions import (												# 正经注释：导入报告生成相关的 actions 函数 / 大白话注释：导入写报告要用的工具
    generate_draft_section_titles,									# 正经注释：生成章节标题 / 大白话注释：列提纲
    generate_report,												# 正经注释：生成报告 / 大白话注释：写报告
    stream_output,													# 正经注释：实时输出 / 大白话注释：给前端发消息
    write_conclusion,												# 正经注释：写结论 / 大白话注释：写结尾
    write_report_introduction,										# 正经注释：写引言 / 大白话注释：写开头
)
from ..utils.llm import construct_subtopics							# 正经注释：子课题构建函数 / 大白话注释：拆分大问题的函数


class ReportGenerator:
    """报告生成器——负责研究报告的完整生成流程

    【正经注释】
    管理报告生成的全部流程，包括引言、正文、结论、子课题拆分和章节标题生成。
    持有对 researcher 实例的引用以访问配置、上下文等共享状态。
    【大白话注释】
    这个类就是"写手"——你告诉他写什么，他就写好：
    - 写开头、写正文、写结尾
    - 把大问题拆成小问题（子课题）
    - 给每个小问题列提纲

    Attributes:
        researcher: 父级 GPTResearcher 实例（大白话：老板）
        research_params: 报告生成参数字典（大白话：写报告需要的各种设置）
    """

    def __init__(self, researcher):
        """初始化报告生成器
        【正经注释】绑定 researcher 实例并预构建报告参数字典。
        【大白话注释】记住"老板"是谁，把写报告需要的参数都准备好。
        Args:
            researcher: GPTResearcher 实例（大白话：老板）
        """
        self.researcher = researcher								# 正经注释：持有对父级实例的引用 / 大白话注释：记住老板
        self.research_params = {									# 正经注释：预构建报告参数字典，避免每次调用时重复构建 / 大白话注释：把写报告需要的参数都打包好
            "query": self.researcher.query,							# 正经注释：研究查询 / 大白话注释：研究的问题
            "agent_role_prompt": self.researcher.cfg.agent_role or self.researcher.role,	# 正经注释：代理角色提示词 / 大白话注释：用什么专家的口吻
            "report_type": self.researcher.report_type,				# 正经注释：报告类型 / 大白话注释：什么格式的报告
            "report_source": self.researcher.report_source,			# 正经注释：信息来源 / 大白话注释：从哪找的资料
            "tone": self.researcher.tone,							# 正经注释：语气 / 大白话注释：用什么语气
            "websocket": self.researcher.websocket,					# 正经注释：WebSocket 连接 / 大白话注释：实时推送通道
            "cfg": self.researcher.cfg,								# 正经注释：配置对象 / 大白话注释：各种设置
            "headers": self.researcher.headers,						# 正经注释：请求头 / 大白话注释：额外的请求信息
        }

    async def write_report(self, existing_headers: list = [], relevant_written_contents: list = [], ext_context=None, custom_prompt="", available_images: list = None) -> str:
        """生成完整研究报告
        【正经注释】
        组装所有报告参数（查询、上下文、角色、图片等），调用 generate_report 生成报告。
        支持子课题报告（需要主话题和已有标题）和标准报告两种模式。
        写报告前会先推送已选图片给前端。
        【大白话注释】
        这是"写手"的核心方法——把所有素材和参数打包好，让 AI 写一份完整报告：
        1. 先把选好的图片发给前端看看
        2. 把素材、设置、要求都准备好
        3. 让 AI 写报告
        Args:
            existing_headers: 已有标题（大白话：写过的标题）
            relevant_written_contents: 已写内容（大白话：写过的段落）
            ext_context: 外部上下文（大白话：外部给的素材）
            custom_prompt: 自定义提示词（大白话：给写手的特别指示）
            available_images: 预生成图片（大白话：已经画好的配图）
        Returns:
            str: 生成的报告（大白话：写好的报告）
        """
        available_images = available_images or []					# 正经注释：确保 images 不为 None / 大白话注释：没给图片就设为空

        # send the selected images prior to writing report		# 正经注释：写报告前先把已选图片推送给前端 / 大白话注释：先让前端看看选了哪些图
        research_images = self.researcher.get_research_images()		# 正经注释：获取已选的研究图片 / 大白话注释：拿到选好的图片
        if research_images:											# 正经注释：有图片时推送 / 大白话注释：有图就发
            await stream_output(
                "images",
                "selected_images",
                json.dumps(research_images),						# 正经注释：序列化为 JSON / 大白话注释：变成 JSON 字符串
                self.researcher.websocket,
                True,
                research_images
            )

        context = ext_context or self.researcher.context			# 正经注释：优先使用外部上下文，否则用内部素材 / 大白话注释：有外部素材就用外部的，没有就用自己搜的

        # Log image availability									# 正经注释：记录图片可用性 / 大白话注释：告诉用户有几张配图可用
        if available_images and self.researcher.verbose:
            await stream_output(
                "logs",
                "images_available",
                f"🖼️ {len(available_images)} pre-generated images available for embedding",
                self.researcher.websocket,
            )

        if self.researcher.verbose:									# 正经注释：推送写报告进度 / 大白话注释：告诉用户"开始写了"
            await stream_output(
                "logs",
                "writing_report",
                f"✍️ Writing report for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        report_params = self.research_params.copy()					# 正经注释：拷贝预构建的参数字典 / 大白话注释：把之前准备好的参数复制一份
        if not report_params["agent_role_prompt"]:					# 正经注释：确保角色提示词不为空 / 大白话注释：没设角色就用配置里的
            report_params["agent_role_prompt"] = self.researcher.cfg.agent_role or self.researcher.role
        report_params["context"] = context							# 正经注释：设置上下文 / 大白话注释：素材
        report_params["custom_prompt"] = custom_prompt				# 正经注释：设置自定义提示词 / 大白话注释：特别指示
        report_params["available_images"] = available_images  # Pass pre-generated images	# 正经注释：传入预生成图片 / 大白话注释：配图

        if self.researcher.report_type == "subtopic_report":		# 正经注释：子课题报告需要额外参数 / 大白话注释：子课题报告——要传主话题和已有内容
            report_params.update({
                "main_topic": self.researcher.parent_query,			# 正经注释：主话题 / 大白话注释：大问题
                "existing_headers": existing_headers,				# 正经注释：已有标题 / 大白话注释：写过的标题
                "relevant_written_contents": relevant_written_contents,	# 正经注释：已写内容 / 大白话注释：写过的段落
                "cost_callback": self.researcher.add_costs,			# 正经注释：费用回调 / 大白话注释：算钱的函数
            })
        else:														# 正经注释：标准报告只需费用回调 / 大白话注释：普通报告
            report_params["cost_callback"] = self.researcher.add_costs

        report = await generate_report(**report_params, **self.researcher.kwargs)	# 正经注释：调用报告生成函数 / 大白话注释：让 AI 写报告！

        if self.researcher.verbose:									# 正经注释：推送报告完成信息 / 大白话注释：告诉用户"写好了"
            await stream_output(
                "logs",
                "report_written",
                f"📝 Report written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return report												# 正经注释：返回生成的报告 / 大白话注释：把写好的报告交出去

    async def write_report_conclusion(self, report_content: str) -> str:
        """生成报告结论
        【正经注释】基于报告正文调用 write_conclusion 生成总结性结论段落。
        【大白话注释】让 AI 看了报告后写一个"结尾"——归纳核心结论。
        Args:
            report_content (str): 报告正文（大白话：已经写好的报告）
        Returns:
            str: 生成的结论（大白话：写好的结尾）
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_conclusion",
                f"✍️ Writing conclusion for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        conclusion = await write_conclusion(						# 正经注释：调用结论生成函数 / 大白话注释：让 AI 写结尾
            query=self.researcher.query,
            context=report_content,									# 正经注释：传入报告正文作为上下文 / 大白话注释：让 AI 看了报告再写
            config=self.researcher.cfg,
            agent_role_prompt=self.researcher.cfg.agent_role or self.researcher.role,
            cost_callback=self.researcher.add_costs,
            websocket=self.researcher.websocket,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "conclusion_written",
                f"📝 Conclusion written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return conclusion											# 正经注释：返回结论 / 大白话注释：交出去

    async def write_introduction(self):
        """生成报告引言
        【正经注释】基于研究查询和上下文调用 write_report_introduction 生成引言。
        【大白话注释】让 AI 写报告的"开头"——介绍研究什么、为什么研究。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "writing_introduction",
                f"✍️ Writing introduction for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        introduction = await write_report_introduction(				# 正经注释：调用引言生成函数 / 大白话注释：让 AI 写开头
            query=self.researcher.query,
            context=self.researcher.context,						# 正经注释：传入研究上下文 / 大白话注释：把搜到的素材给 AI 看
            agent_role_prompt=self.researcher.cfg.agent_role or self.researcher.role,
            config=self.researcher.cfg,
            websocket=self.researcher.websocket,
            cost_callback=self.researcher.add_costs,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "introduction_written",
                f"📝 Introduction written for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return introduction											# 正经注释：返回引言 / 大白话注释：交出去

    async def get_subtopics(self):
        """获取研究子课题
        【正经注释】调用 construct_subtopics 将复杂查询分解为可独立研究的子主题。
        【大白话注释】把一个大问题拆成几个小问题——比如"AI 发展现状"拆成"大模型"、"自动驾驶"等。
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "generating_subtopics",
                f"🌳 Generating subtopics for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        subtopics = await construct_subtopics(						# 正经注释：调用子课题构建函数 / 大白话注释：让 AI 拆问题
            task=self.researcher.query,
            data=self.researcher.context,
            config=self.researcher.cfg,
            subtopics=self.researcher.subtopics,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "subtopics_generated",
                f"📊 Subtopics generated for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return subtopics											# 正经注释：返回子课题列表 / 大白话注释：交出去

    async def get_draft_section_titles(self, current_subtopic: str):
        """生成草稿章节标题
        【正经注释】为指定子课题生成报告的章节标题列表，用于 DetailedReport 的分章节写作。
        【大白话注释】给某个小问题列一个"写作提纲"——比如要写哪几个小节。
        Args:
            current_subtopic: 当前子课题（大白话：正在写的小话题）
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "generating_draft_sections",
                f"📑 Generating draft section titles for '{self.researcher.query}'...",
                self.researcher.websocket,
            )

        draft_section_titles = await generate_draft_section_titles(	# 正经注释：调用章节标题生成函数 / 大白话注释：让 AI 列提纲
            query=self.researcher.query,
            current_subtopic=current_subtopic,
            context=self.researcher.context,
            role=self.researcher.cfg.agent_role or self.researcher.role,
            websocket=self.researcher.websocket,
            config=self.researcher.cfg,
            cost_callback=self.researcher.add_costs,
            prompt_family=self.researcher.prompt_family,
            **self.researcher.kwargs
        )

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "draft_sections_generated",
                f"🗂️ Draft section titles generated for '{self.researcher.query}'",
                self.researcher.websocket,
            )

        return draft_section_titles								# 正经注释：返回章节标题列表 / 大白话注释：交出去

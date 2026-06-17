"""图片生成器技能模块（Image Generator Skill）
【正经注释】
本模块提供 ImageGenerator 类，负责为研究报告生成与内容相关的配图。
支持两种工作模式：
1. 预生成模式（plan_and_generate_images）：在报告生成前，分析上下文提前生成图片
2. 后处理模式（generate_images_for_report）：分析已完成的报告，为合适的章节补充图片
3. 占位符模式（process_image_placeholders）：处理报告中的 [IMAGE: ...] 占位符
【大白话注释】
这个文件就是"画师"——负责给报告配图：
- 看看素材，想想哪些地方需要配图
- 让 AI 画出合适的图
- 把画好的图插到报告里合适的位置
"""
import asyncio														# 正经注释：异步 I/O 库，用于并行生成多张图片 / 大白话注释：同时画几张图
import json															# 正经注释：JSON 解析库 / 大白话注释：解析 JSON
import logging														# 正经注释：日志库 / 大白话注释：记日志
import re															# 正经注释：正则表达式库 / 大白话注释：用模式匹配处理文字
from typing import Any, Dict, List, Optional, Tuple				# 正经注释：类型提示 / 大白话注释：类型标记

from ..actions.utils import stream_output								# 正经注释：WebSocket 输出流 / 大白话注释：给前端发消息
from ..llm_provider.image import ImageGeneratorProvider, ModelsLabImageGeneratorProvider	# 正经注释：图片生成提供者 / 大白话注释：两种画图工具
from ..utils.llm import create_chat_completion						# 正经注释：LLM 调用接口 / 大白话注释：跟 AI 对话的函数

logger = logging.getLogger(__name__)									# 正经注释：创建日志记录器 / 大白话注释：准备记事本


class ImageGenerator:
    """图片生成器——为研究报告生成与内容相关的配图

    【正经注释】
    分析报告内容，识别适合配图的章节，使用 AI 图片生成模型生成配图，
    并将图片嵌入到报告的合适位置。支持 Google Imagen 和 ModelsLab 两种生成器。
    【大白话注释】
    这个类就是"画师"：
    1. 看看报告哪里需要配图
    2. 让 AI 画出合适的图
    3. 把图插到报告里

    Attributes:
        researcher: 父级 GPTResearcher 实例（大白话：老板）
        image_provider: 图片生成提供者（大白话：用哪个画图工具）
        max_images: 每次最多生成几张图（大白话：最多画几张）
    """

    def __init__(self, researcher):
        """初始化图片生成器
        【正经注释】绑定 researcher 实例，从配置中读取图片生成设置并初始化提供者。
        【大白话注释】记住老板，看看配了什么画图工具，准备好画板。
        Args:
            researcher: GPTResearcher 实例（大白话：老板）
        """
        self.researcher = researcher								# 正经注释：持有对父级实例的引用 / 大白话注释：记住老板
        self.cfg = researcher.cfg									# 正经注释：缓存配置对象 / 大白话注释：快捷访问配置
        self.image_provider = None									# 正经注释：图片生成提供者，初始为 None / 大白话注释：还没选好画图工具
        self.max_images = getattr(self.cfg, 'image_generation_max_images', 3)	# 正经注释：从配置读取最大图片数，默认 3 / 大白话注释：最多画 3 张
        self.generated_images: List[Dict[str, Any]] = []				# 正经注释：已生成的图片列表 / 大白话注释：画好的图清单

        # Initialize image provider if configured					# 正经注释：如果配置了图片生成，则初始化提供者 / 大白话注释：配了画图工具就去准备
        self._init_provider()

    def _init_provider(self):
        """初始化图片生成提供者
        【正经注释】从配置读取启用状态和提供者名称，创建对应的图片生成器实例。
        支持 Google Imagen 和 ModelsLab 两种提供者。
        【大白话注释】看看用什么画图工具，准备好了就设为可用。
        """
        try:
            enabled = getattr(self.cfg, 'IMAGE_GENERATION_ENABLED', False)	# 正经注释：检查是否启用了图片生成 / 大白话注释：看看有没有开画图功能
            if not enabled:
                return
            provider_name = getattr(self.cfg, 'IMAGE_GENERATION_PROVIDER', 'google')	# 正经注释：获取提供者名称，默认 Google / 大白话注释：用哪个画图工具
            model = getattr(self.cfg, 'IMAGE_GENERATION_MODEL', None)	# 正经注释：获取模型名称 / 大白话注释：用哪个版本的模型
            if provider_name == 'modelslab':							# 正经注释：ModelsLab 提供者 / 大白话注释：ModelsLab 画图工具
                provider = ModelsLabImageGeneratorProvider(model_id=model)
            else:														# 正经注释：默认使用 Google Imagen / 大白话注释：Google 画图工具
                provider = ImageGeneratorProvider(model_name=model)
            if provider.is_available():								# 正经注释：检查提供者是否可用（API Key 是否配置） / 大白话注释：看看钥匙有没有
                self.image_provider = provider						# 正经注释：设置可用的提供者 / 大白话注释：工具准备好了
                logger.info(f"Image generation provider initialized: {provider_name}")
            else:
                logger.warning(f"Image generation provider '{provider_name}' not available (missing API key?)")
        except Exception as e:										# 正经注释：初始化失败时设为 None / 大白话注释：出错了就不画
            logger.error(f"Failed to initialize image provider: {e}")
            self.image_provider = None

    def is_enabled(self) -> bool:
        """检查图片生成是否启用且可用
        【正经注释】返回 True 当且仅当提供者已初始化且 API Key 有效。
        【大白话注释】看看画师能不能用——工具准备好了吗？钥匙有了吗？
        Returns:
            bool: 是否可用（大白话：能不能画图）
        """
        return self.image_provider is not None and self.image_provider.is_available()

    async def plan_and_generate_images(								# 正经注释：预生成模式——在报告生成前提前画好图 / 大白话注释：先画图再写报告
        self,
        context: str,
        query: str,
        research_id: str = "",
    ) -> List[Dict[str, Any]]:
        """分析上下文并预生成配图
        【正经注释】
        两阶段流程：
        1. 用 LLM 分析研究上下文，识别 2-3 个适合配图的概念
        2. 并行生成所有图片
        在报告写作之前调用，图片生成后可嵌入报告。
        【大白话注释】
        先看看素材，想想哪里需要配图，然后同时画好几张图：
        1. 让 AI 看素材，挑出适合配图的地方
        2. 同时让画师画出这些图
        Args:
            context: 研究上下文（大白话：搜到的素材）
            query: 研究查询（大白话：研究的问题）
            research_id: 研究 ID（大白话：任务编号）
        Returns:
            List[Dict]: 生成的图片信息列表（大白话：画好的图）
        """
        if not self.is_enabled():									# 正经注释：未启用则跳过 / 大白话注释：画师不能用就算了
            logger.info("Image generation is not enabled, skipping pre-generation")
            return []

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "image_planning",
                "🎨 Analyzing research context for visualization opportunities...",
                self.researcher.websocket,
            )

        # Step 1: Use LLM to identify best visualization opportunities	# 正经注释：阶段1 - 用 LLM 识别适合配图的概念 / 大白话注释：让 AI 想想哪里需要图
        image_concepts = await self._plan_image_concepts(context, query)

        if not image_concepts:										# 正经注释：没有适合配图的概念则跳过 / 大白话注释：AI 觉得不需要配图
            logger.info("No suitable visualization opportunities identified")
            return []

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "image_concepts_identified",
                f"🖼️ Identified {len(image_concepts)} visualization concepts, generating images...",
                self.researcher.websocket,
            )

        # Step 2: Generate all images in parallel					# 正经注释：阶段2 - 并行生成所有图片 / 大白话注释：同时画所有图
        image_style = getattr(self.cfg, 'image_generation_style', 'dark')	# 正经注释：获取图片风格，默认暗色 / 大白话注释：用深色风格

        async def generate_single_image(concept: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
            """生成单张图片（内部函数）
            【正经注释】根据概念描述调用图片提供者生成一张图片。
            【大白话注释】根据 AI 的建议画一张图。
            """
            try:
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "image_generating",
                        f"🖼️ Generating image {index + 1}/{len(image_concepts)}: {concept['title'][:50]}...",
                        self.researcher.websocket,
                    )

                images = await self.image_provider.generate_image(	# 正经注释：调用图片生成接口 / 大白话注释：画！
                    prompt=concept['prompt'],						# 正经注释：图片描述提示词 / 大白话注释：画什么
                    context=concept.get('context', ''),				# 正经注释：上下文信息 / 大白话注释：背景信息
                    research_id=research_id,
                    num_images=1,									# 正经注释：每次只生成一张 / 大白话注释：画一张
                    style=image_style,								# 正经注释：图片风格 / 大白话注释：什么风格
                )

                if images:
                    image_info = images[0]
                    image_info['title'] = concept['title']			# 正经注释：添加标题 / 大白话注释：给图起个名
                    image_info['section_hint'] = concept.get('section_hint', '')	# 正经注释：添加章节提示 / 大白话注释：这张图放哪个章节
                    return image_info

            except Exception as e:
                logger.error(f"Failed to generate image for '{concept['title']}': {e}")
            return None

        # Generate all images in parallel							# 正经注释：并行生成所有图片 / 大白话注释：同时画
        tasks = [generate_single_image(concept, i) for i, concept in enumerate(image_concepts)]
        results = await asyncio.gather(*tasks)						# 正经注释：等待所有图片生成完成 / 大白话注释：等所有图都画好

        # Filter out failed generations								# 正经注释：过滤掉生成失败的图片 / 大白话注释：把画失败的去掉
        generated_images = [img for img in results if img is not None]
        self.generated_images = generated_images					# 正经注释：保存已生成的图片 / 大白话注释：存起来

        if self.researcher.verbose:
            if generated_images:
                await stream_output(
                    "logs",
                    "images_ready",
                    f"✅ {len(generated_images)} images ready for report embedding",
                    self.researcher.websocket,
                )
            else:
                await stream_output(
                    "logs",
                    "images_failed",
                    "⚠️ No images could be generated",
                    self.researcher.websocket,
                )

        return generated_images									# 正经注释：返回生成的图片列表 / 大白话注释：把画好的图交出去

    # 返回多个image_info = {
    #     "path": ...,  # ┐
    #     "url": ...,  # │
    #     "absolute_url": ...,  # │ provider 已经给好的 5 个键
    #     "prompt": ...,  # │
    #     "alt_text": ...,  # ┘
    #     "title": ...,  # ┐ skills 层追加的 2 个键
    #     "section_hint": ...,  # ┘
    # }  # = 5 + 2 = 7 个字段

    async def _plan_image_concepts(								# 正经注释：用 LLM 分析上下文，识别适合配图的概念 / 大白话注释：让 AI 想想哪里需要配图
        self,
        context: str,
        query: str,
    ) -> List[Dict[str, Any]]:
        """用 LLM 识别最佳配图机会
        【正经注释】将截断的研究上下文发送给 LLM，返回 2-3 个图片概念（含标题、提示词、章节提示）。
        【大白话注释】让 AI 看看素材，想想哪几个地方配上图会更好看。
        Args:
            context: 研究上下文（大白话：素材）
            query: 研究查询（大白话：问题）
        Returns:
            List[Dict]: 图片概念列表（大白话：AI 建议配什么图）
        """
        # Truncate context if too long								# 正经注释：截断过长的上下文避免超出 token 限制 / 大白话注释：素材太长就截短一点
        max_context_length = 6000
        truncated_context = context[:max_context_length] if len(context) > max_context_length else context

        planning_prompt = f"""Analyze this research context and identify 2-3 concepts that would significantly benefit from professional diagram/infographic illustrations.

RESEARCH QUERY: {query}

RESEARCH CONTEXT:
{truncated_context}

For each visualization opportunity, provide:
1. title: A short descriptive title (e.g., "System Architecture", "Comparison Chart")
2. prompt: A detailed image generation prompt describing exactly what to visualize, including layout and key elements (minimum 30 words)
3. section_hint: Which section of the report this image relates to

Focus on:
- Architecture/system diagrams
- Process flows and workflows
- Comparison charts
- Data visualizations
- Conceptual illustrations

IMPORTANT: Return ONLY a valid JSON array. No markdown, no explanation.

Example output:
[
  {{
    "title": "System Architecture Overview",
    "prompt": "A layered architecture diagram showing the frontend application on top, connecting to an API gateway in the middle, which routes to microservices at the bottom. Use clean boxes with connecting arrows, modern tech aesthetic.",
    "section_hint": "Architecture"
  }}
]

Return 2-3 visualization concepts as a JSON array:"""				# 正经注释：构建图片规划提示词 / 大白话注释：告诉 AI "帮我看看哪里需要配图"

        try:
            response = await create_chat_completion(				# 正经注释：调用快速模型进行图片规划 / 大白话注释：让快 AI 想想
                model=self.cfg.fast_llm_model,						# 正经注释：使用快速模型（非报告生成模型） / 大白话注释：用便宜的快 AI
                messages=[
                    {"role": "system", "content": "You are a visualization expert. Return only valid JSON arrays."},	# 正经注释：系统提示词 / 大白话注释：告诉 AI "你是配图专家"
                    {"role": "user", "content": planning_prompt}
                ],
                temperature=0.4,									# 正经注释：适中温度 / 大白话注释：允许一些创造性
                llm_provider=self.cfg.fast_llm_provider,
                max_tokens=1000,
                llm_kwargs=self.cfg.llm_kwargs,
                cost_callback=self.researcher.add_costs,
            )

            # Parse JSON response									# 正经注释：解析 JSON 响应 / 大白话注释：把 AI 的回答变成列表
            response = response.strip()
            # Remove markdown code blocks if present				# 正经注释：去除 Markdown 代码块标记 / 大白话注释：AI 可能把 JSON 包在代码块里
            if response.startswith("```"):
                response = re.sub(r'^```(?:json)?\n?', '', response)
                response = re.sub(r'\n?```$', '', response)

            concepts = json.loads(response)						# 正经注释：解析 JSON / 大白话注释：变成 Python 列表

            # Validate and limit to max_images						# 正经注释：验证并限制数量 / 大白话注释：检查格式对不对，太多了就截断
            valid_concepts = []
            for concept in concepts[:self.max_images]:
                if isinstance(concept, dict) and 'title' in concept and 'prompt' in concept:
                    valid_concepts.append(concept)

            logger.info(f"Planned {len(valid_concepts)} image concepts")
            return valid_concepts

        except json.JSONDecodeError as e:							# 正经注释：JSON 解析失败 / 大白话注释：AI 返回的格式不对
            logger.error(f"Failed to parse image planning response: {e}")
            return []
        except Exception as e:										# 正经注释：其他异常 / 大白话注释：出错了
            logger.error(f"Error during image planning: {e}")
            return []

    async def analyze_report_for_images(							# 正经注释：分析已完成的报告，找出适合配图的章节 / 大白话注释：报告写好了，看看哪里需要加图
        self,
        report: str,
        query: str,
    ) -> List[Dict[str, Any]]:
        """分析报告，识别适合配图的章节
        【正经注释】提取报告章节后发送给 LLM 分析，返回适合配图的章节信息。
        【大白话注释】把报告切成一段一段的，让 AI 看看哪些段落配上图更好。
        Args:
            report: Markdown 报告文本（大白话：写好的报告）
            query: 研究查询（大白话：研究的问题）
        Returns:
            List[Dict]: 配图建议列表（大白话：AI 建议在哪里加什么图）
        """
        if not self.is_enabled():
            return []

        # Extract sections from the report							# 正经注释：提取报告章节 / 大白话注释：把报告切成段
        sections = self._extract_sections(report)

        if not sections:											# 正经注释：无章节则跳过 / 大白话注释：报告没分段就没法分析
            logger.warning("No sections found in report for image analysis")
            return []

        # Use LLM to identify best sections for images				# 正经注释：用 LLM 识别最佳配图章节 / 大白话注释：让 AI 挑哪里加图
        try:
            analysis_prompt = self._build_analysis_prompt(query, sections)

            response = await create_chat_completion(
                model=self.cfg.fast_llm_model,
                messages=[
                    {"role": "system", "content": "You are an expert at identifying content that would benefit from visual illustrations."},
                    {"role": "user", "content": analysis_prompt},
                ],
                temperature=0.3,
                llm_provider=self.cfg.fast_llm_provider,
                stream=False,
                websocket=None,
                max_tokens=1500,
                llm_kwargs=self.cfg.llm_kwargs,
            )

            # Parse the response									# 正经注释：解析 AI 的配图建议 / 大白话注释：把 AI 的建议整理一下
            image_suggestions = self._parse_analysis_response(response, sections)
            return image_suggestions[:self.max_images]				# 正经注释：限制最大数量 / 大白话注释：太多了就截断

        except Exception as e:
            logger.error(f"Error analyzing report for images: {e}")
            return []

    def _extract_sections(self, report: str) -> List[Dict[str, Any]]:
        """从 Markdown 报告中提取章节
        【正经注释】按 ## 和 ### 标题拆分报告为章节列表，记录每个章节的标题、内容和行号范围。
        【大白话注释】把报告按标题切成一段一段的。
        Args:
            report: Markdown 报告（大白话：报告内容）
        Returns:
            List[Dict]: 章节列表（大白话：切好的段落）
        """
        sections = []												# 正经注释：初始化章节列表 / 大白话注释：准备装切好的段落
        lines = report.split('\n')									# 正经注释：按行分割 / 大白话注释：一行一行看
        current_section = None										# 正经注释：当前正在收集的章节标题 / 大白话注释：当前在哪个标题下面
        current_content = []										# 正经注释：当前章节的内容行 / 大白话注释：当前章节的内容
        section_start = 0											# 正经注释：当前章节起始行号 / 大白话注释：从第几行开始

        for i, line in enumerate(lines):							# 正经注释：遍历每一行 / 大白话注释：一行一行看
            # Check for headers (## or ###)						# 正经注释：检测二级或三级标题 / 大白话注释：看看是不是标题行
            header_match = re.match(r'^(#{2,3})\s+(.+)$', line)

            if header_match:										# 正经注释：找到新标题时保存上一个章节 / 大白话注释：遇到新标题就把前面的内容存起来
                # Save previous section
                if current_section:
                    sections.append({
                        "header": current_section,					# 正经注释：章节标题 / 大白话注释：标题
                        "content": '\n'.join(current_content).strip(),	# 正经注释：章节内容 / 大白话注释：内容
                        "start_line": section_start,				# 正经注释：起始行号 / 大白话注释：从第几行
                        "end_line": i - 1,							# 正经注释：结束行号 / 大白话注释：到第几行
                    })

                # Start new section								# 正经注释：开始新章节 / 大白话注释：开始收集新段落
                current_section = header_match.group(2)				# 正经注释：提取标题文本 / 大白话注释：标题内容
                current_content = []
                section_start = i
            elif current_section:
                current_content.append(line)						# 正经注释：添加到当前章节内容 / 大白话注释：这行属于当前标题下面

        # Don't forget the last section							# 正经注释：保存最后一个章节 / 大白话注释：别忘了最后一段
        if current_section:
            sections.append({
                "header": current_section,
                "content": '\n'.join(current_content).strip(),
                "start_line": section_start,
                "end_line": len(lines) - 1,
            })

        return sections											# 正经注释：返回章节列表 / 大白话注释：交出去

    def _build_analysis_prompt(									# 正经注释：构建配图分析提示词 / 大白话注释：告诉 AI "帮我看看哪里需要图"
        self,
        query: str,
        sections: List[Dict[str, Any]],
    ) -> str:
        """构建 LLM 配图分析提示词
        【正经注释】将报告章节格式化后构建分析提示词，要求 LLM 返回 JSON 格式的配图建议。
        【大白话注释】把报告的各个段落整理好，让 AI 挑出最适合配图的。
        Args:
            query: 研究查询（大白话：研究的问题）
            sections: 章节列表（大白话：报告的各个段落）
        Returns:
            str: 分析提示词（大白话：给 AI 的提问）
        """
        sections_text = "\n\n".join([								# 正经注释：格式化章节文本，每个章节截取前 500 字符 / 大白话注释：把每段内容截短一点列出来
            f"### Section {i+1}: {s['header']}\n{s['content'][:500]}..."
            for i, s in enumerate(sections)
        ])

        return f"""Analyze the following research report sections and identify which {self.max_images} sections would benefit MOST from a visual illustration or diagram.

RESEARCH TOPIC: {query}

REPORT SECTIONS:
{sections_text}

For each recommended section, provide:
1. The section number (1-indexed)
2. A specific, detailed image prompt that would create an informative illustration
3. A brief explanation of why this section benefits from visualization

IMPORTANT:
- Choose sections where visual representation would genuinely aid understanding
- Focus on concepts, processes, comparisons, or data that are inherently visual
- Avoid sections that are purely textual analysis or conclusions
- The image prompt should be specific enough to generate a relevant, professional illustration
- Do NOT suggest images for introduction or conclusion sections

Respond in JSON format:
{{
    "suggestions": [
        {{
            "section_number": 1,
            "section_header": "Section Title",
            "image_prompt": "Detailed prompt for generating an informative illustration...",
            "reason": "Why this section benefits from visualization"
        }}
    ]
}}

Return ONLY the JSON, no additional text."""						# 正经注释：要求 LLM 返回 JSON 格式的配图建议 / 大白话注释：让 AI 用 JSON 回答

    def _parse_analysis_response(									# 正经注释：解析 LLM 的配图分析响应 / 大白话注释：把 AI 的建议整理成列表
        self,
        response: str,
        sections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """解析配图分析响应
        【正经注释】从 LLM 响应中提取 JSON，将建议与原始章节数据关联。
        【大白话注释】把 AI 的回答变成能用的配图建议。
        Args:
            response: LLM 响应文本（大白话：AI 的回答）
            sections: 原始章节列表（大白话：报告的各个段落）
        Returns:
            List[Dict]: 配图建议列表（大白话：整理好的建议）
        """
        try:
            # Try to extract JSON from the response				# 正经注释：从响应中提取 JSON / 大白话注释：从文字里找 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.warning("No JSON found in analysis response")
                return []

            data = json.loads(json_match.group())					# 正经注释：解析 JSON / 大白话注释：变成字典
            suggestions = data.get("suggestions", [])				# 正经注释：获取建议列表 / 大白话注释：AI 的建议

            # Enrich with section data								# 正经注释：将建议与原始章节数据关联 / 大白话注释：把建议和报告段落联系起来
            enriched = []
            for s in suggestions:
                section_num = s.get("section_number", 0) - 1  # Convert to 0-indexed	# 正经注释：转为 0 索引 / 大白话注释：编号从 0 开始
                if 0 <= section_num < len(sections):
                    section = sections[section_num]
                    enriched.append({
                        "section_header": section["header"],		# 正经注释：章节标题 / 大白话注释：标题
                        "section_content": section["content"][:1000],	# 正经注释：章节内容（截取） / 大白话注释：内容
                        "image_prompt": s.get("image_prompt", ""),	# 正经注释：图片提示词 / 大白话注释：画什么
                        "reason": s.get("reason", ""),				# 正经注释：配图理由 / 大白话注释：为什么这里要配图
                        "insert_after_line": section["start_line"],	# 正经注释：插入行号 / 大白话注释：图插在第几行
                    })

            return enriched

        except json.JSONDecodeError as e:							# 正经注释：JSON 解析失败 / 大白话注释：格式不对
            logger.error(f"Failed to parse analysis JSON: {e}")
            return []

    async def generate_images_for_report(							# 正经注释：后处理模式——分析已完成的报告并生成嵌入配图 / 大白话注释：报告写好后加配图
        self,
        report: str,
        query: str,
        research_id: str = "",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """分析报告并生成嵌入配图
        【正经注释】完整的后处理图片生成流程：分析 → 生成 → 嵌入。
        【大白话注释】报告写好了，看看哪里需要加图，画好图后插到报告里。
        Args:
            report: Markdown 报告（大白话：写好的报告）
            query: 研究查询（大白话：研究的问题）
            research_id: 研究 ID（大白话：任务编号）
        Returns:
            Tuple[str, List]: (修改后的报告, 生成的图片列表)（大白话：(加了图的报告, 画好的图)）
        """
        if not self.is_enabled():
            logger.info("Image generation is not enabled, skipping")
            return report, []

        # Notify about image generation starting					# 正经注释：推送开始生成图片 / 大白话注释：告诉用户"开始配图"
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "image_generation_start",
                "🎨 Analyzing report for image generation opportunities...",
                self.researcher.websocket,
            )

        # Analyze report for image opportunities					# 正经注释：分析报告寻找配图机会 / 大白话注释：看看哪里要加图
        suggestions = await self.analyze_report_for_images(report, query)

        if not suggestions:										# 正经注释：无配图建议则跳过 / 大白话注释：AI 觉得不需要加图
            logger.info("No sections identified for image generation")
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "image_generation_skip",
                    "📝 No sections identified that would benefit from images",
                    self.researcher.websocket,
                )
            return report, []

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "image_generation_analyzing",
                f"🔍 Found {len(suggestions)} sections that would benefit from images",
                self.researcher.websocket,
            )

        # Generate images for each suggestion						# 正经注释：逐个为建议生成图片 / 大白话注释：一张一张画
        generated_images = []
        for i, suggestion in enumerate(suggestions):
            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "image_generating",
                    f"🖼️ Generating image {i+1}/{len(suggestions)}: {suggestion['section_header'][:50]}...",
                    self.researcher.websocket,
                )

            try:
                images = await self.image_provider.generate_image(	# 正经注释：调用图片生成接口 / 大白话注释：画！
                    prompt=suggestion["image_prompt"],
                    context=suggestion["section_content"],
                    research_id=research_id,
                    num_images=1,
                )

                if images:
                    image_info = images[0]
                    image_info["section_header"] = suggestion["section_header"]	# 正经注释：记录章节标题 / 大白话注释：这张图属于哪个章节
                    generated_images.append(image_info)

                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "image_generated",
                            f"✅ Image generated for: {suggestion['section_header'][:50]}",
                            self.researcher.websocket,
                        )
            except Exception as e:
                logger.error(f"Failed to generate image for section '{suggestion['section_header']}': {e}")
                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "image_generation_error",
                        f"⚠️ Failed to generate image: {str(e)[:100]}",
                        self.researcher.websocket,
                    )

        # Embed images in the report								# 正经注释：将图片嵌入报告 / 大白话注释：把图插到报告里
        if generated_images:
            report = self._embed_images_in_report(report, generated_images, suggestions)	# 正经注释：调用嵌入方法 / 大白话注释：把图插进去
            self.generated_images = generated_images

            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "image_generation_complete",
                    f"🎉 Successfully generated and embedded {len(generated_images)} images",
                    self.researcher.websocket,
                )

                # Send generated images through WebSocket			# 正经注释：通过 WebSocket 推送图片给前端 / 大白话注释：把图发给前端
                await stream_output(
                    "generated_images",
                    "inline_images",
                    json.dumps([{"url": img["url"], "alt": img["alt_text"]} for img in generated_images]),
                    self.researcher.websocket,
                    True,
                    generated_images,
                )

        return report, generated_images							# 正经注释：返回修改后的报告和图片列表 / 大白话注释：交出去

    def _embed_images_in_report(									# 正经注释：将生成的图片嵌入报告 Markdown 中 / 大白话注释：把图画插到报告里合适的位置
        self,
        report: str,
        images: List[Dict[str, Any]],
        suggestions: List[Dict[str, Any]],
    ) -> str:
        """将图片嵌入报告 Markdown
        【正经注释】按章节标题匹配，在对应标题后插入 Markdown 图片语法。
        【大白话注释】找到报告里对应的标题，在标题下面插入图片。
        Args:
            report: 原始报告 Markdown（大白话：报告内容）
            images: 生成的图片信息（大白话：画好的图）
            suggestions: 原始配图建议（大白话：AI 的建议）
        Returns:
            str: 修改后的报告（大白话：加了图的报告）
        """
        lines = report.split('\n')									# 正经注释：按行分割 / 大白话注释：一行一行看

        # Create a mapping of section headers to images				# 正经注释：建立章节标题到图片的映射 / 大白话注释：把标题和图对应起来
        section_to_image = {}
        for img, sug in zip(images, suggestions):
            section_to_image[sug["section_header"]] = img

        # Find section headers and insert images after them			# 正经注释：找到标题后插入图片 / 大白话注释：找到标题就在下面加图
        modified_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            modified_lines.append(line)

            # Check if this is a header that needs an image			# 正经注释：检查是否为需要配图的标题 / 大白话注释：这个标题需要加图吗
            header_match = re.match(r'^(#{2,3})\s+(.+)$', line)
            if header_match:
                header_text = header_match.group(2)
                if header_text in section_to_image:					# 正经注释：标题在映射中则插入图片 / 大白话注释：需要加图就加上
                    img = section_to_image[header_text]
                    # Insert image after the header with a blank line	# 正经注释：在标题后空一行插入图片 Markdown / 大白话注释：空一行再放图
                    image_markdown = f"\n![{img['alt_text']}]({img['url']})\n"
                    modified_lines.append(image_markdown)

            i += 1

        return '\n'.join(modified_lines)							# 正经注释：拼接回完整报告 / 大白话注释：把所有行拼回去

    def get_generated_images(self) -> List[Dict[str, Any]]:
        """获取已生成的图片列表
        【正经注释】返回当前实例中缓存的所有已生成图片。
        【大白话注释】看看之前画了哪些图。
        Returns:
            List[Dict]: 已生成的图片信息列表（大白话：画好的图清单）
        """
        return self.generated_images

    async def process_image_placeholders(							# 正经注释：占位符模式——处理报告中的 [IMAGE: ...] 占位符 / 大白话注释：找到报告里的"画图标记"然后画
        self,
        report: str,
        query: str,
        research_id: str = "",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """处理报告中的图片占位符
        【正经注释】
        查找报告中所有 [IMAGE: description] 占位符，为每个占位符生成图片，
        然后将占位符替换为 Markdown 图片语法。
        未启用图片生成时直接移除占位符。
        【大白话注释】
        报告里可能有这种标记：[IMAGE: 系统架构图]
        这个方法就找到这些标记，画出对应的图，然后把标记替换成真正的图片。
        Args:
            report: 含占位符的报告 Markdown（大白话：带标记的报告）
            query: 研究查询（大白话：研究的问题）
            research_id: 研究 ID（大白话：任务编号）
        Returns:
            Tuple[str, List]: (处理后的报告, 生成的图片列表)（大白话：(换好图的报告, 画好的图)）
        """
        if not self.is_enabled():
            # If image generation is not enabled, just remove the placeholders	# 正经注释：未启用时移除所有占位符 / 大白话注释：不能画就把标记删掉
            report = re.sub(r'\[IMAGE:\s*[^\]]+\]', '', report)
            return report, []

        # Find all image placeholders								# 正经注释：查找所有图片占位符 / 大白话注释：找出所有"画图标记"
        placeholder_pattern = r'\[IMAGE:\s*([^\]]+)\]'
        placeholders = list(re.finditer(placeholder_pattern, report))

        if not placeholders:										# 正经注释：无占位符则直接返回 / 大白话注释：没有标记就不用处理
            logger.info("No image placeholders found in report")
            return report, []

        # Limit to max_images										# 正经注释：限制最大处理数 / 大白话注释：太多了就截断
        placeholders = placeholders[:self.max_images]

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "image_placeholders_found",
                f"🎨 Found {len(placeholders)} image placeholders to process",
                self.researcher.websocket,
            )

        generated_images = []
        replacements = []  # List of (original_text, replacement_text) tuples	# 正经注释：记录原始文本和替换文本的对应关系 / 大白话注释：记录哪个标记换成什么图

        for i, match in enumerate(placeholders):
            image_description = match.group(1).strip()				# 正经注释：提取占位符中的图片描述 / 大白话注释：标记里说的画什么
            original_text = match.group(0)							# 正经注释：完整的占位符文本 / 大白话注释：整个标记

            if self.researcher.verbose:
                await stream_output(
                    "logs",
                    "image_generating",
                    f"🖼️ Generating image {i+1}/{len(placeholders)}: {image_description[:60]}...",
                    self.researcher.websocket,
                )

            try:
                # Get image style from config (default to "dark" for app theme)	# 正经注释：从配置获取图片风格 / 大白话注释：用什么风格画
                image_style = getattr(self.cfg, 'image_generation_style', 'dark')
                logger.info(f"Using image style: {image_style}")

                # Generate the image with dark mode styling		# 正经注释：生成图片 / 大白话注释：画！
                images = await self.image_provider.generate_image(
                    prompt=image_description,						# 正经注释：图片描述 / 大白话注释：画什么
                    context=query,  # Use query as context			# 正经注释：用查询作为上下文 / 大白话注释：给画师一些背景信息
                    research_id=research_id,
                    num_images=1,
                    style=image_style,
                )

                if images:
                    image_info = images[0]
                    image_info["description"] = image_description	# 正经注释：记录描述 / 大白话注释：记下画了什么
                    generated_images.append(image_info)

                    # Create markdown replacement with absolute path for PDF compatibility	# 正经注释：创建 Markdown 图片替换文本 / 大白话注释：把标记换成图片语法
                    # Use the absolute URL for proper rendering in PDF/DOCX
                    markdown_image = f"\n\n![{image_info['alt_text']}]({image_info['url']})\n\n"
                    replacements.append((original_text, markdown_image))

                    if self.researcher.verbose:
                        await stream_output(
                            "logs",
                            "image_generated",
                            f"✅ Generated: {image_description[:40]}...",
                            self.researcher.websocket,
                        )
                else:												# 正经注释：生成失败则移除占位符 / 大白话注释：画不出来就删掉标记
                    # Remove placeholder if image generation failed
                    replacements.append((original_text, ""))
                    logger.warning(f"No image generated for: {image_description[:50]}")

            except Exception as e:									# 正经注释：异常时也移除占位符 / 大白话注释：出错了就删掉标记
                logger.error(f"Failed to generate image for '{image_description[:50]}': {e}")
                # Remove the failed placeholder
                replacements.append((original_text, ""))

                if self.researcher.verbose:
                    await stream_output(
                        "logs",
                        "image_generation_error",
                        f"⚠️ Failed to generate: {str(e)[:80]}",
                        self.researcher.websocket,
                    )

        # Apply all replacements									# 正经注释：应用所有替换 / 大白话注释：把标记都换成图
        modified_report = report
        for original, replacement in replacements:
            modified_report = modified_report.replace(original, replacement, 1)	# 正经注释：逐个替换 / 大白话注释：一个一个换

        self.generated_images = generated_images					# 正经注释：保存已生成的图片 / 大白话注释：存起来

        if generated_images and self.researcher.verbose:
            await stream_output(
                "logs",
                "image_generation_complete",
                f"🎉 Successfully generated {len(generated_images)} inline images",
                self.researcher.websocket,
            )

            # Send generated images through WebSocket				# 正经注释：通过 WebSocket 推送图片 / 大白话注释：把图发给前端
            await stream_output(
                "generated_images",
                "inline_images",
                json.dumps([{"url": img["url"], "alt": img["alt_text"]} for img in generated_images]),
                self.researcher.websocket,
                True,
                generated_images,
            )

        return modified_report, generated_images					# 正经注释：返回处理后的报告和图片 / 大白话注释：交出去

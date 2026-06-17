"""
深度研究入口脚本（deep_research/main）

【正经注释】
本模块提供了深度研究的简洁入口函数 main()，演示如何使用 GPTResearcher
执行深度研究并生成报告。通过 report_type="deep" 触发深度研究模式，
支持进度回调函数以实时跟踪研究的深度、广度和查询进度。
最终将报告导出为 PDF 文件。

【大白话注释】
这个文件是深度研究的"启动脚本"。用法很简单：给它一个问题，它就帮你
用"深度模式"去研究（就是那种一层层挖的深度研究），还能实时打印进度。
研究完了自动写报告，还帮你转成 PDF 文件保存。
可以直接命令行运行，也可以当模块导入用。
"""

from gpt_researcher import GPTResearcher  # 正经注释：导入核心研究器类，是执行研究和生成报告的主引擎 / 大白话注释：把"研究大脑"请过来，所有活儿都是它干的
from backend.utils import write_md_to_pdf  # 正经注释：导入 Markdown 转 PDF 的工具函数 / 大白话注释：把报告从文字转成 PDF 文件的工具
import asyncio  # 正经注释：异步编程核心库，用于运行异步主函数 / 大白话注释：异步用的，让程序能跑 async 函数


async def main(task: str):
    """
    深度研究主函数

    【正经注释】
    执行完整的深度研究流程：初始化 GPTResearcher（使用 deep 报告类型）、
    注册进度回调函数、执行研究、生成报告并导出为 PDF。
    进度回调会在每个研究阶段被调用，输出当前深度、广度和查询进度。

    【大白话注释】
    一键深度研究按钮！流程是：
    1. 设置一个进度监控函数，实时打印研究到哪了
    2. 创建一个"深度研究模式"的研究器
    3. 开始研究（会自动一层层深入）
    4. 写报告
    5. 把报告保存为 PDF

    Args:
        task: 要研究的主题或问题字符串
    """
    # Progress callback
    def on_progress(progress):  # 正经注释：定义进度回调函数，接收 ResearchProgress 对象 / 大白话注释：研究进度监控器，每次有进展就被调用
        print(f"Depth: {progress.current_depth}/{progress.total_depth}")  # 正经注释：打印当前深度进度 / 大白话注释：显示"现在挖到第几层了/总共要挖几层"
        print(f"Breadth: {progress.current_breadth}/{progress.total_breadth}")  # 正经注释：打印当前广度进度 / 大白话注释：显示"这一层搜几个问题/总共搜几个"
        print(f"Queries: {progress.completed_queries}/{progress.total_queries}")  # 正经注释：打印查询完成进度 / 大白话注释：显示"已经搜了几个问题/总共要搜几个"
        if progress.current_query:  # 正经注释：如果有当前正在处理的查询则打印 / 大白话注释：如果正在搜某个问题，就显示出来
            print(f"Current query: {progress.current_query}")

    # Initialize researcher with deep research type
    researcher = GPTResearcher(  # 正经注释：初始化 GPTResearcher 实例 / 大白话注释：创建"研究大脑"
        query=task,  # 正经注释：传入研究主题 / 大白话注释：告诉它研究什么
        report_type="deep",  # This will trigger deep research  # 正经注释：使用 deep 类型触发深度研究模式 / 大白话注释：用"深度模式"，会一层层深入挖掘
    )

    # Run research with progress tracking
    print("Starting deep research...")  # 正经注释：输出研究开始提示 / 大白话注释：告诉用户"开始挖了"
    context = await researcher.conduct_research(on_progress=on_progress)  # 正经注释：执行深度研究，传入进度回调 / 大白话注释：让研究大脑开始干活，有进展就通知我
    print("\nResearch completed. Generating report...")  # 正经注释：输出研究完成提示 / 大白话注释：告诉用户"资料搜完了，开始写报告"

    # Generate the final report
    report = await researcher.write_report()  # 正经注释：基于研究结果生成最终报告 / 大白话注释：让研究大脑把搜到的资料写成报告
    await write_md_to_pdf(report, "deep_research_report")  # 正经注释：将报告导出为 PDF 文件 / 大白话注释：把报告保存成 PDF 文件
    print(f"\nFinal Report: {report}")  # 正经注释：输出生成的报告全文 / 大白话注释：把报告内容打印出来看看

if __name__ == "__main__":  # 正经注释：脚本直接运行时的入口 / 大白话注释：直接运行这个文件时执行下面的代码
    query = "What are the most effective ways for beginners to start investing?"  # 正经注释：默认研究问题示例 / 大白话注释：默认研究问题：新手怎么开始投资？
    asyncio.run(main(query))  # 正经注释：运行异步主函数 / 大白话注释：启动异步程序，开始研究！

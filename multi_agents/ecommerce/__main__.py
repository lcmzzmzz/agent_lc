"""
EcomResearcher 独立 CLI 入口。

【正经注释】
通过 `python -m multi_agents.ecommerce ...` 调用，不修改原 cli.py。
负责解析参数、调用 runner、打印输出文件路径。

【大白话注释】
命令行启动入口。在终端敲一行命令就能跑：
python -m multi_agents.ecommerce --query "portable blender" --market US --depth standard
"""

from __future__ import annotations

import argparse
import asyncio

from multi_agents.ecommerce.llm_helper import default_llm_fn
from multi_agents.ecommerce.runner import run_ecommerce_research


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="multi_agents.ecommerce",
        description="EcomResearcher：跨境电商 AI 选品与市场调研助手",
    )
    parser.add_argument("--query", required=True, help="品类关键词，例如 portable blender")
    parser.add_argument("--market", default="US", help="目标市场，默认 US")
    parser.add_argument(
        "--platforms",
        default="amazon,google",
        help="平台偏好，逗号分隔，默认 amazon,google",
    )
    parser.add_argument(
        "--depth",
        default="standard",
        choices=["fast", "standard", "deep"],
        help="调研深度，默认 standard",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="禁用 LLM 打分，退回纯规则模式（不消耗 LLM 额度）",
    )
    return parser


def main() -> None:
    # 加载 .env，使 TAVILY_API_KEY 等检索器配置生效
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    args = build_parser().parse_args()

    result = asyncio.run(
        run_ecommerce_research(
            query=args.query,
            target_market=args.market,
            platforms=[p.strip() for p in args.platforms.split(",") if p.strip()],
            depth=args.depth,
            llm_fn=None if args.no_llm else default_llm_fn,
        )
    )

    paths = result["output_paths"]
    print("Ecommerce research complete.")
    print(f"Report:  {paths['report']}")
    print(f"Audit:   {paths['audit']}")
    print(f"Quality: {paths['quality']}")


if __name__ == "__main__":
    main()

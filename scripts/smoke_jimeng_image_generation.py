from __future__ import annotations

import asyncio
from pathlib import Path

from multi_agents.ecommerce.tools.image_generation.base import ImageGenerationRequest
from multi_agents.ecommerce.tools.image_generation.volc_ark_jimeng import (
    VolcArkJimengProvider,
)


async def main() -> None:
    output_dir = Path("outputs/ecommerce/smoke-jimeng")
    provider = VolcArkJimengProvider(output_dir=output_dir)
    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="smoke_portable_blender",
            prompt=(
                "Minimal ecommerce product concept render of a portable blender on a pure white background, "
                "transparent cup, soft natural light, premium clean Amazon main image style, no logo, no text."
            ),
            model="doubao-seedream-4-5-251128",
            size="2K",
            watermark=False,
        )
    )
    print(
        {
            "status": result.status,
            "local_path": result.local_path,
            "remote_url": result.remote_url,
            "width": result.width,
            "height": result.height,
            "warning": result.warning,
            "usage": result.usage,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

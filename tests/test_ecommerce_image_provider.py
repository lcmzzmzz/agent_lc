from pathlib import Path

import pytest

from multi_agents.ecommerce.tools.image_generation.base import ImageGenerationRequest
from multi_agents.ecommerce.tools.image_generation.volc_ark_jimeng import VolcArkJimengProvider


class FakeImageData:
    def __init__(self, url="https://example.com/image.jpeg", size="2048x2048"):
        self.url = url
        self.size = size


class FakeUsage:
    generated_images = 1
    output_tokens = 100
    total_tokens = 100


class FakeResponse:
    def __init__(self, size="2048x2048"):
        self.data = [FakeImageData(size=size)]
        self.usage = FakeUsage()


class FakeImages:
    def __init__(self, response=None):
        self.kwargs = None
        self.response = response or FakeResponse()

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class FakeArkClient:
    def __init__(self, response=None):
        self.images = FakeImages(response)


def fake_downloader(url, target_path):
    path = Path(target_path).with_suffix(".jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-image")
    return {
        "local_path": str(path),
        "mime_type": "image/jpeg",
        "width": 2048,
        "height": 2048,
    }


@pytest.mark.asyncio
async def test_seedream_45_omits_unsupported_output_format(tmp_path):
    client = FakeArkClient()
    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=client,
        downloader=fake_downloader,
    )

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "success"
    assert "output_format" not in client.images.kwargs
    assert client.images.kwargs["response_format"] == "url"
    assert Path(result.local_path).exists()
    assert result.width == 2048
    assert result.height == 2048


@pytest.mark.asyncio
async def test_provider_reads_local_image_size_when_sdk_omits_size(tmp_path):
    from PIL import Image

    def png_downloader(url, target_path):
        path = Path(target_path).with_suffix(".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 24), color=(255, 255, 255)).save(path)
        return {
            "local_path": str(path),
            "mime_type": "image/png",
            "width": 0,
            "height": 0,
        }

    client = FakeArkClient(FakeResponse(size=""))
    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=client,
        downloader=png_downloader,
    )

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "success"
    assert result.width == 32
    assert result.height == 24


@pytest.mark.asyncio
async def test_seedream_50_sends_png_output_format(tmp_path):
    client = FakeArkClient()
    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=client,
        downloader=fake_downloader,
    )

    await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-5-0-260128",
        )
    )

    assert client.images.kwargs["output_format"] == "png"


@pytest.mark.asyncio
async def test_missing_api_key_returns_failed_result(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_ARK_API_KEY", raising=False)
    provider = VolcArkJimengProvider(output_dir=tmp_path)

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "failed"
    assert result.warning == "missing ARK_API_KEY"


@pytest.mark.asyncio
async def test_provider_error_is_redacted(tmp_path):
    class BrokenImages:
        def generate(self, **kwargs):
            raise RuntimeError("ARK_API_KEY=secret-token exploded")

    class BrokenClient:
        images = BrokenImages()

    provider = VolcArkJimengProvider(
        output_dir=tmp_path,
        ark_client=BrokenClient(),
        downloader=fake_downloader,
    )

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "failed"
    assert "secret-token" not in result.warning
    assert "ARK_API_KEY=[REDACTED]" in result.warning


@pytest.mark.asyncio
async def test_provider_returns_failed_when_client_init_raises(tmp_path):
    # [FIX-8] an SDK import / Ark() init failure must surface as a failed result, not raise.
    provider = VolcArkJimengProvider(output_dir=tmp_path, api_key="fake-key")

    def boom():
        raise RuntimeError("ARK_API_KEY=secret-init Ark init exploded")

    provider._client = boom  # type: ignore[assignment]

    result = await provider.generate(
        ImageGenerationRequest(
            asset_id="visual_product_01",
            prompt="portable blender product photo",
            model="doubao-seedream-4-5-251128",
        )
    )

    assert result.status == "failed"
    assert "secret-init" not in result.warning
    assert "ARK_API_KEY=[REDACTED]" in result.warning

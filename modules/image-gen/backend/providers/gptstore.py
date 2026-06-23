import logging

from .base import GenResult, GenSpec, ImageProvider

logger = logging.getLogger("v2.image-gen").getChild("gptstore")


class GPTStoreProvider(ImageProvider):
    provider_key = "gptstore"

    async def generate(self, spec: GenSpec) -> list[GenResult]:
        from app.gateway.router import gateway_router

        size = f"{spec.width}x{spec.height}"
        result = await gateway_router.generate_image(
            prompt=spec.prompt, size=size, count=spec.count,
        )

        images: list[GenResult] = []
        for img_data in result.get("images", []):
            b64_str = img_data.get("b64", "")
            if b64_str:
                import base64
                images.append(GenResult(
                    image_bytes=base64.b64decode(b64_str),
                    meta={"placeholder": False},
                ))

        if not images:
            error_msg = result.get("error", "No images returned from gateway")
            raise RuntimeError(error_msg)

        logger.info("GPTStore generated %d images for prompt=%r", len(images), spec.prompt[:80])
        return images

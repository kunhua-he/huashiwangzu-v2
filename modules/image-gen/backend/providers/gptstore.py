import base64
import logging
import re

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

    async def transform(self, spec: GenSpec) -> list[GenResult]:
        source_images = spec.extra.get("source_images")
        if not isinstance(source_images, list) or not source_images:
            raise RuntimeError("source image bytes are required")
        source = source_images[0] if isinstance(source_images[0], dict) else {}
        source_bytes = source.get("bytes")
        if not source_bytes:
            raise RuntimeError("source image bytes are required")

        from app.config import get_settings
        from app.gateway.config import get_model_type_config

        cfg = get_settings()
        api_key = cfg.GPTSTORE_API_KEY
        base_url = cfg.GPTSTORE_BASE_URL.rstrip("/")
        proxy_url = cfg.GPTSTORE_PROXY
        if not api_key:
            raise NotImplementedError("GPTSTORE_API_KEY not configured")

        img_cfg = get_model_type_config("image_gen")
        profile_key, profile = self._resolve_image_profile(img_cfg)
        model_name = profile.get("model")
        if not model_name:
            raise RuntimeError(f"Image generation profile '{profile_key}' is missing model")

        size = f"{spec.width}x{spec.height}"

        prompt = self._build_transform_prompt(spec)
        tool_config: dict = {"type": "image_generation", "action": "edit"}
        m = re.match(r"^(\d+)\s*[xX]\s*(\d+)$", size.strip())
        if m:
            tool_config["dimensions"] = f"{m.group(1)}x{m.group(2)}"

        import httpx

        client_kw: dict = {
            "timeout": httpx.Timeout(180.0),
            "follow_redirects": True,
        }
        if proxy_url:
            client_kw["proxy"] = httpx.Proxy(url=proxy_url)

        images: list[GenResult] = []
        async with httpx.AsyncClient(**client_kw) as client:
            for _ in range(spec.count):
                content = [{"type": "input_text", "text": prompt}]
                for source in source_images[:8]:
                    if not isinstance(source, dict):
                        continue
                    raw_bytes = source.get("bytes")
                    if not raw_bytes:
                        continue
                    mime_type = source.get("mime_type") or "image/png"
                    image_b64 = base64.b64encode(raw_bytes).decode("ascii")
                    content.append({
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_b64}",
                    })
                body = {
                    "model": model_name,
                    "input": [
                        {
                            "role": "user",
                            "content": content,
                        }
                    ],
                    "tools": [tool_config],
                    "store": False,
                }
                resp = await client.post(
                    f"{base_url}/responses",
                    json=body,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                for raw in self._extract_image_b64(data):
                    images.append(GenResult(
                        image_bytes=base64.b64decode(raw),
                        meta={"placeholder": False},
                    ))
                if len(images) >= spec.count:
                    break

        if not images:
            raise RuntimeError("No images returned from GPTStore image-to-image")

        logger.info("GPTStore transformed %d images for prompt=%r", len(images), spec.prompt[:80])
        return images[:spec.count]

    @staticmethod
    def _resolve_image_profile(img_cfg: dict) -> tuple[str, dict]:
        primary = str(img_cfg.get("primary") or "")
        fallback_chain = img_cfg.get("fallback_chain", [])
        profiles = img_cfg.get("profiles", {})
        candidate_keys = [primary] + fallback_chain if primary else fallback_chain
        for key in candidate_keys:
            profile = profiles.get(key)
            if profile:
                return str(key), profile
        raise RuntimeError("No image generation profile configured")

    @staticmethod
    def _build_transform_prompt(spec: GenSpec) -> str:
        mode = str(spec.extra.get("mode") or "edit")
        strength = spec.extra.get("strength")
        preserve_subject = bool(spec.extra.get("preserve_subject", True))
        parts = [spec.prompt]
        if mode:
            parts.append(f"Mode: {mode}.")
        if strength is not None:
            parts.append(f"Edit strength: {strength}.")
        if preserve_subject:
            parts.append("Preserve the main subject, identity, product shape, and readable labels unless explicitly changed.")
        return "\n".join(parts)

    @staticmethod
    def _extract_image_b64(data: dict) -> list[str]:
        images: list[str] = []
        for item in data.get("output", []):
            if item.get("type") == "image_generation_call":
                raw = item.get("result") or item.get("b64_json")
                if raw:
                    images.append(raw)
        return images

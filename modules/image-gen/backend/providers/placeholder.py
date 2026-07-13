import io
import logging

from PIL import Image, ImageDraw, ImageFont

from .base import GenResult, GenSpec, ImageProvider

logger = logging.getLogger("v2.image-gen").getChild("placeholder")


class PlaceholderProvider(ImageProvider):
    provider_key = "placeholder"

    async def generate(self, spec: GenSpec) -> list[GenResult]:
        results: list[GenResult] = []
        for _ in range(spec.count):
            buf = io.BytesIO()
            img = self._make_placeholder(spec.prompt, spec.width, spec.height)
            img.save(buf, format="PNG")
            results.append(GenResult(
                image_bytes=buf.getvalue(),
                meta={"placeholder": True},
            ))
        logger.info("Generated %d placeholder images for prompt=%r", spec.count, spec.prompt[:80])
        return results

    async def transform(self, spec: GenSpec) -> list[GenResult]:
        source_images = spec.extra.get("source_images")
        if not isinstance(source_images, list) or not source_images:
            raise RuntimeError("source image bytes are required")
        source_bytes_list = [
            source.get("bytes")
            for source in source_images[:8]
            if isinstance(source, dict) and source.get("bytes")
        ]
        if not source_bytes_list:
            raise RuntimeError("source image bytes are required")
        results: list[GenResult] = []
        for _ in range(spec.count):
            buf = io.BytesIO()
            img = self._make_transform_placeholder(spec.prompt, source_bytes_list, spec.width, spec.height)
            img.save(buf, format="PNG")
            results.append(GenResult(
                image_bytes=buf.getvalue(),
                meta={"placeholder": True},
            ))
        logger.info("Generated %d transform placeholder images for prompt=%r", spec.count, spec.prompt[:80])
        return results

    @staticmethod
    def _make_placeholder(prompt: str, width: int, height: int) -> Image.Image:
        img = Image.new("RGB", (width, height), (245, 245, 245))
        draw = ImageDraw.Draw(img)

        watermark_text = "图片生成功能开发中"
        prompt_display = prompt if len(prompt) <= 60 else prompt[:57] + "..."

        font_large = None
        font_small = None
        for font_path in (
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ):
            try:
                font_large = ImageFont.truetype(font_path, 32)
                font_small = ImageFont.truetype(font_path, 24)
                break
            except (OSError, IOError):
                continue
        if font_large is None:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), prompt_display, font=font_large)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (width - tw) // 2
        ty = (height - th) // 2 - 30
        draw.text((tx, ty), prompt_display, fill=(60, 60, 60), font=font_large)

        wbbox = draw.textbbox((0, 0), watermark_text, font=font_small)
        ww = wbbox[2] - wbbox[0]
        wx = (width - ww) // 2
        wy = ty + th + 40
        draw.text((wx, wy), watermark_text, fill=(160, 160, 160), font=font_small)

        return img

    @staticmethod
    def _make_transform_placeholder(
        prompt: str,
        source_bytes_list: list[bytes | None],
        width: int,
        height: int,
    ) -> Image.Image:
        img = Image.new("RGB", (width, height), (245, 245, 245))
        draw = ImageDraw.Draw(img)

        font_large = None
        font_small = None
        for font_path in (
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ):
            try:
                font_large = ImageFont.truetype(font_path, 30)
                font_small = ImageFont.truetype(font_path, 20)
                break
            except (OSError, IOError):
                continue
        if font_large is None:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        thumbs: list[Image.Image] = []
        for source_bytes in source_bytes_list:
            if not source_bytes:
                continue
            try:
                with Image.open(io.BytesIO(source_bytes)) as source_img:
                    thumb = source_img.convert("RGB")
                    max_thumb = (max(1, int(width * 0.38)), max(1, int(height * 0.42)))
                    thumb.thumbnail(max_thumb)
                    thumbs.append(thumb.copy())
            except Exception:
                continue
        if thumbs:
            columns = min(2, len(thumbs))
            gap = 12
            total_width = sum(thumb.width for thumb in thumbs[:columns]) + gap * (columns - 1)
            x = max(12, (width - total_width) // 2)
            y = max(24, int(height * 0.12))
            for thumb in thumbs[:4]:
                if x + thumb.width > width - 12:
                    x = max(12, (width - total_width) // 2)
                    y += max(item.height for item in thumbs[:columns]) + gap
                img.paste(thumb, (x, y))
                draw.rectangle(
                    (x, y, x + thumb.width - 1, y + thumb.height - 1),
                    outline=(180, 180, 180),
                    width=2,
                )
                x += thumb.width + gap

        title = "图生图功能开发中"
        prompt_display = prompt if len(prompt) <= 56 else prompt[:53] + "..."
        title_bbox = draw.textbbox((0, 0), title, font=font_large)
        title_x = (width - (title_bbox[2] - title_bbox[0])) // 2
        title_y = int(height * 0.74)
        draw.text((title_x, title_y), title, fill=(60, 60, 60), font=font_large)

        prompt_bbox = draw.textbbox((0, 0), prompt_display, font=font_small)
        prompt_x = (width - (prompt_bbox[2] - prompt_bbox[0])) // 2
        prompt_y = title_y + 46
        draw.text((prompt_x, prompt_y), prompt_display, fill=(120, 120, 120), font=font_small)

        return img

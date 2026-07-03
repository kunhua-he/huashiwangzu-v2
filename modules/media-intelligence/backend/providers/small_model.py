from __future__ import annotations

from .base import MediaContext, MediaProvider, StageResult


class SmallModelProvider(MediaProvider):
    provider_key = "small_model.rule_based_summary"

    async def run(self, context: MediaContext) -> StageResult:
        modality = "image" if context.media_type == "image" else "video"
        summary = (
            f"{modality.title()} file {context.file_name} was analyzed with local file facts. "
            "No trained small-model runtime is configured, so this summary is rule-based."
        )
        tags = [context.media_type, context.extension]
        if context.size_bytes > 20_000_000:
            tags.append("large_file")
        return StageResult(
            stage="small_model",
            provider=self.provider_key,
            status="degraded",
            data={
                "summary": summary,
                "tags": tags,
                "model": "not_configured",
                "degraded": [
                    {
                        "code": "small_model_missing",
                        "dependency": "small_model",
                        "message": "No local CLIP/YOLO/classifier/ASR adapter is configured; summary uses rule-based facts.",
                        "install_command": "Install a small-model adapter and register it under media-intelligence providers.",
                    }
                ],
            },
            warnings=["No small-model adapter is configured; using a rule-based summary."],
            confidence=0.4,
        )

"""Shared prompt template loader for knowledge module services.

Each service calls ``load_prompt(db, template_name, fallback)`` at the top
of its entry-point functions to retrieve the system prompt from the framework
``framework_prompt_templates`` table.  When the DB lookup fails the
*fallback* string is used instead (with a clear warning), so the system never
silently produces empty prompts.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge").getChild("prompt_utils")

# Template name constants — the single source of truth for prompt identity.
TPROFILE = "knowledge_profile_system"
TENTITY = "knowledge_entity_extraction"
TFUSION = "knowledge_page_fusion"
TFUSION_LEGACY = "knowledge_page_fusion_legacy"
TRAW_OCR = "knowledge_raw_ocr"
TRAW_VISION = "knowledge_raw_vision"

# Short inline fallbacks (last resort when DB is unreachable).
# These are NOT the full prompts — see seed.py for the canonical versions.
_FALLBACK_PROFILE = (
    "# System\nAnalyze the fused page content and generate a document-level "
    "profile. Return JSON."
)
_FALLBACK_ENTITY = (
    "# System\nExtract entities and relationships from the given content. "
    "Return JSON with \"entities\" and \"relationships\"."
)
_FALLBACK_FUSION = (
    "# System\nCross-validate three rounds of raw extraction results and "
    "produce a fused authoritative description. Return JSON."
)
_FALLBACK_FUSION_LEGACY = (
    "# System\nMerge chunked content into coherent paragraphs. "
    "Return plain text only."
)
_FALLBACK_RAW_OCR = "# System\nExtract all visible text from the image in reading order."
_FALLBACK_RAW_VISION = "# System\nDescribe the page layout and visual composition."

FALLBACKS: dict[str, str] = {
    TPROFILE: _FALLBACK_PROFILE,
    TENTITY: _FALLBACK_ENTITY,
    TFUSION: _FALLBACK_FUSION,
    TFUSION_LEGACY: _FALLBACK_FUSION_LEGACY,
    TRAW_OCR: _FALLBACK_RAW_OCR,
    TRAW_VISION: _FALLBACK_RAW_VISION,
}


async def load_prompt(db: AsyncSession | None, template_name: str) -> str:
    """Load and render a prompt template from the framework DB.

    Args:
        db: Active database session. ``None`` means the DB is unavailable.
        template_name: The ``name`` column value in ``framework_prompt_templates``.

    Returns:
        The rendered prompt content string.

    Raises:
        RuntimeError: If both DB lookup and fallback fail.
    """
    fallback = FALLBACKS.get(template_name)
    if db is None:
        if fallback:
            logger.warning("Prompt template '%s' requested without DB, using fallback", template_name)
            return fallback
        raise RuntimeError(f"Prompt template '{template_name}' not available")

    from app.services.prompt_service import render_template

    try:
        return await render_template(db, template_name)
    except Exception as exc:
        if fallback:
            logger.warning(
                "Prompt template '%s' not found in DB, using fallback: %s",
                template_name, exc,
            )
            return fallback
        logger.error(
            "Prompt template '%s' not found and no fallback defined: %s",
            template_name, exc,
        )
        raise RuntimeError(f"Prompt template '{template_name}' not available") from exc

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_knowledge_module(module_suffix: str):
    package_prefix = (
        "huashiwangzu_modules.knowledge"
        if any(name.startswith("huashiwangzu_modules.knowledge") for name in sys.modules)
        else "modules.knowledge.backend"
    )
    module_name = f"{package_prefix}.{module_suffix}"
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    return importlib.import_module(module_name)


entity_service = _load_knowledge_module("services.entity_service")
fusion_service = _load_knowledge_module("services.fusion_service")
profile_service = _load_knowledge_module("services.profile_service")
prompt_utils = _load_knowledge_module("services.prompt_utils")
TENTITY = prompt_utils.TENTITY
TFUSION = prompt_utils.TFUSION
TPROFILE = prompt_utils.TPROFILE


class _FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows

    def first(self) -> object | None:
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self) -> object | None:
        return self.first()


class _FakeExecuteResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self.rows)

    def scalar_one_or_none(self) -> object | None:
        return self.rows[0] if self.rows else None


class _FakeProfileDb:
    def __init__(self) -> None:
        fusion = SimpleNamespace(
            page=1,
            fused_text="模板运行路径测试正文，长度超过二十个字符。",
            page_summary="模板测试摘要",
        )
        document = SimpleNamespace(summary="")
        self._results = [
            _FakeExecuteResult([fusion]),
            _FakeExecuteResult([]),
            _FakeExecuteResult([document]),
        ]
        self.added: list[object] = []

    async def execute(self, _statement: object) -> _FakeExecuteResult:
        return self._results.pop(0)

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_fusion_llm_uses_db_prompt(monkeypatch):
    marker = "DB-FUSION-PROMPT"
    seen: dict[str, object] = {}
    db = object()

    async def fake_load_prompt(received_db: object, template_name: str) -> str:
        seen["load"] = (received_db, template_name)
        return marker

    async def fake_chat(*args, **kwargs) -> dict:
        messages = kwargs.get("messages") or args[0]
        seen["system"] = messages[0]["content"]
        return {
            "content": json.dumps(
                {
                    "fused_text": "融合正文",
                    "page_summary": "摘要",
                    "page_title": None,
                    "entities": [],
                    "attributes": {},
                    "tags": [],
                    "conflicts": [],
                    "confidence": 0.9,
                },
                ensure_ascii=False,
            )
        }

    monkeypatch.setattr(fusion_service, "load_prompt", fake_load_prompt)
    monkeypatch.setattr(fusion_service.gateway_router, "chat", fake_chat)

    result = await fusion_service._llm_fuse(db, {1: "第一轮", 2: "第二轮", 3: "第三轮"})

    assert seen["load"] == (db, TFUSION)
    assert seen["system"] == marker
    assert result["fused_text"] == "融合正文"


@pytest.mark.asyncio
async def test_entity_extraction_uses_db_prompt(monkeypatch):
    marker = "DB-ENTITY-PROMPT"
    seen: dict[str, object] = {}
    db = object()

    async def fake_load_prompt(received_db: object, template_name: str) -> str:
        seen["load"] = (received_db, template_name)
        return marker

    async def fake_chat(*args, **kwargs) -> dict:
        messages = kwargs.get("messages") or args[0]
        seen["system"] = messages[0]["content"]
        return {"content": json.dumps({"entities": [{"name": "华世", "category": "组织"}], "relationships": []})}

    monkeypatch.setattr(entity_service, "load_prompt", fake_load_prompt)
    monkeypatch.setattr(entity_service.gateway_router, "chat", fake_chat)

    result = await entity_service.extract_entities_from_text("华世是一家企业。", db=db)

    assert seen["load"] == (db, TENTITY)
    assert seen["system"] == marker
    assert result["entities"][0]["name"] == "华世"


@pytest.mark.asyncio
async def test_profile_generation_uses_db_prompt(monkeypatch):
    marker = "DB-PROFILE-PROMPT"
    seen: dict[str, object] = {}
    db = _FakeProfileDb()

    async def fake_load_prompt(received_db: object, template_name: str) -> str:
        seen["load"] = (received_db, template_name)
        return marker

    async def fake_chat(*args, **kwargs) -> dict:
        messages = kwargs.get("messages") or args[0]
        seen["system"] = messages[0]["content"]
        return {
            "content": json.dumps(
                {
                    "subject": "模板画像",
                    "doc_type": "其他",
                    "chapter_structure": [],
                    "core_conclusions": "结论",
                    "key_entities": [],
                    "doc_summary": "摘要",
                    "searchable_phrases": [],
                    "applicable_scenarios": "",
                    "expiry_risk": "low",
                    "confidence": 0.8,
                },
                ensure_ascii=False,
            )
        }

    async def fake_embedding(_text: str) -> None:
        return None

    monkeypatch.setattr(profile_service, "load_prompt", fake_load_prompt)
    monkeypatch.setattr(profile_service.gateway_router, "chat", fake_chat)
    monkeypatch.setattr(profile_service, "get_embedding", fake_embedding)

    result = await profile_service.generate_document_profile(db, document_id=1, owner_id=2)

    assert seen["load"] == (db, TPROFILE)
    assert seen["system"] == marker
    assert result["subject"] == "模板画像"

from __future__ import annotations

from app.services import module_registry


def test_caller_owner_id_is_parsed_and_rejects_invalid_values() -> None:
    assert module_registry._caller_owner_id("user:42") == 42
    assert module_registry._caller_owner_id("user:not-an-int") is None
    assert module_registry._caller_owner_id("system:task-worker") is None


def test_register_capability_normalizes_execution_and_retrieval_contracts() -> None:
    async def handler(params: dict, caller: str) -> dict:
        return {"params": params, "caller": caller}

    module_registry.register_capability(
        "snapshot-test",
        "read",
        handler,
        description="Read a snapshot test record",
        parameters={"record_id": {"type": "integer"}},
        execution_contract={
            "execution_mode": "sync",
            "resource_class": "fast",
            "timeout_seconds": 5,
            "idempotency": "supported",
            "side_effect_level": "none",
            "output_reference_types": ["record", "record"],
            "parallel_safe": True,
        },
        retrieval={
            "aliases": ["find record", "read record"],
            "when_to_use": "When the user asks for one stored record",
            "input_reference_types": ["record"],
        },
    )
    try:
        capability = next(
            item
            for item in module_registry.list_capabilities()
            if item["module"] == "snapshot-test" and item["action"] == "read"
        )
        assert capability["execution_contract"]["timeout_seconds"] == 5
        assert capability["execution_contract"]["output_reference_types"] == ["record"]
        assert capability["execution_contract"]["contract_declared"] is True
        assert capability["execution_contract"]["risk_declared"] is True
        assert capability["retrieval"]["aliases"] == ["find record", "read record"]
    finally:
        module_registry.unregister_capability("snapshot-test")


def test_missing_execution_contract_is_visible_to_structured_runtime() -> None:
    async def handler(params: dict, caller: str) -> dict:
        return {"params": params, "caller": caller}

    module_registry.register_capability("snapshot-test", "uncontracted", handler)
    try:
        capability = next(
            item
            for item in module_registry.list_capabilities()
            if item["module"] == "snapshot-test" and item["action"] == "uncontracted"
        )
        assert capability["execution_contract"]["contract_declared"] is False
        assert capability["execution_contract"]["risk_declared"] is False
    finally:
        module_registry.unregister_capability("snapshot-test")


def test_outbound_contract_defaults_to_confirmation_not_readonly() -> None:
    normalized = module_registry._normalize_execution_contract(
        {
            "side_effect_level": "outbound",
            "idempotency": "required",
        },
    )
    assert normalized["side_effect_level"] == "outbound"
    assert normalized["approval_policy"] == "requires_confirmation"
    assert normalized["risk_declared"] is True


def test_invalid_idempotency_is_not_silently_downgraded() -> None:
    normalized = module_registry._normalize_execution_contract(
        {
            "side_effect_level": "outbound",
            "idempotency": "sometimes",
        },
    )
    assert normalized["idempotency"] == "invalid"

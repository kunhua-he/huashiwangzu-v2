from __future__ import annotations

from dataclasses import replace

import pytest
from app.services.permission_service import PrincipalContext, allowed_capability_ids


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _RowResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Identity:
    def __init__(self, identity_id: int, mode: str = "all") -> None:
        self.id = identity_id
        self.permission_match_mode = mode


@pytest.mark.asyncio
async def test_allowed_capabilities_default_open_and_permission_filtered() -> None:
    results = iter([
        _ScalarResult([_Identity(1), _Identity(2), _Identity(3, "any")]),
        _RowResult([(2, 7), (2, 8), (3, 8), (3, 9)]),
    ])

    class FakeSession:
        async def execute(self, _statement):
            return next(results)

    principal = PrincipalContext(user_id=4, permission_ids=(7, 8))
    allowed = await allowed_capability_ids(
        FakeSession(),  # type: ignore[arg-type]
        principal=principal,
        capability_ids=[1, 2, 3],
    )

    assert allowed == {1, 2, 3}

    results = iter([
        _ScalarResult([_Identity(1), _Identity(2), _Identity(3, "any")]),
        _RowResult([(2, 7), (2, 8), (3, 8), (3, 9)]),
    ])
    restricted = await allowed_capability_ids(
        FakeSession(),  # type: ignore[arg-type]
        principal=replace(principal, permission_ids=(7,)),
        capability_ids=[1, 2, 3],
    )

    assert restricted == {1}

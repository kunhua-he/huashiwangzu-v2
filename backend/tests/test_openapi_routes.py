from app.main import app


def test_framework_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/api/desktop/apps" in paths
    assert "/api/desktop/state" in paths
    assert "/api/files/list" in paths
    assert "/api/login" in paths
    assert "/api/users/" in paths
    assert "/api/roles/matrix" in paths
    assert "/api/system/status" in paths
    assert "/api/settings/" in paths
    assert "/api/menu" in paths
    assert "/api/health" in paths


def test_openapi_operation_ids_are_unique() -> None:
    operation_ids: list[str] = []
    for methods in app.openapi()["paths"].values():
        for operation in methods.values():
            operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids))

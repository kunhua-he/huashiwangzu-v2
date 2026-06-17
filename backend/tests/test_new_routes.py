from app.main import app


def test_framework_core_routes_exist():
    paths = app.openapi()["paths"]
    assert "/api/desktop/apps/{app_key}" in paths
    assert "/api/app-manager/apps/scan-register" in paths
    assert "/api/roles/matrix/export" in paths

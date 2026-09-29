from commerce_connector.api.app import create_app


def test_frontpage_product_endpoints_exist():
    paths = set(create_app().openapi()["paths"])
    expected = {
        "/api/v1/auth/signup",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/session",
        "/api/v1/me",
        "/api/v1/me/profile",
        "/api/v1/me/workspaces",
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/tasks/{task_id}/messages",
        "/api/v1/library",
        "/api/v1/files",
        "/api/v1/files/upload",
        "/api/v1/files/{file_id}",
        "/api/v1/models",
        "/api/v1/subscription/plans",
        "/api/v1/subscription",
        "/api/v1/subscription/usage",
        "/api/v1/subscription/upgrade-intent",
        "/api/v1/ai/ask",
        "/api/v1/ai/stream",
    }
    assert expected.issubset(paths)


def test_no_backend_secret_values_in_openapi():
    text = str(create_app().openapi()).lower()
    assert "your_server_side_service_role_key" not in text
    assert "your_gemini_api_key" not in text
    assert "database_url" not in text

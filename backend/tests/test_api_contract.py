from commerce_connector.api.app import create_app


def test_openapi_contains_frontend_contract():
    app = create_app()
    schema = app.openapi()
    paths = set(schema["paths"])
    expected = {
        "/api/v1/health",
        "/api/v1/tenants",
        "/api/v1/platforms",
        "/api/v1/connections",
        "/api/v1/connections/{connection_id}/resources",
        "/api/v1/connections/{connection_id}/test",
        "/api/v1/sync/run",
        "/api/v1/sync/background",
        "/api/v1/sync/jobs/{job_id}",
        "/api/v1/data/catalog",
        "/api/v1/data/overview/{tenant_id}",
        "/api/v1/data/{layer}/{table}",
        "/api/v1/ai/rag/rebuild",
        "/api/v1/ai/ask",
        "/api/v1/dashboards",
    }
    assert expected.issubset(paths)


def test_openapi_has_no_backend_secret_fields_in_responses():
    schema = create_app().openapi()
    serialized = str(schema).lower()
    assert "supabase_service_role_key" not in serialized
    assert "gemini_api_key" not in serialized
    assert "database_url" not in serialized

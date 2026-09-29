"""The 15 endpoints the frontend depends on must exist with the right HTTP method."""
from commerce_connector.api.app import create_app

REQUIRED = [
    ("get", "/api/v1/me"),
    ("get", "/api/v1/platforms"),
    ("get", "/api/v1/connections"),
    ("get", "/api/v1/library"),
    ("get", "/api/v1/files"),
    ("get", "/api/v1/models"),
    ("get", "/api/v1/prompts"),
    ("get", "/api/v1/subscription"),
    ("get", "/api/v1/usage"),
    ("get", "/api/v1/health"),
    ("post", "/api/v1/conversations"),
    ("get", "/api/v1/conversations"),
    ("get", "/api/v1/conversations/{id}"),
    ("post", "/api/v1/conversations/{id}/messages"),
    ("post", "/api/v1/conversations/{id}/stream"),
]


def test_all_required_endpoints_exist():
    paths = create_app().openapi()["paths"]
    missing = [(m, p) for m, p in REQUIRED if p not in paths or m not in paths[p]]
    assert not missing, f"Missing endpoints: {missing}"


def test_old_task_routes_still_work_for_backward_compatibility():
    paths = create_app().openapi()["paths"]
    assert "post" in paths["/api/v1/tasks"]
    assert "get" in paths["/api/v1/tasks/{task_id}/messages"]
    assert "post" in paths["/api/v1/ai/ask"]
    assert "post" in paths["/api/v1/ai/stream"]
    assert "get" in paths["/api/v1/subscription/usage"]

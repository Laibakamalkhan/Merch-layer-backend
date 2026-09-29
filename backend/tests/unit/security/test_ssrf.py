import pytest
from commerce_connector.core.exceptions import SecurityError
from commerce_connector.security.ssrf import assert_safe_public_url
def test_localhost_blocked():
    with pytest.raises(SecurityError):
        assert_safe_public_url("http://127.0.0.1:8000")

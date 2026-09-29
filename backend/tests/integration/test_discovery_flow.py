from commerce_connector.discovery.platform_detector import detect_platform
def test_shopify_fingerprint():
    platform,confidence=detect_platform("https://store.myshopify.com")
    assert platform=="shopify" and confidence==1.0

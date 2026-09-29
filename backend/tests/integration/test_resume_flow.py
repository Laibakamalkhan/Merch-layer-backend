from commerce_connector.runtime.checkpoint import CheckpointStore
def test_checkpoint():
    store=CheckpointStore(); store.save("con","orders",{"cursor":"abc"})
    assert store.get("con","orders")=={"cursor":"abc"}

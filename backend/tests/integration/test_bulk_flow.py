import pytest
from commerce_connector.bulk.poll import poll_until_ready
@pytest.mark.asyncio
async def test_poll():
    calls={"n":0}
    async def check():
        calls["n"]+=1
        return {"ready":calls["n"]>=2}
    result=await poll_until_ready(check,interval_seconds=0.001,max_attempts=3)
    assert result["ready"]

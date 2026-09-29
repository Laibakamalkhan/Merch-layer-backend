import random, time
from email.utils import parsedate_to_datetime
def retry_delay(response, attempt_index, base_delay, max_delay, respect_retry_after=True):
    if response is not None and respect_retry_after:
        value = response.headers.get("Retry-After")
        if value:
            try: return min(max_delay, max(0.0,float(value)))
            except ValueError:
                try:
                    dt = parsedate_to_datetime(value)
                    return min(max_delay, max(0.0, dt.timestamp()-time.time()))
                except Exception: pass
    return min(max_delay, base_delay*(2**attempt_index)+random.uniform(0,min(0.5,base_delay)))

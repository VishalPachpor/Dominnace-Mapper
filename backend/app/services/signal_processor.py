import json
from app.utils.redis_client import redis_client

def get_next_signal():

    signal = redis_client.rpop("signals")

    if signal:
        return json.loads(signal)

    return None

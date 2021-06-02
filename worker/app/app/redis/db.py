import aioredis
import os

HOST = os.environ["REDIS_HOST"]

redis = aioredis.from_url(f"redis://{HOST}", encoding="utf-8", decode_responses=True)

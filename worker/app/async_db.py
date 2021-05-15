import aioredis

redis = aioredis.from_url("redis://127.0.0.1", encoding="utf-8", decode_responses=True)
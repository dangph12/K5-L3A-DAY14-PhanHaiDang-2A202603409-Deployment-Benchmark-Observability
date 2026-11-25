"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""


import hashlib
import math
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


SLIDING_WINDOW = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.max(1, math.ceil(tonumber(oldest[2]) + 60 - now))
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('EXPIRE', KEYS[1], 60)
return 0
"""


def check_rate_limit(key: str) -> None:
    # TODO: gợi ý dùng Redis sorted set: ZREMRANGEBYSCORE → ZCARD → ZADD → EXPIRE
    digest = hashlib.sha256(key.encode()).hexdigest()
    redis_key = f"agent:{settings.environment}:rate:{digest}"
    retry_after = int(r.eval(SLIDING_WINDOW, 1, redis_key, settings.rate_limit_per_minute, uuid.uuid4().hex))
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )

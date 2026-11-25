"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


@dataclass(frozen=True)
class Reservation:
    key: str
    amount: float


RESERVE_BUDGET = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local estimate = tonumber(ARGV[1])
local budget = tonumber(ARGV[2])
if current >= budget or current + estimate > budget then return 0 end
redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
redis.call('EXPIREAT', KEYS[1], ARGV[3])
return 1
"""

RECONCILE_COST = """
redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], 172800)
return 1
"""


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens / 1000 * PRICE_INPUT_PER_1K + output_tokens / 1000 * PRICE_OUTPUT_PER_1K


def check_budget(estimated_cost: float = 0.0) -> Reservation:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    key = f"agent:{settings.environment}:budget:{now:%Y-%m-%d}"
    accepted = r.eval(RESERVE_BUDGET, 1, key, estimated_cost, settings.daily_budget_usd, int(tomorrow.timestamp()) + 86400)
    if not accepted:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    return Reservation(key, estimated_cost)


def record_cost(input_tokens: int, output_tokens: int, reservation: Reservation | None = None) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = estimate_cost(input_tokens, output_tokens)
    if reservation is None:
        now = datetime.now(timezone.utc)
        reservation = Reservation(f"agent:{settings.environment}:budget:{now:%Y-%m-%d}", 0.0)
    r.eval(RECONCILE_COST, 1, reservation.key, cost - reservation.amount)
    return cost

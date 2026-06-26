"""Generic per-(module:action) circuit breaker — DB-backed, cross-worker.

State persisted in ``framework_circuit_breaker_states`` table so that
``--workers 3`` deployments share a single consistent view.

States: CLOSED → OPEN (on N consecutive failures) → HALF_OPEN (after recovery_timeout) → CLOSED or OPEN
"""

import time
import logging
from typing import Literal

from sqlalchemy import text

from app.core.exceptions import AppException
from app.database import AsyncSessionLocal

logger = logging.getLogger("v2.circuit_breaker")

CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

    async def _ensure_row(self):
        """Idempotent insert — first write sets the params."""
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text("SELECT state FROM framework_circuit_breaker_states WHERE key = :key"),
                {"key": self.name},
            )
            if r.fetchone():
                return
            await db.execute(
                text("""
                    INSERT INTO framework_circuit_breaker_states
                        (key, state, failure_count, failure_threshold, recovery_timeout)
                    VALUES (:key, 'CLOSED', 0, :ft, :rt)
                    ON CONFLICT (key) DO NOTHING
                """),
                {"key": self.name, "ft": self.failure_threshold, "rt": self.recovery_timeout},
            )
            await db.commit()

    @property
    async def state(self) -> CircuitState:
        """Read current state from DB."""
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text("SELECT state FROM framework_circuit_breaker_states WHERE key = :key"),
                {"key": self.name},
            )
            row = r.fetchone()
            return row[0] if row else "CLOSED"

    async def call(self, fn, *args, **kwargs):
        await self._ensure_row()

        # Phase 1: pre-call check with row lock
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text("""
                    SELECT state,
                           EXTRACT(EPOCH FROM last_failure_time) AS last_failure_epoch,
                           failure_threshold,
                           recovery_timeout
                    FROM framework_circuit_breaker_states
                    WHERE key = :key FOR UPDATE
                """),
                {"key": self.name},
            )
            row = r.fetchone()
            if not row:
                state = "CLOSED"
            else:
                state = row[0]
                last_failure_epoch = row[1] or 0.0
            if state == "OPEN":
                if time.time() - float(last_failure_epoch) >= self.recovery_timeout:
                        await db.execute(
                            text("""
                                UPDATE framework_circuit_breaker_states
                                SET state = 'HALF_OPEN', updated_at = NOW()
                                WHERE key = :key
                            """),
                            {"key": self.name},
                        )
                        await db.commit()
                        state = "HALF_OPEN"
                        logger.info("Circuit breaker '%s' → HALF_OPEN (recovery timeout elapsed)", self.name)

            if state == "OPEN":
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN — request fast-rejected"
                )

        # Phase 2: execute the call
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            await self._record_failure()
            raise
        else:
            await self._record_success()
            return result

    async def _record_failure(self):
        """Atomic increment-and-open.  Only transitions from CLOSED/HALF_OPEN to OPEN."""
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                text("""
                    UPDATE framework_circuit_breaker_states
                    SET failure_count = failure_count + 1,
                        last_failure_time = NOW(),
                        updated_at = NOW()
                    WHERE key = :key
                    RETURNING failure_count, failure_threshold
                """),
                {"key": self.name},
            )
            row = r.fetchone()
            if row:
                cnt, threshold = row
                if cnt >= threshold:
                    await db.execute(
                        text("""
                            UPDATE framework_circuit_breaker_states
                            SET state = 'OPEN', updated_at = NOW()
                            WHERE key = :key AND state IN ('CLOSED', 'HALF_OPEN')
                        """),
                        {"key": self.name},
                    )
                    logger.warning(
                        "Circuit breaker '%s' → OPEN (%d consecutive failures)",
                        self.name, cnt,
                    )
            await db.commit()

    async def _record_success(self):
        """Reset failure count + close if was HALF_OPEN."""
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("""
                    UPDATE framework_circuit_breaker_states
                    SET failure_count = 0,
                        state = CASE WHEN state = 'HALF_OPEN' THEN 'CLOSED' ELSE state END,
                        updated_at = NOW()
                    WHERE key = :key
                """),
                {"key": self.name},
            )
            await db.commit()


class CircuitBreakerOpenError(AppException):
    def __init__(self, message: str = "Circuit breaker is OPEN"):
        super().__init__(message, code="CIRCUIT_OPEN", status_code=503)


# Global registry (process-local cache — state lives in DB)
_breakers: dict[str, CircuitBreaker] = {}


async def get_circuit_breaker(key: str, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> CircuitBreaker:
    """Get-or-create a circuit breaker for *key* (``module:action``).

    The instance is cached per-process; the actual state is in the DB,
    so ``--workers 3`` all see the same truth.
    """
    if key not in _breakers:
        _breakers[key] = CircuitBreaker(
            name=key,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    return _breakers[key]

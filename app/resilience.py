"""
Resilience and fallback mechanisms for Komek Damu Bot.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Circuit breaker states
CIRCUIT_CLOSED = "closed"
CIRCUIT_OPEN = "open"
CIRCUIT_HALF_OPEN = "half_open"

# Circuit breaker storage
_circuit_states: dict = {}
_failure_counts: dict = {}
_last_failure_time: dict = {}

# Config
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_TIMEOUT_SECONDS = 30
CIRCUIT_RECOVERY_TIMEOUT = 60


def circuit_breaker(service_name: str):
    """Decorator for circuit breaker pattern."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check circuit state
            state = _circuit_states.get(service_name, CIRCUIT_CLOSED)
            
            if state == CIRCUIT_OPEN:
                # Check if we should try to recover
                last_failure = _last_failure_time.get(service_name, 0)
                if asyncio.get_event_loop().time() - last_failure > CIRCUIT_RECOVERY_TIMEOUT:
                    _circuit_states[service_name] = CIRCUIT_HALF_OPEN
                    logger.info(f"Circuit breaker for {service_name} entering half-open state")
                else:
                    logger.warning(f"Circuit breaker for {service_name} is OPEN, skipping request")
                    raise Exception(f"Service {service_name} temporarily unavailable")
            
            try:
                # Try to execute
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=CIRCUIT_TIMEOUT_SECONDS
                )
                
                # Success - reset circuit
                if state == CIRCUIT_HALF_OPEN:
                    _circuit_states[service_name] = CIRCUIT_CLOSED
                    logger.info(f"Circuit breaker for {service_name} closed")
                _failure_counts[service_name] = 0
                
                return result
                
            except Exception as e:
                # Failure - increment counter
                _failure_counts[service_name] = _failure_counts.get(service_name, 0) + 1
                _last_failure_time[service_name] = asyncio.get_event_loop().time()
                
                if _failure_counts[service_name] >= CIRCUIT_FAILURE_THRESHOLD:
                    _circuit_states[service_name] = CIRCUIT_OPEN
                    logger.error(f"Circuit breaker for {service_name} opened after {CIRCUIT_FAILURE_THRESHOLD} failures")
                
                raise
        
        return wrapper
    return decorator


# Fallback responses
FALLBACK_RESPONSES_RU = {
    "error": "Извините, произошла ошибка. Попробуйте ещё раз или напишите /start",
    "timeout": "Извините, ответ занял слишком много времени. Попробуйте ещё раз.",
    "ai_unavailable": "Извините, AI временно недоступен. Менеджер поможет вам:\n📞 +7 (XXX) XXX-XX-XX",
}

FALLBACK_RESPONSES_KK = {
    "error": "Кешіріңіз, қате орын алды. Қайта көріңіз немесе /start жазыңыз",
    "timeout": "Кешіріңіз, жауап уақытты көп алды. Қайта көріңіз.",
    "ai_unavailable": "Кешіріңіз, AI уақытша қолжетімсіз. Менеджер көмектеседі:\n📞 +7 (XXX) XXX-XX-XX",
}


def get_fallback_response(error_type: str, lang: str = "ru") -> str:
    """Get fallback response for error."""
    responses = FALLBACK_RESPONSES_RU if lang == "ru" else FALLBACK_RESPONSES_KK
    return responses.get(error_type, responses["error"])


async def with_fallback(
    func: Callable,
    fallback_value: Any,
    max_retries: int = 2,
    delay: float = 1.0
) -> Any:
    """Execute function with retry and fallback."""
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(delay * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"All attempts failed, returning fallback")
                return fallback_value

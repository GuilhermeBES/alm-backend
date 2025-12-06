"""
Serviço de rate limiting para APIs externas.
"""

import os
import time
from collections import deque
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

RATE_LIMIT_CALLS = int(os.getenv("BRAPI_RATE_LIMIT_CALLS", "5"))
RATE_LIMIT_PERIOD = int(os.getenv("BRAPI_RATE_LIMIT_PERIOD", "60"))


class RateLimiter:
    """
    Rate limiter baseado em sliding window.
    """

    def __init__(self, max_calls: int = RATE_LIMIT_CALLS, period: int = RATE_LIMIT_PERIOD):
        """
        Args:
            max_calls: Número máximo de chamadas permitidas
            period: Período em segundos
        """
        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()

    def is_allowed(self) -> bool:
        """
        Verifica se uma nova chamada é permitida.

        Returns:
            True se permitido, False caso contrário
        """
        current_time = time.time()

        # Remove chamadas antigas fora do período
        while self._calls and self._calls[0] < current_time - self.period:
            self._calls.popleft()

        # Verifica se atingiu o limite
        if len(self._calls) >= self.max_calls:
            return False

        return True

    def record_call(self) -> None:
        """Registra uma nova chamada."""
        self._calls.append(time.time())

    def time_until_next_call(self) -> Optional[float]:
        """
        Retorna o tempo em segundos até a próxima chamada ser permitida.

        Returns:
            Tempo em segundos ou None se já permitido
        """
        if self.is_allowed():
            return None

        if not self._calls:
            return None

        # Tempo até a chamada mais antiga sair da janela
        oldest_call = self._calls[0]
        current_time = time.time()
        time_until_allowed = (oldest_call + self.period) - current_time

        return max(0, time_until_allowed)

    def reset(self) -> None:
        """Reseta o rate limiter."""
        self._calls.clear()


# Instância global para brapi.dev
brapi_rate_limiter = RateLimiter(max_calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)

"""
Serviço de cache em memória com TTL.
"""

import os
import time
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))


class CacheService:
    """Serviço de cache em memória com TTL."""

    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Recupera um valor do cache.

        Args:
            key: Chave do cache

        Returns:
            Valor armazenado ou None se expirado/não existir
        """
        if key not in self._cache:
            return None

        value, expiration = self._cache[key]

        # Verifica se expirou
        if time.time() > expiration:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Armazena um valor no cache.

        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl: Tempo de vida em segundos (padrão: CACHE_TTL_SECONDS)
        """
        if ttl is None:
            ttl = CACHE_TTL_SECONDS

        expiration = time.time() + ttl
        self._cache[key] = (value, expiration)

    def delete(self, key: str) -> None:
        """
        Remove um valor do cache.

        Args:
            key: Chave do cache
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()

    def cleanup_expired(self) -> int:
        """
        Remove entradas expiradas do cache.

        Returns:
            Número de entradas removidas
        """
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiration) in self._cache.items()
            if current_time > expiration
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)


# Instância global do serviço de cache
cache_service = CacheService()

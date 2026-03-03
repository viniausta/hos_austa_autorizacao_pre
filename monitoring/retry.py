"""Decorator de retry com backoff exponencial para operações falíveis no RPA.

Uso:
    from monitoring.retry import retry
    from core.exceptions import LoginFalhouError

    @retry(max_tentativas=3, espera=2.0, excecoes=(LoginFalhouError,))
    def realizar_login(...):
        ...
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Callable, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def retry(
    max_tentativas: int = 3,
    espera: float = 2.0,
    excecoes: Tuple[Type[Exception], ...] = (Exception,),
    backoff: float = 1.5,
) -> Callable[[F], F]:
    """Reexecuta a função decorada em caso de falha com espera crescente.

    Args:
        max_tentativas: Número máximo de execuções (padrão: 3).
        espera: Tempo de espera inicial em segundos (padrão: 2.0).
        excecoes: Tupla de exceções que disparam nova tentativa (padrão: Exception).
        backoff: Multiplicador aplicado ao tempo de espera a cada tentativa (padrão: 1.5).
                 Ex: espera=2, backoff=1.5 → tentativas em 2s, 3s, 4.5s...
    """

    def decorador(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            espera_atual = espera
            for tentativa in range(1, max_tentativas + 1):
                try:
                    return func(*args, **kwargs)
                except excecoes as e:
                    if tentativa == max_tentativas:
                        logger.error(
                            "[retry] Todas as %d tentativas esgotadas para '%s': %s",
                            max_tentativas,
                            func.__name__,
                            e,
                        )
                        raise
                    logger.warning(
                        "[retry] Tentativa %d/%d falhou em '%s': %s — aguardando %.1fs...",
                        tentativa,
                        max_tentativas,
                        func.__name__,
                        e,
                        espera_atual,
                    )
                    time.sleep(espera_atual)
                    espera_atual *= backoff

        return wrapper  # type: ignore[return-value]

    return decorador

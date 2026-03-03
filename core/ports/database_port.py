"""Porta de banco de dados — abstração para a camada de domínio.

Qualquer implementação de banco de dados (Oracle, PostgreSQL, mock para testes)
deve satisfazer este Protocol para ser injetada no sistema.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class DatabasePort(Protocol):
    """Contrato de acesso ao banco de dados."""

    def execute_query(
        self, sql: str, params: Optional[Tuple] = None
    ) -> List[Dict[str, Any]]:
        """Executa uma consulta SQL e retorna lista de dicionários."""
        ...

    def execute_scalar(
        self, sql: str, params: Optional[Tuple] = None
    ) -> Any:
        """Executa uma consulta e retorna o primeiro valor da primeira linha."""
        ...

    def execute_non_query(
        self, sql: str, params: Optional[Tuple] = None
    ) -> None:
        """Executa um comando DML (INSERT, UPDATE, DELETE) sem retorno."""
        ...

    def call_procedure(self, name: str, params: Dict[str, Any]) -> None:
        """Executa uma stored procedure sem parâmetros de saída."""
        ...

    def call_procedure_with_output(
        self,
        name: str,
        params: Dict[str, Any],
        output_params: Dict[str, str],
    ) -> Dict[str, Any]:
        """Executa uma procedure com parâmetros OUT e retorna seus valores.

        Args:
            name: Nome completo da procedure (ex: "SCHEMA.PROCEDURE").
            params: Parâmetros de entrada {nome: valor}.
            output_params: Parâmetros de saída {nome: tipo_oracle}.
                           Tipos suportados: "NUMBER", "VARCHAR", "DATE".

        Returns:
            Dicionário {nome_param: valor_retornado}.
        """
        ...

    def close(self) -> None:
        """Fecha a conexão com o banco de dados."""
        ...

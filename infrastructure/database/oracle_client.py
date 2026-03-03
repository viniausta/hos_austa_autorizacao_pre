"""Cliente Oracle — implementação concreta de DatabasePort.

Gerencia conexão com o banco Oracle usando oracledb, com suporte automático
ao modo thin (sem Instant Client) e fallback para thick (com Instant Client).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.exceptions import BancoDadosError

logger = logging.getLogger(__name__)

try:
    import oracledb
except ImportError as exc:
    raise ImportError(
        "oracledb não está instalado. Execute: pip install oracledb"
    ) from exc

# Mapeamento de nomes de tipos Oracle para constantes do driver
_ORACLE_TYPE_MAP: Dict[str, Any] = {
    "NUMBER": oracledb.NUMBER,
    "VARCHAR": oracledb.DB_TYPE_VARCHAR,
    "DATE": oracledb.DB_TYPE_DATE,
}


class OracleClient:
    """Cliente Oracle que implementa DatabasePort.

    Tenta conexão em modo thin primeiro; caso o banco exija Instant Client
    (erros DPY-2021 ou DPY-3015), inicializa automaticamente via
    ORACLE_INSTANT_CLIENT_DIR ou pastas padrão na raiz do projeto.
    """

    def __init__(self, config: Any) -> None:
        """
        Args:
            config: objeto Settings com atributos db_host, db_port, db_service,
                    db_user, db_password.
        """
        dsn = oracledb.makedsn(
            config.db_host,
            int(config.db_port or 1521),
            service_name=config.db_service,
        )
        self.conn = self._conectar(dsn, config.db_user, config.db_password)
        logger.info(
            "Conectado ao Oracle em %s:%s/%s",
            config.db_host,
            config.db_port,
            config.db_service,
        )

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------

    def _conectar(self, dsn: str, user: str, password: str) -> Any:
        """Tenta conexão thin; faz fallback para thick se necessário."""
        try:
            return oracledb.connect(user=user, password=password, dsn=dsn)
        except Exception as e:
            msg = str(e)
            _requer_thick = (
                "init_oracle_client() must be called first" in msg
                or "DPY-2021" in msg
                or "DPY-3015" in msg
                or "password verifier" in msg
            )
            if not _requer_thick:
                raise BancoDadosError(f"Falha ao conectar ao Oracle: {e}") from e

            lib_dir = self._localizar_instant_client()
            if lib_dir:
                try:
                    oracledb.init_oracle_client(lib_dir=lib_dir)
                    logger.info("Oracle Instant Client inicializado em: %s", lib_dir)
                    return oracledb.connect(user=user, password=password, dsn=dsn)
                except Exception as e2:
                    raise BancoDadosError(
                        f"Conexão falhou mesmo após init_oracle_client: {e2}"
                    ) from e2
            raise BancoDadosError(
                "Oracle Instant Client requerido, mas não encontrado. "
                "Configure ORACLE_INSTANT_CLIENT_DIR."
            ) from e

    @staticmethod
    def _localizar_instant_client() -> Optional[str]:
        """Busca o Instant Client via env var ou caminhos padrão do projeto."""
        lib_dir = os.environ.get("ORACLE_INSTANT_CLIENT_DIR")
        if lib_dir:
            return lib_dir

        project_root = Path(__file__).resolve().parent.parent.parent
        candidatos = [
            project_root / "instantclient",
            project_root / "instantclient_23_9",
            project_root / "instantclient_19_8",
        ]
        for caminho in candidatos:
            if caminho.exists():
                return str(caminho)
        return None

    # ------------------------------------------------------------------
    # DatabasePort — implementação
    # ------------------------------------------------------------------

    def execute_query(
        self, sql: str, params: Optional[Tuple] = None
    ) -> List[Dict[str, Any]]:
        """Executa uma consulta SQL e retorna lista de dicionários."""
        logger.debug("execute_query: %s | params=%s", sql[:120], params)
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params) if params else cur.execute(sql)
            cols = [c[0].lower() for c in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
            return rows
        except Exception as e:
            raise BancoDadosError(f"Erro em execute_query: {e}") from e

    def execute_scalar(
        self, sql: str, params: Optional[Tuple] = None
    ) -> Any:
        """Executa uma consulta e retorna o primeiro valor da primeira linha."""
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params) if params else cur.execute(sql)
            row = cur.fetchone()
            cur.close()
            return row[0] if row else None
        except Exception as e:
            raise BancoDadosError(f"Erro em execute_scalar: {e}") from e

    def execute_non_query(
        self, sql: str, params: Optional[Tuple] = None
    ) -> None:
        """Executa um DML (INSERT/UPDATE/DELETE) com commit automático."""
        logger.debug("execute_non_query: %s | params=%s", sql[:120], params)
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params) if params else cur.execute(sql)
            self.conn.commit()
            cur.close()
        except Exception as e:
            raise BancoDadosError(f"Erro em execute_non_query: {e}") from e

    def call_procedure(self, name: str, params: Dict[str, Any]) -> None:
        """Executa uma stored procedure sem parâmetros OUT."""
        logger.debug("call_procedure: %s | params=%s", name, list(params.keys()))
        try:
            cur = self.conn.cursor()
            cur.callproc(name, list(params.values()))
            self.conn.commit()
            cur.close()
        except Exception as e:
            raise BancoDadosError(f"Erro ao chamar procedure '{name}': {e}") from e

    def call_procedure_with_output(
        self,
        name: str,
        params: Dict[str, Any],
        output_params: Dict[str, str],
    ) -> Dict[str, Any]:
        """Executa uma procedure com parâmetros OUT e retorna seus valores.

        Args:
            name: Nome da procedure (ex: "SCHEMA.PROC").
            params: Parâmetros de entrada em ordem da assinatura da procedure.
            output_params: {nome_param: tipo} — tipos: "NUMBER", "VARCHAR", "DATE".

        Returns:
            Dicionário {nome_param: valor_retornado} para cada parâmetro OUT.
        """
        logger.debug(
            "call_procedure_with_output: %s | inputs=%s | outputs=%s",
            name,
            list(params.keys()),
            list(output_params.keys()),
        )
        try:
            cur = self.conn.cursor()
            all_params = dict(params)
            out_vars: Dict[str, Any] = {}

            for param_name, type_str in output_params.items():
                oracle_type = _ORACLE_TYPE_MAP.get(type_str.upper())
                if oracle_type is None:
                    raise BancoDadosError(
                        f"Tipo Oracle desconhecido '{type_str}' para parâmetro '{param_name}'. "
                        f"Use: {list(_ORACLE_TYPE_MAP.keys())}"
                    )
                var = cur.var(oracle_type)
                all_params[param_name] = var
                out_vars[param_name] = var

            cur.callproc(name, list(all_params.values()))
            self.conn.commit()
            cur.close()

            return {k: v.getvalue() for k, v in out_vars.items()}
        except BancoDadosError:
            raise
        except Exception as e:
            raise BancoDadosError(
                f"Erro ao chamar procedure com output '{name}': {e}"
            ) from e

    def close(self) -> None:
        """Fecha a conexão com o banco de dados."""
        try:
            self.conn.close()
            logger.info("Conexão Oracle fechada.")
        except Exception as e:
            logger.warning("Erro ao fechar conexão Oracle: %s", e)

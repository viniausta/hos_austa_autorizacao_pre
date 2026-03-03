"""Serviço de controle de execução do robô RPA.

Responsável por:
- Registrar o início de cada execução no banco (PR_CRIAR_CONTROLE_EXECUCAO)
- Persistir logs de execução (PR_REGISTRAR_LOG)
- Registrar o encerramento (PR_FINALIZAR_EXECUCAO)
- Obter parâmetros configuráveis (RPA_PARAMETRO_OBTER)
"""
from __future__ import annotations

import logging
from typing import Optional

from core.ports.database_port import DatabasePort

logger = logging.getLogger(__name__)


class ControleExecucaoService:
    """Gerencia o ciclo de vida da execução do robô no banco de dados."""

    def __init__(
        self,
        db: DatabasePort,
        id_unidade: int,
        id_projeto: int,
        dev_mode: bool,
    ) -> None:
        self._db = db
        self._id_unidade = id_unidade
        self._id_projeto = id_projeto
        self._dev_mode = dev_mode
        self.id_execucao: Optional[int] = None

    # ------------------------------------------------------------------
    # Ciclo de vida da execução
    # ------------------------------------------------------------------

    def criar_execucao(
        self,
        unidade: str,
        projeto: str,
        script: str,
        usuario: str,
    ) -> None:
        """Registra o início de uma nova execução e armazena o id_execucao.

        Args:
            unidade: Nome da unidade hospitalar.
            projeto: Nome do projeto RPA.
            script: Nome do script (RPA_SCRIPT_NAME).
            usuario: Usuário que disparou a execução.
        """
        try:
            resultado = self._db.call_procedure_with_output(
                "ROBO_RPA.PR_CRIAR_CONTROLE_EXECUCAO",
                params={
                    "P_UNIDADE": unidade,
                    "P_PROJETO": projeto,
                    "P_SCRIPT": script,
                    "P_ETAPA": "-",
                    "P_USUARIO": usuario,
                },
                output_params={"P_ID_EXECUCAO": "NUMBER"},
            )
            raw = resultado.get("P_ID_EXECUCAO")
            self.id_execucao = int(raw) if raw is not None else None
            logger.info("Controle de execução criado — id_execucao=%s", self.id_execucao)
        except Exception as e:
            logger.exception("Erro ao criar controle de execução: %s", e)

    def registrar_log(
        self,
        tipo_log: str,
        mensagem: str,
        registro_id: Optional[str] = None,
    ) -> None:
        """Registra uma linha de log no arquivo local E no banco de dados.

        O log local é sempre registrado. A gravação no banco é não-crítica:
        falhas são registradas como WARNING mas não interrompem o fluxo.

        Args:
            tipo_log: "INFO", "WARN" ou "ERROR".
            mensagem: Texto da mensagem.
            registro_id: Identificador do registro sendo processado (opcional).
        """
        nivel = tipo_log.upper()
        if "INFO" in nivel:
            logger.info(mensagem)
        elif "WARN" in nivel:
            logger.warning(mensagem)
        else:
            logger.error(mensagem)

        try:
            self._db.call_procedure(
                "ROBO_RPA.PR_REGISTRAR_LOG",
                {
                    "p_id_execucao": self.id_execucao or 0,
                    "p_tipo_log": tipo_log,
                    "p_registro_id": registro_id or "",
                    "p_mensagem": mensagem,
                },
            )
        except Exception as e:
            logger.warning("Falha ao gravar log no banco: %s", e)

    def finalizar_execucao(
        self,
        status: str = "Concluido",
        observacoes: str = "-",
    ) -> None:
        """Registra o encerramento formal da execução no banco."""
        try:
            self._db.call_procedure(
                "ROBO_RPA.PR_FINALIZAR_EXECUCAO",
                {
                    "P_ID_EXECUCAO": self.id_execucao or 0,
                    "P_STATUS": status,
                    "P_OBSERVACOES": observacoes,
                },
            )
            logger.info(
                "Execução finalizada no banco — status='%s' | id=%s",
                status,
                self.id_execucao,
            )
        except Exception as e:
            logger.debug(
                "PR_FINALIZAR_EXECUCAO indisponível: %s", e
            )

    # ------------------------------------------------------------------
    # Parâmetros configuráveis
    # ------------------------------------------------------------------

    def obter_parametro(
        self,
        chave: str,
        id_unidade: Optional[int] = None,
        id_projeto: Optional[int] = None,
        dev: Optional[bool] = None,
    ) -> Optional[str]:
        """Obtém um parâmetro de configuração do banco de dados.

        Args:
            chave: Chave do parâmetro (ex: "URL_UNIMED", "CONTINUAR_EXECUCAO").
            id_unidade: ID da unidade (usa config se None).
            id_projeto: ID do projeto (usa config se None).
            dev: Flag de ambiente dev (usa config se None).

        Returns:
            Valor do parâmetro como string, ou None se não encontrado/erro.
        """
        un = id_unidade if id_unidade is not None else self._id_unidade
        pr = id_projeto if id_projeto is not None else self._id_projeto
        dv = dev if dev is not None else self._dev_mode

        try:
            resultado = self._db.call_procedure_with_output(
                "ROBO_RPA.RPA_PARAMETRO_OBTER",
                params={
                    "P_ID_UNIDADE": un,
                    "P_ID_PROJETO": pr,
                    "P_CHAVE": chave,
                    "P_DEV": str(dv),
                },
                output_params={"P_VALOR": "VARCHAR"},
            )
            valor = resultado.get("P_VALOR")
            logger.debug("Parâmetro '%s' = '%s'", chave, valor)
            return valor
        except Exception as e:
            logger.exception("Erro ao obter parâmetro '%s': %s", chave, e)
            return None

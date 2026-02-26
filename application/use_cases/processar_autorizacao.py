"""Caso de uso: Processar solicitações de autorização de PA — Unimed.

Orquestra o fluxo completo:
1. Obtém credenciais e URL da Unimed via parâmetros do banco
2. Realiza login no portal (com retry automático)
3. Consulta autorizações pendentes em loop
4. Processa cada autorização individualmente com tratamento de falhas
5. Encerra quando CONTINUAR_EXECUCAO = False no banco
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

from application.services.controle_execucao_service import ControleExecucaoService
from config.settings import Settings
from core.entities.autorizacao import Autorizacao
from core.exceptions import SpsadtFalhouError, LoginFalhouError
from core.ports.spsadt_port import SpsadtPort
from core.ports.database_port import DatabasePort
from core.ports.login_port import LoginPort
from core.ports.notificador_port import NotificadorPort
from monitoring.retry import retry

logger = logging.getLogger(__name__)

# Status TASY gravado em ambos os casos de impedimento.
_NR_STATUS_IMPEDIMENTO = 167

# ---------------------------------------------------------------------------
# Query de busca — parâmetros dinâmicos evitam SQL injection e hardcodes
# ---------------------------------------------------------------------------
_SQL_AUTORIZACOES_PENDENTES = """
    SELECT *
FROM
    tasy.BPM_AUTORIZACOES_V bpm
WHERE
    ds_setor_origem = 'CM-Pronto Atendimento'
    AND ie_tipo_autorizacao IN (1, 6)
    AND cd_convenio IN (27)
    AND dt_entrada > TRUNC(SYSDATE)
    AND cd_estabelecimento = :1
    --AND ds_estagio = 'CM-Necessidade de Autorização - WS'
    and nr_atendimento = 308176
"""


class ProcessarAutorizacaoUseCase:
    """Caso de uso principal: processa autorizações de PA no portal Unimed."""

    def __init__(
        self,
        config: Settings,
        db: DatabasePort,
        login: LoginPort,
        autorizacao: SpsadtPort,
        controle: ControleExecucaoService,
        notificador: Optional[NotificadorPort] = None,
    ) -> None:
        self._config = config
        self._db = db
        self._login = login
        self._autorizacao = autorizacao
        self._controle = controle
        self._notificador = notificador

    # ------------------------------------------------------------------
    # Ponto de entrada do caso de uso
    # ------------------------------------------------------------------

    def executar(self) -> None:
        """Executa o loop principal de processamento de autorizações."""
        url = self._controle.obter_parametro("URL_UNIMED")
        usuario = self._config.usuario_tasy
        senha = self._config.senha_tasy

        if not all([url, usuario, senha]):
            raise ValueError(
                "Parâmetros URL_UNIMED, USUARIO_UNIMED ou SENHA_UNIMED não encontrados. "
                "Configure-os no banco de parâmetros RPA."
            )

        self._controle.registrar_log(
            "INFO", f"Início do robô — Id Execução: {self._controle.id_execucao}"
        )

        self._realizar_login(url, usuario, senha)

        while self._deve_continuar():
            autorizacoes = self._buscar_autorizacoes_pendentes()

            if not autorizacoes:
                logger.info("Nenhuma autorização pendente. Aguardando 5s...")
                time.sleep(5)
                continue

            logger.info(
                "%d autorização(ões) encontrada(s) para processar.", len(autorizacoes))
            self._controle.registrar_log(
                "INFO", f"{len(autorizacoes)} autorização(ões) encontrada(s)."
            )

            for autorizacao in autorizacoes:
                self._processar_item(autorizacao)

        self._controle.registrar_log(
            "INFO", "Loop encerrado — CONTINUAR_EXECUCAO=False.")

    # ------------------------------------------------------------------
    # Etapas internas
    # ------------------------------------------------------------------

    @retry(max_tentativas=3, espera=5.0, excecoes=(LoginFalhouError,))
    def _realizar_login(self, url: str, usuario: str, senha: str) -> None:
        """Realiza login com retry automático em caso de falha."""
        try:
            self._login.realizar_login(url, usuario, senha)
            self._controle.registrar_log(
                "INFO", "Login realizado com sucesso.")
        except LoginFalhouError as e:
            self._controle.registrar_log("ERROR", f"Falha no login: {e}")
            if self._notificador:
                self._notificador.notificar_erro(
                    "Falha no login do robô de autorizações PA",
                    detalhes=str(e),
                )
            raise

    def _deve_continuar(self) -> bool:
        """Consulta o banco para saber se o loop deve continuar."""
        raw = self._controle.obter_parametro("CONTINUAR_EXECUCAO")
        continuar = str(raw).strip().upper() in (
            "1", "TRUE", "S", "SIM", "YES")
        if not continuar:
            logger.info("CONTINUAR_EXECUCAO=%s — encerrando loop.", raw)
        return continuar

    def _buscar_autorizacoes_pendentes(self) -> List[Autorizacao]:
        """Consulta autorizações pendentes no banco de dados."""
        try:
            rows = self._db.execute_query(
                _SQL_AUTORIZACOES_PENDENTES,
                (self._config.cd_estabelecimento,),
            )
            return [Autorizacao.from_row(r) for r in rows]
        except Exception as e:
            logger.exception("Erro ao buscar autorizações: %s", e)
            self._controle.registrar_log(
                "ERROR", f"Erro ao buscar autorizações: {e}")
            return []

    def _processar_item(self, autorizacao: Autorizacao) -> None:
        """Processa uma autorização individual com tratamento isolado de falhas.

        Falhas em um item não interrompem o processamento dos demais.
        """
        logger.info(
            "Processando: NrAtend=%s | Convenio=%s | Tipo=%s | Seq=%s",
            autorizacao.nr_atendimento,
            autorizacao.cd_convenio,
            autorizacao.tipo_autorizacao,
            autorizacao.nr_sequencia,
        )
        try:
            self._autorizacao.processar(autorizacao)

            self._controle.registrar_log(
                "INFO",
                (
                    f"Autorização processada — NrAtend={autorizacao.nr_atendimento} "
                    f"| Convenio={autorizacao.cd_convenio} "
                    f"| Tipo={autorizacao.tipo_autorizacao}"
                ),
                str(autorizacao.nr_atendimento),
            )

        except SpsadtFalhouError as e:
            logger.error(
                "Falha na autorização NrAtend=%s: %s", autorizacao.nr_atendimento, e
            )
            self._controle.registrar_log(
                "ERROR",
                f"Falha na autorização NrAtend={autorizacao.nr_atendimento}: {e}",
                str(autorizacao.nr_atendimento),
            )
            self._atualizar_falha_banco(autorizacao, str(e))
            if self._notificador:
                self._notificador.notificar_erro(
                    f"Falha na autorização {autorizacao.nr_atendimento}",
                    detalhes={"erro": str(
                        e), "convenio": autorizacao.cd_convenio},
                )

        except Exception as e:
            logger.exception(
                "Erro ao processar NrAtend=%s: %s", autorizacao.nr_atendimento, e
            )
            self._controle.registrar_log(
                "ERROR",
                f"Erro ao processar NrAtend={autorizacao.nr_atendimento}: {e}",
                str(autorizacao.nr_atendimento),
            )
            if self._notificador:
                self._notificador.notificar_erro(
                    f"Erro ao processar autorização {autorizacao.nr_atendimento}",
                    detalhes={"erro": str(
                        e), "convenio": autorizacao.cd_convenio},
                )

    def _atualizar_falha_banco(self, autorizacao: Autorizacao, mensagem: str) -> None:
        """Registra o impedimento nos dois bancos após falha no SPSADT.

        1. Atualiza o estágio da autorização no TASY via procedure.
        2. Atualiza o status na base de controle do RPA.

        """
        try:
            self._db.call_procedure(
                "TASY.ATUALIZAR_AUTORIZACAO_CONVENIO",
                {
                    "NR_SEQUENCIA_P": autorizacao.nr_sequencia,
                    "NM_USUARIO_P": "automacaotasy",
                    "NR_SEQ_ESTAGIO_P": _NR_STATUS_IMPEDIMENTO,
                    "IE_CONTA_PARTICULAR_P": "N",
                    "IE_CONTA_CONVENIO_P": "N",
                    "IE_COMMIT_P": "S",
                },
            )
            logger.info(
                "TASY atualizado — NrSeq=%s | Status=%s",
                autorizacao.nr_sequencia,
                _NR_STATUS_IMPEDIMENTO,
            )
        except Exception as e:
            logger.error(
                "Erro ao chamar ATUALIZAR_AUTORIZACAO_CONVENIO — NrSeq=%s: %s",
                autorizacao.nr_sequencia, e,
            )

        try:
            self._db.execute_non_query(
                """
                UPDATE ROBO_RPA.HOS_AUTORIZACOES
                SET
                    STATUS       = 'IMPEDIMENTO',
                    MENSAGEM     = :1,
                    DT_EXECUCAO  = SYSTIMESTAMP,
                    CD_REQUISICAO = NULL
                WHERE NR_SEQUENCIA = :2
                """,
                (mensagem, autorizacao.nr_sequencia),
            )
            logger.info(
                "HOS_AUTORIZACOES atualizado — NrSeq=%s | STATUS=IMPEDIMENTO",
                autorizacao.nr_sequencia,
            )
        except Exception as e:
            logger.error(
                "Erro ao atualizar HOS_AUTORIZACOES — NrSeq=%s: %s",
                autorizacao.nr_sequencia, e,
            )

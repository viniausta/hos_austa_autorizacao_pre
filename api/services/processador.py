"""Processador de autorização em background para o modo API/FHIR.

Cada request dispara uma thread isolada que:
  1. Cria suas próprias conexões (DB + browser)
  2. Faz login no portal TASY (URL obtida do banco de parâmetros)
  3. Constrói a entidade Autorizacao a partir do payload FHIR recebido
  4. Processa a autorização via use case (sem consulta Oracle para entrada)
  5. Faz callback ao CIB Seven com o resultado
  6. Libera todos os recursos
"""
import logging
import os
from typing import Optional

from api.schemas import AutorizacaoFhirRequest
from api.services.cib_seven import enviar_callback
from application.services.controle_execucao_service import ControleExecucaoService
from application.use_cases.processar_autorizacao import ProcessarAutorizacaoUseCase
from config.settings import Settings
from core.entities.autorizacao import Autorizacao
from infrastructure.browser.page_objects.login_page import LoginPage
from infrastructure.browser.page_objects.spsadt_page import SpsadtPage
from infrastructure.browser.web_controller import WebController
from infrastructure.database.oracle_client import OracleClient

logger = logging.getLogger(__name__)


def processar_autorizacao(
    payload: AutorizacaoFhirRequest,
    config: Settings,
) -> None:
    """Executa em thread de background: cria recursos, processa e faz callback.

    Recebe todos os dados necessários via payload FHIR — não consulta Oracle
    para dados de entrada. Oracle é usado apenas para:
      - Verificação de duplicidade (ROBO_RPA.HOS_AUTORIZACOES)
      - Gravar resultado via procedures TASY
      - Parâmetros do portal (URL_UNIMED via ControleExecucaoService)
    """
    db: Optional[OracleClient] = None
    browser: Optional[WebController] = None
    resultado: dict = {
        "status_retorno_tasy": "FALHA",
        "mensagem": "",
        "cod_guia": "",
        "cod_requisicao": "",
    }

    nr_sequencia = payload.atendimento.nr_sequencia
    process_instance_id = payload.process_instance_id
    message_name = payload.message_name

    try:
        db = OracleClient(config)
        caminho_download = str(config.caminho_padrao / "download")

        controle = ControleExecucaoService(
            db=db,
            id_unidade=config.id_unidade,
            id_projeto=config.id_projeto,
            dev_mode=config.dev_mode,
        )
        controle.criar_execucao(
            unidade=config.unidade,
            projeto=config.projeto,
            script=config.rpa_script_name,
            usuario=config.username,
        )

        browser = WebController(
            remote_url=os.environ.get("SELENIUM_REMOTE_URL"),
            caminho_download=caminho_download,
        )
        login_page = LoginPage(browser)
        spsadt_page = SpsadtPage(
            browser,
            caminho_download=caminho_download,
            caminho_backup=config.caminho_backup_guia,
            dev_mode=config.dev_mode,
        )

        use_case = ProcessarAutorizacaoUseCase(
            config=config,
            db=db,
            login=login_page,
            autorizacao=spsadt_page,
            controle=controle,
        )

        # Login + carrega URL do portal do banco de parâmetros
        use_case.inicializar()

        # Constrói entidade a partir do payload FHIR (sem SELECT no Oracle)
        autorizacao = Autorizacao.from_fhir_payload(payload)

        resultado_processamento = use_case.processar_com_dados(autorizacao)
        if resultado_processamento:
            resultado = {
                "status_retorno_tasy": str(resultado_processamento.get("status_retorno_tasy", "")),
                "mensagem": resultado_processamento.get("mensagem", ""),
                "cod_guia": resultado_processamento.get("cod_guia", ""),
                "cod_requisicao": resultado_processamento.get("cod_requisicao", ""),
            }
        elif config.dev_mode:
            resultado = {
                "status_retorno_tasy": "IMPEDIMENTO",
                "mensagem": "DEV mode — execução de teste sem submissão real",
                "cod_guia": "",
                "cod_requisicao": "",
            }
        elif not resultado_processamento:
            resultado = {
                "status_retorno_tasy": "IMPEDIMENTO",
                "mensagem": "Autorização não processada (duplicata ou cancelada)",
                "cod_guia": "",
                "cod_requisicao": "",
            }

        controle.finalizar_execucao(status="Concluido")

    except Exception as e:
        logger.exception(
            "Erro ao processar NrSeq=%s | instance=%s: %s",
            nr_sequencia, process_instance_id, e,
        )
        resultado["mensagem"] = str(e)
        if db:
            try:
                ControleExecucaoService(db, 0, 0, False).registrar_log(
                    "ERROR", f"API/FHIR: erro NrSeq={nr_sequencia}: {e}"
                )
            except Exception:
                pass

    finally:
        if browser:
            try:
                browser.fechar_navegador()
            except Exception:
                pass
        if db:
            db.close()

    # Callback sempre executado, mesmo em caso de falha
    try:
        enviar_callback(
            engine_rest_url=config.maezo_engine_rest_url,
            message_name=message_name,
            process_instance_id=process_instance_id,
            resultado=resultado,
        )
    except Exception as e:
        logger.error(
            "Falha no callback CIB Seven — NrSeq=%s | instance=%s: %s",
            nr_sequencia, process_instance_id, e,
        )

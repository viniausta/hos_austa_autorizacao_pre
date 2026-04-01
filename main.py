"""Entry point — Automação de Autorizações de PA (Pronto Atendimento) — Hospital Austa. [ Convênio UNIMED ].

Responsabilidade única: compor e conectar as dependências, depois disparar o caso de uso.
Toda lógica de negócio está na camada application/.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from monitoring.logger_config import logger
from config.settings import Settings
from core.exceptions import RPAException
from infrastructure.database.oracle_client import OracleClient
from infrastructure.browser.web_controller import WebController
from infrastructure.browser.page_objects.spsadt_page import SpsadtPage
from infrastructure.browser.page_objects.login_page import LoginPage
from infrastructure.notifications.cliq_notificador import CliqNotificador
from application.services.controle_execucao_service import ControleExecucaoService
from application.use_cases.processar_autorizacao import ProcessarAutorizacaoUseCase


def _mapear_unidades_de_rede(config: "Settings") -> None:
    """Mapeia (ou remapeia) os compartilhamentos de rede necessários para a automação.

    Executado uma vez ao iniciar, garante que os paths de rede estejam acessíveis
    antes de qualquer operação de leitura/escrita de arquivos.
    """
    compartilhamentos = [
        r"\\10.100.0.110\tasyhospausta",
        r"\\172.20.255.13\tasyausta\anexo_opme",
    ]
    usuario = config.caminho_rede_anexo
    senha = config.senha_rede_anexo

    for caminho in compartilhamentos:
        try:
            subprocess.run(
                ["net", "use", caminho, "/delete", "/y"],
                capture_output=True,
                check=False,
            )
            resultado = subprocess.run(
                ["net", "use", caminho, f"/user:{usuario}", senha, "/persistent:yes"],
                capture_output=True,
                text=True,
                check=False,
            )
            if resultado.returncode == 0:
                logger.info("Unidade de rede mapeada: %s", caminho)
            else:
                logger.warning(
                    "Falha ao mapear '%s': %s",
                    caminho,
                    (resultado.stderr or resultado.stdout).strip(),
                )
        except Exception as e:
            logger.warning("Erro ao mapear unidade de rede '%s': %s", caminho, e)


def main() -> int:
    """Ponto de entrada principal.

    Returns:
        0 em sucesso, 1 em falha — compatível com sys.exit() e supervisores de processo.
    """
    config = Settings.from_env()
    logger.info(
        "Iniciando automação '%s' | Unidade: %s | Dev: %s",
        config.rpa_script_name,
        config.unidade,
        config.dev_mode,
    )

    # Mapeia unidades de rede antes de qualquer operação de arquivo
    _mapear_unidades_de_rede(config)

    # Prepara diretórios necessários
    config.caminho_padrao.mkdir(parents=True, exist_ok=True)
    (config.caminho_padrao / "Evidencia").mkdir(parents=True, exist_ok=True)
    caminho_download = config.caminho_padrao / "download"
    caminho_download.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # Notificador criado ANTES da infraestrutura — só depende das
    # credenciais Zoho, garantindo que falhas de DB/browser sejam
    # notificadas normalmente.
    # -----------------------------------------------------------------
    notificador = None
    if all([
        config.zoho_client_id,
        config.zoho_client_secret,
        config.zoho_refresh_token,
        config.cliq_canal_normal,
        config.cliq_canal_erro,
    ]):
        notificador = CliqNotificador(
            client_id=config.zoho_client_id,
            client_secret=config.zoho_client_secret,
            refresh_token=config.zoho_refresh_token,
            canal_normal=config.cliq_canal_normal,
            canal_erro=config.cliq_canal_erro,
            dev_mode=config.dev_mode,
        )
        logger.info("Notificador Cliq ativo (DEV=%s).", config.dev_mode)

    db: Optional[OracleClient] = None
    browser: Optional[WebController] = None
    controle: Optional[ControleExecucaoService] = None

    try:
        # -----------------------------------------------------------------
        # Infraestrutura
        # -----------------------------------------------------------------
        db = OracleClient(config)

        # Modo remoto (Docker) ativado quando SELENIUM_REMOTE_URL está configurada
        selenium_remote_url = os.environ.get("SELENIUM_REMOTE_URL")
        if selenium_remote_url:
            logger.info("Modo Docker: conectando ao Selenium em %s",
                        selenium_remote_url)
        browser = WebController(
            remote_url=selenium_remote_url,
            caminho_download=str(caminho_download),
        )

        # -----------------------------------------------------------------
        # Serviço de controle de execução
        # -----------------------------------------------------------------
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

        caso_de_uso = ProcessarAutorizacaoUseCase(
            config=config,
            db=db,
            login=LoginPage(browser),
            autorizacao=SpsadtPage(
                browser,
                caminho_download=str(caminho_download),
                caminho_backup=config.caminho_backup_guia,
                dev_mode=config.dev_mode,
            ),
            controle=controle,
            notificador=notificador,
        )
        caso_de_uso.executar()

        controle.registrar_log("INFO", "Automação concluída com sucesso.")
        controle.finalizar_execucao(status="Concluido")
        logger.info("Automação finalizada com sucesso.")
        return 0

    except RPAException as e:
        logger.error("Erro de domínio na automação: %s", e)
        if controle:
            try:
                controle.registrar_log("ERROR", f"Encerramento por erro de domínio: {e}")
                controle.finalizar_execucao(status="Erro", observacoes=str(e))
            except Exception:
                pass
        if notificador:
            notificador.notificar_erro(
                f"[{config.rpa_script_name}] Execução encerrada — erro de domínio",
                detalhes=str(e),
            )
        return 1

    except Exception as e:
        logger.exception("Erro inesperado — automação encerrada com falha.")
        if controle:
            try:
                controle.registrar_log("ERROR", f"Encerramento por erro inesperado: {e}")
                controle.finalizar_execucao(status="Erro", observacoes=str(e))
            except Exception:
                pass
        if notificador:
            notificador.notificar_erro(
                f"[{config.rpa_script_name}] Execução encerrada — erro inesperado",
                detalhes=str(e),
            )
        return 1

    finally:
        if db:
            db.close()
        if browser:
            try:
                browser.fechar_navegador()
            except Exception:
                logger.warning("Erro ao fechar o navegador no encerramento.")


if __name__ == "__main__":
    sys.exit(main())

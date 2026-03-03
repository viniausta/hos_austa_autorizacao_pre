"""Page Object Model — Tela de Login do sistema TASY/Unimed.

Encapsula todos os seletores e ações da tela de login, isolando os
detalhes de UI do restante da aplicação (Padrão POM).
"""
from __future__ import annotations

import logging

from core.exceptions import LoginFalhouError
from core.ports.browser_port import BrowserPort

logger = logging.getLogger(__name__)


class LoginPage:
    """Representa a tela de login do portal TASY.

    Todos os seletores e a sequência de interação ficam aqui.
    Se a UI mudar, apenas este arquivo precisa ser atualizado.
    """

    # Seletores da tela de login
    _SEL_USUARIO = ("id", "nmUsuario")
    _SEL_SENHA = ("id", "dsSenha")
    _SEL_PRESTADOR = ("id", "tipoUsuario")
    _SEL_BTN_ENTRAR = ("id", "btn_entrar")

    # Elemento que confirma login bem-sucedido
    _SEL_POS_LOGIN = ("xpath", '//font[text()="Requisição para autorização"]')

    def __init__(self, browser: BrowserPort) -> None:
        self._browser = browser

    def realizar_login(self, url: str, usuario: str, senha: str) -> None:
        """Navega até a URL e realiza login com as credenciais fornecidas.

        Usa `frame_do_elemento` para localizar automaticamente o iFrame correto
        antes de cada bloco de ações, restaurando o contexto ao documento principal
        ao final de cada bloco.

        Args:
            url: URL completa da página de login.
            usuario: Nome de usuário para autenticação.
            senha: Senha para autenticação.

        Raises:
            ElementoNaoEncontradoError: Se o campo de usuário ou o elemento
                                        pós-login não forem encontrados em nenhum frame.
            LoginFalhouError: Se o elemento de confirmação de login não aparecer.
        """
        logger.info("Navegando para a página de login: %s", url)
        self._browser.navegar(url)

        logger.debug("Localizando campo de usuário e preenchendo credenciais...")
        with self._browser.frame_do_elemento(*self._SEL_USUARIO, timeout=10):
            self._browser.selecionar_opcao(*self._SEL_PRESTADOR, "Prestador", timeout=5)
            self._browser.definir_valor(*self._SEL_USUARIO, usuario, timeout=5)
            self._browser.definir_valor(*self._SEL_SENHA, senha, timeout=5)
            self._browser.click_elemento(*self._SEL_BTN_ENTRAR, timeout=10)
        # frame_do_elemento restaura o contexto para o documento principal automaticamente

        # Verifica se o login foi bem-sucedido pela presença do elemento esperado
        with self._browser.frame_do_elemento(*self._SEL_POS_LOGIN, timeout=10):
            if not self._browser.verificar_existencia_elemento(*self._SEL_POS_LOGIN, timeout=10):
                raise LoginFalhouError(
                    "Elemento pós-login não encontrado. Verifique as credenciais ou a estrutura da página."
                )

        logger.info("Login realizado com sucesso.")

        # Fecha abas extras abertas pelo sistema, mantendo apenas o portal principal
        self._browser.fechar_abas_exceto("Portal da operadora", timeout=10)
        logger.info("Abas extras fechadas após login.")

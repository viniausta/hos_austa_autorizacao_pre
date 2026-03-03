"""Porta de navegador — abstração para a camada de domínio.

Qualquer implementação de browser (Selenium, Playwright, mock para testes)
deve satisfazer este Protocol para ser injetada no sistema.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class BrowserPort(Protocol):
    """Contrato de controle de navegador web."""

    def navegar(self, url: str) -> None:
        """Navega para a URL especificada."""
        ...

    def aguardar_elemento_visivel(
        self, seletor: str, valor: str, timeout: int = 10
    ) -> bool:
        """Aguarda elemento ficar visível. Retorna True se visível dentro do timeout."""
        ...

    def definir_valor(
        self, seletor: str, valor: str, texto: str, timeout: int = 10
    ) -> None:
        """Limpa e preenche um campo de input com o texto informado."""
        ...

    def click_elemento(
        self, seletor: str, valor: str, timeout: int = 10, js: bool = False
    ) -> bool:
        """Clica em um elemento. Retorna True se o clique foi realizado."""
        ...

    def selecionar_opcao(
        self,
        seletor: str,
        valor: str,
        texto_opcao: str,
        por: str = "texto",
        timeout: int = 10,
    ) -> None:
        """Seleciona uma opção de um <select> pelo texto visível ou pelo value.

        Args:
            por: "texto" (padrão) para texto visível, "value" para o atributo value.
        """
        ...

    def verificar_existencia_elemento(
        self, seletor: str, valor: str, timeout: int = 5
    ) -> bool:
        """Verifica se um elemento existe no DOM dentro do timeout."""
        ...

    def alternar_frame_com_elemento(
        self, seletor: str, valor: str, timeout: int = 5
    ) -> bool:
        """Busca recursivamente em iFrames e posiciona o driver no frame correto."""
        ...

    def frame_do_elemento(
        self, seletor: str, valor: str, timeout: int = 5
    ) -> AbstractContextManager[None]:
        """Context manager que localiza o iFrame do elemento e restaura o contexto ao sair.

        Uso:
            with browser.frame_do_elemento("id", "nmUsuario"):
                browser.definir_valor("id", "nmUsuario", "texto")
            # contexto volta ao documento principal automaticamente

        Raises:
            ElementoNaoEncontradoError: se o elemento não for encontrado em nenhum frame.
        """
        ...

    def sair_frame(self) -> None:
        """Retorna o contexto para o documento principal."""
        ...

    def obter_texto(self, seletor: str, valor: str, timeout: int = 10) -> str:
        """Retorna o texto visível do elemento (propriedade .text — para spans, divs, etc.)."""
        ...

    def obter_valor(self, seletor: str, valor: str, timeout: int = 10) -> str:
        """Retorna o atributo value do elemento (para inputs, selects e textareas)."""
        ...

    def obter_atributo(
        self, seletor: str, valor: str, atributo: str, timeout: int = 10
    ) -> Optional[str]:
        """Retorna o valor de um atributo HTML do elemento."""
        ...

    def enviar_tecla(
        self, seletor: str, valor: str, tecla: str, timeout: int = 10
    ) -> None:
        """Envia uma tecla especial a um elemento (ex: 'TAB', 'ENTER', 'ESCAPE')."""
        ...

    def tratar_alerta(
        self, aceitar: bool = True, timeout: int = 10
    ) -> Optional[str]:
        """Aceita ou descarta alerta JS e retorna seu texto. None se não houver alerta."""
        ...

    def fechar_aba(self) -> None:
        """Fecha a aba atual e volta para a anterior."""
        ...

    def fechar_abas_exceto(self, titulo_contem: str, timeout: int = 10) -> bool:
        """Fecha todas as abas abertas exceto a que contém o título especificado.

        Retorna True se a aba foi encontrada e as demais fechadas.
        Retorna False se nenhuma aba com o título for encontrada dentro do timeout.
        """
        ...

    def obter_titulo_aba(self) -> str:
        """Retorna o título da aba/janela atualmente ativa."""
        ...

    def fechar_navegador(self) -> None:
        """Encerra o navegador e libera recursos."""
        ...

    def captura_tela(self, caminho: str) -> None:
        """Salva uma captura de tela no caminho especificado."""
        ...

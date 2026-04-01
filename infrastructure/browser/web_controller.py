"""Controlador de navegador web via Selenium — implementação concreta de BrowserPort.

Suporta dois modos de operação:
  - Local:  instancia o ChromeDriver na própria máquina (desenvolvimento).
  - Remoto: conecta a um Selenium Standalone/Grid via Remote WebDriver (Docker/CI).
            Ativado quando remote_url é fornecido (ex: http://selenium:4444/wd/hub).
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from core.exceptions import ElementoNaoEncontradoError, NavegadorError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Importações opcionais — degradação graciosa se Selenium não instalado
# ---------------------------------------------------------------------------
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select, WebDriverWait
    from selenium.common.exceptions import (
        NoAlertPresentException,
        TimeoutException,
        WebDriverException,
        ElementNotInteractableException,
    )

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.firefox import GeckoDriverManager
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        _WDM_AVAILABLE = True
    except Exception:
        _WDM_AVAILABLE = False

    _SELENIUM_AVAILABLE = True

except Exception:
    _SELENIUM_AVAILABLE = False
    webdriver = None  # type: ignore[assignment]
    WebDriver = object  # type: ignore[assignment,misc]
    Options = object  # type: ignore[assignment]
    ChromeService = object  # type: ignore[assignment]
    WebDriverWait = object  # type: ignore[assignment]
    Select = object  # type: ignore[assignment]
    EC = object  # type: ignore[assignment]
    TimeoutException = Exception  # type: ignore[assignment,misc]
    NoAlertPresentException = Exception  # type: ignore[assignment,misc]
    WebDriverException = Exception  # type: ignore[assignment,misc]
    By = object  # type: ignore[assignment]
    ActionChains = object  # type: ignore[assignment]
    _WDM_AVAILABLE = False


# ---------------------------------------------------------------------------
# Placeholder quando Selenium não está disponível
# ---------------------------------------------------------------------------
if not _SELENIUM_AVAILABLE:
    class WebController:  # type: ignore[no-redef]
        """Placeholder: lança RuntimeError ao instanciar sem Selenium."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "Selenium não encontrado. Instale com: pip install selenium"
            )

else:
    class WebController:  # type: ignore[no-redef]
        """Wrapper do Selenium WebDriver — implementa BrowserPort.

        Modo local  → driver_path ou webdriver-manager resolvem o ChromeDriver.
        Modo remoto → remote_url aponta para Selenium Standalone/Grid
                      (ex: "http://selenium:4444/wd/hub" no Docker).
        """

        def __init__(
            self,
            driver_path: Optional[str] = None,
            browser: str = "chrome",
            remote_url: Optional[str] = None,
            caminho_download: Optional[str] = None,
        ) -> None:
            if remote_url:
                self.driver: Any = self._iniciar_browser_remoto(
                    remote_url, caminho_download)
            else:
                self.driver = self._iniciar_browser(
                    driver_path, browser, caminho_download)
            self.actions = ActionChains(self.driver)

        # ------------------------------------------------------------------
        # Inicialização — modo remoto (Docker / Selenium Standalone)
        # ------------------------------------------------------------------

        def _iniciar_browser_remoto(
            self, remote_url: str, caminho_download: Optional[str] = None
        ) -> Any:
            """Conecta ao Selenium Standalone ou Grid via Remote WebDriver.

            Flags obrigatórias para ambiente containerizado:
              --no-sandbox           → necessário para rodar como root no container
              --disable-dev-shm-usage → evita crash por /dev/shm limitado
            Headless removido: o container Selenium já usa Xvfb como display
            virtual, permitindo visualização via noVNC em localhost:7900.
            """
            options = Options()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-notifications")
            options.add_experimental_option(
                "excludeSwitches", ["enable-logging"])
            # enableVNC: permite visualizar a sessão no Selenoid-UI (ignorado pelo Selenium Grid)
            options.set_capability("selenoid:options", {"enableVNC": True, "enableVideo": False})
            if caminho_download:
                options.add_experimental_option("prefs", {
                    "download.default_directory": caminho_download,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "plugins.always_open_pdf_externally": True,
                })

            try:
                driver = webdriver.Remote(
                    command_executor=remote_url,
                    options=options,
                )
                logger.info("Navegador remoto conectado em: %s", remote_url)
                return driver
            except Exception as e:
                raise NavegadorError(
                    f"Falha ao conectar ao Selenium remoto em '{remote_url}': {e}"
                ) from e

        # ------------------------------------------------------------------
        # Inicialização do driver
        # ------------------------------------------------------------------

        def _iniciar_browser(
            self,
            driver_path: Optional[str],
            browser: str,
            caminho_download: Optional[str] = None,
        ) -> Any:
            """Cria e retorna a instância do WebDriver conforme o navegador."""
            project_root = Path(__file__).resolve().parent.parent.parent

            def _driver_local(names: list) -> Optional[str]:
                for name in names:
                    p = project_root / name
                    if p.exists():
                        return str(p)
                return None

            options = Options()
            options.add_argument("--start-maximized")
            options.add_experimental_option(
                "excludeSwitches", ["enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("disable-popup-blocking")
            options.add_argument("disable-notifications")
            options.add_argument("disable-gpu")
            if caminho_download:
                options.add_experimental_option("prefs", {
                    "download.default_directory": caminho_download,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "plugins.always_open_pdf_externally": True,
                })

            try:
                if browser == "chrome":
                    service = self._resolver_service_chrome(
                        driver_path, _driver_local, ChromeService
                    )
                    return webdriver.Chrome(service=service, options=options)

                elif browser == "firefox":
                    from selenium.webdriver.firefox.service import Service as FirefoxService
                    service = self._resolver_service_generico(
                        driver_path,
                        _driver_local,
                        FirefoxService,
                        ["geckodriver.exe", "geckodriver"],
                        GeckoDriverManager if _WDM_AVAILABLE else None,
                    )
                    return webdriver.Firefox(service=service)

                elif browser == "edge":
                    from selenium.webdriver.edge.service import Service as EdgeService
                    service = self._resolver_service_generico(
                        driver_path,
                        _driver_local,
                        EdgeService,
                        ["msedgedriver.exe", "msedgedriver"],
                        EdgeChromiumDriverManager if _WDM_AVAILABLE else None,
                    )
                    return webdriver.Edge(service=service)

                else:
                    raise NavegadorError(
                        f"Navegador não suportado: '{browser}'")

            except WebDriverException as e:
                logger.error("Erro ao iniciar navegador '%s': %s", browser, e)
                raise NavegadorError(f"Falha ao iniciar navegador: {e}") from e

        def _resolver_service_chrome(self, driver_path, finder, ServiceClass):
            if _WDM_AVAILABLE and not driver_path:
                try:
                    return ServiceClass(ChromeDriverManager().install())
                except Exception:
                    local = finder(["chromedriver.exe", "chromedriver"])
                    return ServiceClass(executable_path=local) if local else ServiceClass()
            if driver_path:
                return ServiceClass(executable_path=driver_path)
            local = finder(["chromedriver.exe", "chromedriver"])
            return ServiceClass(executable_path=local) if local else ServiceClass()

        def _resolver_service_generico(self, driver_path, finder, ServiceClass, names, ManagerClass):
            if ManagerClass and not driver_path:
                try:
                    return ServiceClass(ManagerClass().install())
                except Exception:
                    local = finder(names)
                    return ServiceClass(executable_path=local) if local else ServiceClass()
            if driver_path:
                return ServiceClass(executable_path=driver_path)
            local = finder(names)
            return ServiceClass(executable_path=local) if local else ServiceClass()

        # ------------------------------------------------------------------
        # Navegação
        # ------------------------------------------------------------------

        def navegar(self, url: str) -> None:
            """Navega para a URL especificada."""
            try:
                self.driver.get(url)
                logger.info("Navegou para: %s", url)
            except Exception as e:
                logger.exception("Erro ao navegar para %s: %s", url, e)
                raise

        def voltar_pagina(self) -> None:
            """Navega para a página anterior no histórico."""
            self.driver.back()

        def avancar_pagina(self) -> None:
            """Avança uma página no histórico."""
            self.driver.forward()

        def atualizar_pagina(self) -> None:
            """Recarrega a página atual."""
            self.driver.refresh()

        def obter_titulo_aba(self) -> str:
            """Retorna o título da aba/janela atualmente ativa."""
            return self.driver.title

        def fechar_navegador(self) -> None:
            """Encerra o navegador e libera recursos."""
            self.driver.quit()
            logger.info("Navegador encerrado.")

        # ------------------------------------------------------------------
        # Abas e janelas
        # ------------------------------------------------------------------

        def abrir_nova_aba(self, url: Optional[str] = None) -> None:
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            if url:
                self.navegar(url)

        def alternar_aba(self, indice: int) -> None:
            self.driver.switch_to.window(self.driver.window_handles[indice])

        def fechar_aba(self) -> None:
            self.driver.close()
            if self.driver.window_handles:
                self.driver.switch_to.window(self.driver.window_handles[-1])

        def localizar_ou_anexar_aba(
            self,
            titulo_contem: Optional[str] = None,
            url_contem: Optional[str] = None,
            timeout: int = 10,
        ) -> bool:
            """Procura aba por título ou URL. Retorna True se encontrada."""
            end_time = time.time() + timeout
            while time.time() < end_time:
                for handle in self.driver.window_handles:
                    self.driver.switch_to.window(handle)
                    if (titulo_contem and titulo_contem in self.driver.title) or (
                        url_contem and url_contem in self.driver.current_url
                    ):
                        return True
                time.sleep(0.5)
            return False

        def fechar_abas_exceto(self, titulo_contem: str, timeout: int = 10) -> bool:
            """Fecha todas as abas abertas exceto a que contém o título especificado.

            Aguarda até o timeout para localizar a aba desejada. Ao final,
            o driver fica posicionado na aba mantida.

            Args:
                titulo_contem: Substring do título da aba que deve ser mantida.
                timeout: Tempo máximo em segundos para localizar a aba desejada.

            Returns:
                True se a aba foi encontrada e as demais fechadas.
                False se nenhuma aba com o título for encontrada dentro do timeout.
            """
            aba_principal = None
            end_time = time.time() + timeout

            while time.time() < end_time:
                for handle in self.driver.window_handles:
                    self.driver.switch_to.window(handle)
                    if titulo_contem in self.driver.title:
                        aba_principal = handle
                        break
                if aba_principal:
                    break
                time.sleep(0.5)

            if not aba_principal:
                titulos = []
                for handle in self.driver.window_handles:
                    self.driver.switch_to.window(handle)
                    titulos.append(f"'{self.driver.title}'")
                logger.warning(
                    "Aba com título '%s' não encontrada. Abas abertas: [%s]",
                    titulo_contem,
                    ", ".join(titulos),
                )
                return False

            for handle in list(self.driver.window_handles):
                if handle != aba_principal:
                    self.driver.switch_to.window(handle)
                    titulo_fechado = self.driver.title
                    self.driver.close()
                    logger.debug("Aba fechada: '%s'", titulo_fechado)

            self.driver.switch_to.window(aba_principal)
            logger.info(
                "Abas extras fechadas. Aba ativa: '%s'", self.driver.title
            )
            return True

        # ------------------------------------------------------------------
        # Interação com elementos
        # ------------------------------------------------------------------

        def click_elemento(
            self, seletor: str, valor: str, timeout: int = 10, js: bool = False
        ) -> bool:
            """Clica no elemento. Retorna True se clicado com sucesso."""
            try:
                el = self._encontrar_elemento(seletor, valor, timeout)
                if js:
                    self.driver.execute_script("arguments[0].click();", el)
                else:
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", el)
                        el.click()
                    except ElementNotInteractableException:
                        logger.debug(
                            "ElementNotInteractable — usando JS click para %s='%s'",
                            seletor, valor,
                        )
                        self.driver.execute_script("arguments[0].click();", el)
                return True
            except ElementoNaoEncontradoError:
                return False

        def definir_valor(
            self, seletor: str, valor: str, texto: str, timeout: int = 5
        ) -> None:
            """Limpa o campo e preenche com o texto informado."""
            el = self._encontrar_elemento(seletor, valor, timeout)
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el)
                el.clear()
                el.send_keys(texto)
            except ElementNotInteractableException:
                logger.debug(
                    "ElementNotInteractable em definir_valor — usando JS para %s='%s'",
                    seletor, valor,
                )
                self.driver.execute_script(
                    "arguments[0].value = arguments[1];", el, texto)

        def obter_texto(self, seletor: str, valor: str, timeout: int = 10) -> str:
            """Retorna o texto visível do elemento (propriedade .text)."""
            return self._encontrar_elemento(seletor, valor, timeout).text

        def obter_valor(self, seletor: str, valor: str, timeout: int = 10) -> str:
            """Retorna o valor atual do input/select via propriedade DOM.

            Usa execute_script em vez de get_attribute("value") porque campos
            preenchidos por JavaScript têm a propriedade DOM atualizada, mas o
            atributo HTML pode permanecer vazio.
            """
            el = self._encontrar_elemento(seletor, valor, timeout)
            return self.driver.execute_script("return arguments[0].value;", el) or ""

        def obter_atributo(
            self, seletor: str, valor: str, atributo: str, timeout: int = 10
        ) -> Optional[str]:
            """Retorna o valor de um atributo HTML do elemento."""
            return self._encontrar_elemento(seletor, valor, timeout).get_attribute(atributo)

        def aguardar_elemento_visivel(
            self, seletor: str, valor: str, timeout: int = 10
        ) -> bool:
            """Aguarda elemento ficar visível. Retorna True se visível no timeout."""
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located(self._by(seletor, valor))
                )
                return True
            except TimeoutException:
                return False

        def verificar_existencia_elemento(
            self, seletor: str, valor: str, timeout: int = 5
        ) -> bool:
            """Verifica se um elemento existe no DOM. Retorna True se encontrado."""
            try:
                self._encontrar_elemento(seletor, valor, timeout)
                return True
            except ElementoNaoEncontradoError:
                return False

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
                seletor: Tipo do seletor ("id", "xpath", etc.).
                valor: Valor do seletor.
                texto_opcao: Texto visível ou value da opção a selecionar.
                por: Critério de seleção — "texto" (padrão) ou "value".
                timeout: Tempo máximo de espera pelo elemento.
            """
            el = self._encontrar_elemento(seletor, valor, timeout)
            select = Select(el)
            if por == "value":
                select.select_by_value(texto_opcao)
            else:
                select.select_by_visible_text(texto_opcao)

        def rolar_para_elemento(
            self, seletor: str, valor: str, timeout: int = 10
        ) -> None:
            """Rola a página até o elemento ficar visível na viewport."""
            el = self._encontrar_elemento(seletor, valor, timeout)
            self.driver.execute_script(
                "arguments[0].scrollIntoView(true);", el)

        def upload_arquivo(
            self, seletor: str, valor: str, caminho_arquivo: str, timeout: int = 10
        ) -> None:
            """Realiza upload via input[type=file]."""
            el = self._encontrar_elemento(seletor, valor, timeout)
            el.send_keys(caminho_arquivo)

        def enviar_tecla(
            self, seletor: str, valor: str, tecla: str, timeout: int = 10
        ) -> None:
            """Envia uma tecla especial a um elemento.

            Args:
                tecla: Nome da tecla em maiúsculo — "TAB", "ENTER", "ESCAPE",
                       "BACKSPACE", "DELETE", "HOME", "END", "F5", etc.
            """
            _MAPA = {
                "TAB": Keys.TAB,
                "ENTER": Keys.ENTER,
                "ESCAPE": Keys.ESCAPE,
                "BACKSPACE": Keys.BACK_SPACE,
                "DELETE": Keys.DELETE,
                "HOME": Keys.HOME,
                "END": Keys.END,
                "F5": Keys.F5,
                "PAGE_UP": Keys.PAGE_UP,
                "PAGE_DOWN": Keys.PAGE_DOWN,
            }
            el = self._encontrar_elemento(seletor, valor, timeout)
            key = _MAPA.get(tecla.upper(), tecla)
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el)
                el.send_keys(key)
            except ElementNotInteractableException:
                logger.debug(
                    "ElementNotInteractable em enviar_tecla — usando ActionChains para %s='%s'",
                    seletor, valor,
                )
                ActionChains(self.driver).send_keys(key).perform()
            logger.debug("Tecla '%s' enviada para %s='%s'",
                         tecla, seletor, valor)

        # ------------------------------------------------------------------
        # Frames e iFrames
        # ------------------------------------------------------------------

        def alternar_frame(self, seletor: str, valor: str, timeout: int = 10) -> None:
            """Muda o contexto para o frame identificado pelo seletor."""
            el = self._encontrar_elemento(seletor, valor, timeout)
            self.driver.switch_to.frame(el)
            logger.debug(
                "Contexto alternado para frame: %s=%s | iframes internos: %d",
                seletor,
                valor,
                len(self.driver.find_elements(By.TAG_NAME, "iframe")),
            )

        def sair_frame(self) -> None:
            """Retorna o contexto para o documento principal."""
            self.driver.switch_to.default_content()

        def alternar_frame_com_elemento(
            self, seletor: str, valor: str, timeout: int = 5
        ) -> bool:
            """Retorna ao documento raiz e busca recursivamente o frame com o elemento.

            Ao retornar True, o driver já está posicionado no frame correto
            para que ações sejam realizadas imediatamente.

            Returns:
                True se o elemento foi encontrado (contexto já está no frame correto).
                False se não encontrado em nenhum frame/documento.
            """
            self.driver.switch_to.default_content()
            return self._buscar_elemento_nos_frames(seletor, valor, timeout)

        @contextmanager
        def frame_do_elemento(
            self, seletor: str, valor: str, timeout: int = 5
        ) -> Generator[None, None, None]:
            """Context manager que localiza o iFrame do elemento e restaura o contexto ao sair.

            Busca recursivamente o frame que contém o elemento, posiciona o driver
            nele e, ao sair do bloco `with`, retorna automaticamente ao documento
            principal — mesmo que uma exceção seja levantada dentro do bloco.

            Raises:
                ElementoNaoEncontradoError: se não encontrar o elemento em nenhum frame.
            """
            encontrou = self.alternar_frame_com_elemento(
                seletor, valor, timeout)
            if not encontrou:
                raise ElementoNaoEncontradoError(
                    f"Elemento não encontrado em nenhum frame: {seletor}='{valor}'"
                )
            try:
                yield
            finally:
                self.driver.switch_to.default_content()
                logger.debug("Contexto restaurado para o documento principal.")

        def _buscar_elemento_nos_frames(
            self, seletor: str, valor: str, timeout: int
        ) -> bool:
            """Busca recursiva por elemento nos frames do contexto atual.

            Testa o contexto atual antes de entrar nos frames filhos.
            Ao encontrar, mantém o contexto posicionado no frame correto.
            """
            # Testa no contexto atual (espera curta para não travar em frames vazios)
            try:
                WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located(self._by(seletor, valor))
                )
                return True
            except TimeoutException:
                pass

            frames = self.driver.find_elements(
                By.XPATH, ".//iframe | .//frame")
            logger.debug(
                "Verificando %d frame(s) no contexto atual.", len(frames))

            for idx, frame in enumerate(frames):
                try:
                    self.driver.switch_to.frame(frame)
                    logger.debug("Entrando no frame %d de %d.",
                                 idx + 1, len(frames))
                    if self._buscar_elemento_nos_frames(seletor, valor, timeout):
                        return True
                    self.driver.switch_to.parent_frame()
                except Exception:
                    logger.debug(
                        "Falha ao navegar no frame %d; reposicionando para o pai.",
                        idx + 1,
                    )
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        pass

            return False

        # ------------------------------------------------------------------
        # Utilitários de página
        # ------------------------------------------------------------------

        def obter_html(self) -> str:
            """Retorna o HTML da página atual."""
            return self.driver.page_source

        def obter_titulo(self) -> str:
            """Retorna o título da página atual."""
            return self.driver.title

        def obter_url(self) -> str:
            """Retorna a URL atual do navegador."""
            return self.driver.current_url

        def aguardar(self, segundos: float) -> None:
            """Pausa a execução por uma duração em segundos."""
            time.sleep(segundos)

        def executar_javascript(self, script: str) -> Any:
            """Executa um script JavaScript no contexto da página atual."""
            return self.driver.execute_script(script)

        def captura_tela(self, caminho: str) -> None:
            """Salva uma captura de tela no caminho especificado."""
            self.driver.save_screenshot(caminho)
            logger.debug("Captura de tela salva em: %s", caminho)

        def tratar_alerta(self, aceitar: bool = True, timeout: int = 10) -> Optional[str]:
            """Aceita ou descarta alerta e retorna seu texto."""
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.alert_is_present())
                alert = self.driver.switch_to.alert
                texto = alert.text
                alert.accept() if aceitar else alert.dismiss()
                return texto
            except (TimeoutException, NoAlertPresentException):
                return None
            except Exception:
                return None

        # ------------------------------------------------------------------
        # Utilitários internos
        # ------------------------------------------------------------------

        def _by(self, seletor: str, valor: str) -> tuple:
            """Mapeia seletor textual para tupla (By, valor) do Selenium."""
            mapa = {
                "id": By.ID,
                "xpath": By.XPATH,
                "css": By.CSS_SELECTOR,
                "name": By.NAME,
                "class": By.CLASS_NAME,
                "tag": By.TAG_NAME,
            }
            if seletor not in mapa:
                raise ValueError(
                    f"Seletor '{seletor}' não suportado. Use: {list(mapa.keys())}"
                )
            return (mapa[seletor], valor)

        def _encontrar_elemento(self, seletor: str, valor: str, timeout: int = 5) -> Any:
            """Aguarda elemento estar presente no DOM e o retorna.

            Raises:
                ElementoNaoEncontradoError: se não encontrado dentro do timeout.
            """
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located(self._by(seletor, valor))
                )
            except TimeoutException as e:
                msg = f"Elemento não encontrado: {seletor}='{valor}' (timeout={timeout}s)"
                logger.error(msg)
                raise ElementoNaoEncontradoError(msg) from e

        # ------------------------------------------------------------------
        # Context manager
        # ------------------------------------------------------------------

        def __enter__(self) -> "WebController":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            try:
                self.fechar_navegador()
            except Exception:
                logger.exception("Erro ao fechar navegador no __exit__")

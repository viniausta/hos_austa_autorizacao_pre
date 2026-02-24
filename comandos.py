"""Comandos para automação 

Este módulo fornece comandos utilizando Selenium WebDriver com uma
proteção de compatibilidade: se o `selenium` não estiver instalado, o módulo ainda pode ser
importado, mas ao tentar instanciar `WebController` gera um erro claro.
"""

import time
import logging
import os
from pathlib import Path
from typing import Any, Optional, Tuple, List, Dict, TYPE_CHECKING


try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoAlertPresentException,
        WebDriverException,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    # webdriver-manager é opcional; tenta importar gerenciadores por conveniência
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.firefox import GeckoDriverManager
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        _WEBDRIVER_MANAGER_AVAILABLE = True
    except Exception:
        _WEBDRIVER_MANAGER_AVAILABLE = False

    _SELENIUM_AVAILABLE = True
except Exception:
    _SELENIUM_AVAILABLE = False
    webdriver = None
    WebDriver = object
    Options = object
    ChromeService = object
    WebDriverWait = object
    Select = object
    EC = object
    TimeoutException = Exception
    NoAlertPresentException = Exception
    WebDriverException = Exception
    By = object
    ActionChains = object

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Funções utilitárias internas
# mesmo quando o driver oracledb não está instalado no ambiente.
try:
    import oracledb
except Exception:
    oracledb = None


if not _SELENIUM_AVAILABLE:
    class WebController:
        """Placeholder quando selenium não está disponível.

        Tentar instanciar esta classe gerará um RuntimeError com uma
        instrução clara para instalar o Selenium.
        """

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "Selenium is required to use WebController. Install it: pip install selenium"
            )

else:
    class WebController:
        """Wrapper do Selenium WebDriver."""

        def __init__(self, driver_path: Optional[str] = None, browser: str = "chrome") -> None:
            """Inicializa o controlador de navegador.

            Args:
                driver_path: Caminho opcional para o executável do driver.
                browser: Nome do navegador ("chrome", "firefox" ou "edge").
            """
            self.driver: Any = self._start_browser(driver_path, browser)
            self.actions = ActionChains(self.driver)

        def _start_browser(self, driver_path: Optional[str], browser: str) -> Any:
            """Cria e retorna a instância do WebDriver conforme o navegador.

            Usa a API de Service do Selenium 4 quando disponível.
            """
            options = Options()
            options.add_argument("--start-maximized")
            options.add_experimental_option(
                "excludeSwitches", ["enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("disable-popup-blocking")
            options.add_argument("disable-notifications")
            options.add_argument("disable-gpu")
            project_root = Path(__file__).resolve().parent

            def _local_driver_path(names: list) -> Optional[str]:
                # verifica nomes comuns de executáveis na raiz do projeto
                for n in names:
                    p = project_root / n
                    if p.exists():
                        return str(p)
                return None

            try:
                if browser == "chrome":
                    # Usa webdriver-manager se disponível e nenhum driver_path explícito fornecido
                    if _WEBDRIVER_MANAGER_AVAILABLE and not driver_path:
                        try:
                            mgr_path = ChromeDriverManager().install()
                            service = ChromeService(mgr_path)
                        except Exception:
                            # fallback: tenta encontrar driver na raiz do projeto
                            local = _local_driver_path(
                                ["chromedriver.exe", "chromedriver"])
                            if local:
                                service = ChromeService(executable_path=local)
                            else:
                                # última opção: deixa ChromeService escolher (requer driver no PATH)
                                service = ChromeService()
                    else:
                        # explicit driver_path or no webdriver-manager: prefer provided path
                        if driver_path:
                            service = ChromeService(
                                executable_path=driver_path)
                        else:
                            local = _local_driver_path(
                                ["chromedriver.exe", "chromedriver"])
                            service = ChromeService(
                                executable_path=local) if local else ChromeService()
                    return webdriver.Chrome(service=service, options=options)
                elif browser == "firefox":
                    from selenium.webdriver.firefox.service import Service as FirefoxService
                    if _WEBDRIVER_MANAGER_AVAILABLE and not driver_path:
                        try:
                            mgr_path = GeckoDriverManager().install()
                            service = FirefoxService(mgr_path)
                        except Exception:
                            local = _local_driver_path(
                                ["geckodriver.exe", "geckodriver"])
                            if local:
                                service = FirefoxService(executable_path=local)
                            else:
                                service = FirefoxService()
                    else:
                        if driver_path:
                            service = FirefoxService(
                                executable_path=driver_path)
                        else:
                            local = _local_driver_path(
                                ["geckodriver.exe", "geckodriver"])
                            service = FirefoxService(
                                executable_path=local) if local else FirefoxService()
                    return webdriver.Firefox(service=service)
                elif browser == "edge":
                    from selenium.webdriver.edge.service import Service as EdgeService
                    if _WEBDRIVER_MANAGER_AVAILABLE and not driver_path:
                        try:
                            mgr_path = EdgeChromiumDriverManager().install()
                            service = EdgeService(mgr_path)
                        except Exception:
                            local = _local_driver_path(
                                ["msedgedriver.exe", "msedgedriver"])
                            if local:
                                service = EdgeService(executable_path=local)
                            else:
                                service = EdgeService()
                    else:
                        if driver_path:
                            service = EdgeService(executable_path=driver_path)
                        else:
                            local = _local_driver_path(
                                ["msedgedriver.exe", "msedgedriver"])
                            service = EdgeService(
                                executable_path=local) if local else EdgeService()
                    return webdriver.Edge(service=service)
                else:
                    raise ValueError("Navegador não suportado.")
            except WebDriverException as e:
                logger.error("Erro ao iniciar navegador: %s", e)
                raise

        def navegar(self, url: str) -> None:
            """Navega para uma URL específica no navegador.

            Args:
                url (str): A URL completa para qual o navegador deve navegar.
                          Deve incluir o protocolo (http:// ou https://).

            Returns:
                None

            Raises:
                Exception: Se ocorrer algum erro durante a navegação.

            Exemplo:
                controller.navegar('https://www.exemplo.com.br')
            """
            try:
                self.driver.get(url)
                logger.info("Navegou para %s", url)
            except Exception:
                logger.exception("Erro ao navegar para %s", url)
                raise

        def voltar_pagina(self) -> None:
            """Navega para a página anterior no histórico do navegador.

            Este método é equivalente a clicar no botão 'Voltar' do navegador.

            Returns:
                None

            Exemplo:
                controller.voltar_pagina()
            """
            self.driver.back()

        def avancar_pagina(self) -> None:
            """Avança uma página no histórico do navegador."""
            self.driver.forward()

        def atualizar_pagina(self) -> None:
            """Recarrega a página atual do navegador."""
            self.driver.refresh()

        def fechar_navegador(self) -> None:
            """Encerra o navegador e libera recursos."""
            self.driver.quit()

        def abrir_nova_aba(self, url: Optional[str] = None) -> None:
            """Abre uma nova aba e, opcionalmente, navega para uma URL."""
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            if url:
                self.navegar(url)

        def alternar_aba(self, indice: int) -> None:
            """Alterna o foco para a aba pelo índice na lista de janelas."""
            self.driver.switch_to.window(self.driver.window_handles[indice])

        def fechar_aba(self) -> None:
            """Fecha a aba atual e alterna para a última aba restante, se houver."""
            self.driver.close()
            if self.driver.window_handles:
                self.driver.switch_to.window(self.driver.window_handles[-1])

        def localizar_ou_anexar_aba(
            self, titulo_contem: Optional[str] = None, url_contem: Optional[str] = None, timeout: int = 10
        ) -> bool:
            """Procura por uma aba cujo título ou URL contenha o texto especificado.

            Retorna True se encontrou a aba dentro do timeout.
            """
            end_time = time.time() + timeout
            while time.time() < end_time:
                for handle in self.driver.window_handles:
                    self.driver.switch_to.window(handle)
                    if (
                        (titulo_contem and titulo_contem in self.driver.title)
                        or (url_contem and url_contem in self.driver.current_url)
                    ):
                        return True
                time.sleep(0.5)
            return False

        def click_elemento(self, seletor: str, valor: str, timeout: int = 10, js: bool = False) -> bool:
            """Clica em um elemento da página web identificado pelo seletor especificado.

            Args:
                seletor (str): Tipo de seletor (id, xpath, css, name, class, tag).
                valor (str): O valor do seletor para localizar o elemento.
                timeout (int, optional): Tempo máximo de espera em segundos. Padrão é 10.

            Returns:
                None

            Raises:
                TimeoutException: Se o elemento não for encontrado no tempo especificado.

            Exemplo:
                # Clica em um botão com id="salvar"
                controller.click_elemento('id', 'salvar')

                # Clica em um link com texto específico
                controller.click_elemento('xpath', '//a[text()="Próximo"]')
            """
            el = self._encontrar_elemento(seletor, valor, timeout)
            if js:
                if el:
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
            else:
                if el:
                    el.click()
                    return True
            return False

        def definir_valor(self, seletor: str, valor: str, texto: str, timeout: int = 5) -> None:
            """Define um texto em um elemento de input após limpar seu conteúdo anterior.

            Args:
                seletor (str): Tipo de seletor (id, xpath, css, name, class, tag).
                valor (str): O valor do seletor para localizar o elemento.
                texto (str): O texto a ser inserido no elemento.
                timeout (int, optional): Tempo máximo de espera em segundos. Padrão é 10.

            Returns:
                None

            Raises:
                TimeoutException: Se o elemento não for encontrado no tempo especificado.

            Exemplo:
                # Preenche um campo de email
                controller.definir_valor('id', 'email', 'usuario@exemplo.com')

                # Preenche um campo de busca
                controller.definir_valor('name', 'busca', 'termos de busca')
            """
            el = self._encontrar_elemento(seletor, valor, timeout)
            el.clear()
            el.send_keys(texto)

        def obter_texto(self, seletor: str, valor: str, timeout: int = 10) -> str:
            """Retorna o texto visível do elemento localizado."""
            el = self._encontrar_elemento(seletor, valor, timeout)
            return el.text

        def obter_atributo(self, seletor: str, valor: str, atributo: str, timeout: int = 10) -> Optional[str]:
            """Retorna o valor do atributo solicitado do elemento localizado."""
            el = self._encontrar_elemento(seletor, valor, timeout)
            return el.get_attribute(atributo)

        def aguardar_elemento_visivel(self, seletor: str, valor: str, timeout: int = 10) -> bool:
            """Aguarda até que um elemento esteja visível na página dentro do tempo especificado.

            Args:
                seletor (str): Tipo de seletor (id, xpath, css, name, class, tag).
                valor (str): O valor do seletor para localizar o elemento.
                timeout (int, optional): Tempo máximo de espera em segundos. Padrão é 10.

            Returns:
                bool: True se o elemento ficou visível dentro do timeout, False caso contrário.

            Exemplo:
                # Aguarda até 5 segundos por um elemento de loading desaparecer
                if controller.aguardar_elemento_visivel('id', 'loading', 5):
                    print('Elemento ficou visível')
                else:
                    print('Elemento não apareceu no tempo esperado')
            """
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located(self._by(seletor, valor))
                )
                return True
            except TimeoutException:
                return False

        def verificar_existencia_elemento(self, seletor: str, valor: str, timeout: int = 5) -> bool:
            """Verifica se um elemento existe (presença) dentro do timeout.

            Retorna True em caso positivo, False caso não seja encontrado.
            """
            try:
                self._encontrar_elemento(seletor, valor, timeout)
                return True
            except TimeoutException:
                return False

        def selecionar_opcao(self, seletor: str, valor: str, texto_opcao: str, timeout: int = 10) -> None:
            """Seleciona uma opção em um elemento select pelo texto visível.

            Args:
                seletor (str): Tipo de seletor (id, xpath, css, name, class, tag).
                valor (str): O valor do seletor para localizar o elemento select.
                texto_opcao (str): O texto visível da opção que deve ser selecionada.
                timeout (int, optional): Tempo máximo de espera em segundos. Padrão é 10.

            Returns:
                None

            Raises:
                TimeoutException: Se o elemento não for encontrado no tempo especificado.

            Exemplo:
                controller.selecionar_opcao('id', 'estado', 'São Paulo')
            """
            el = self._encontrar_elemento(seletor, valor, timeout)
            Select(el).select_by_visible_text(texto_opcao)

        def rolar_para_elemento(self, seletor: str, valor: str, timeout: int = 10) -> None:
            """Rola a página até que o elemento especificado fique visível na viewport.

            Args:
                seletor (str): Tipo de seletor (id, xpath, css, name, class, tag).
                valor (str): O valor do seletor para localizar o elemento.
                timeout (int, optional): Tempo máximo de espera em segundos. Padrão é 10.

            Returns:
                None

            Raises:
                TimeoutException: Se o elemento não for encontrado no tempo especificado.

            Exemplo:
                controller.rolar_para_elemento('id', 'secao-comentarios', 5)
            """
            el = self._encontrar_elemento(seletor, valor, timeout)
            self.driver.execute_script(
                "arguments[0].scrollIntoView(true);", el)

        def upload_arquivo(self, seletor: str, valor: str, caminho_arquivo: str, timeout: int = 10) -> None:
            """Realiza o upload de um arquivo através de um elemento input do tipo file.

            Args:
                seletor (str): Tipo de seletor (id, xpath, css, name, class, tag).
                valor (str): O valor do seletor para localizar o elemento input file.
                caminho_arquivo (str): Caminho completo do arquivo a ser enviado.
                timeout (int, optional): Tempo máximo de espera em segundos. Padrão é 10.

            Returns:
                None

            Raises:
                TimeoutException: Se o elemento não for encontrado no tempo especificado.
                Exception: Se o arquivo não existir ou não puder ser acessado.

            Exemplo:
                # Upload de um documento
                controller.upload_arquivo('id', 'input-arquivo', 'C:/documentos/contrato.pdf')
            """
            el = self._encontrar_elemento(seletor, valor, timeout)
            el.send_keys(caminho_arquivo)

        # Validação e extração
        def obter_html(self) -> str:
            """Retorna o HTML da página atual (page_source)."""
            return self.driver.page_source

        def obter_titulo(self) -> str:
            """Retorna o título da página atual."""
            return self.driver.title

        def obter_url(self) -> str:
            """Retorna a URL atual do navegador."""
            return self.driver.current_url

        # Execução e controle
        def aguardar(self, segundos: float) -> None:
            """Pausa a execução por uma duração em segundos."""
            time.sleep(segundos)

        def executar_javascript(self, script: str) -> Any:
            """Executa um script JavaScript no contexto da página atual.

            Args:
                script (str): O código JavaScript a ser executado.

            Returns:
                Any: O resultado da execução do script JavaScript, se houver.
                     O tipo do retorno depende do que o script retorna.

            Exemplo:
                # Recuperar o valor de uma variável JavaScript
                valor = controller.executar_javascript('return window.innerHeight;')

                # Executar uma função JavaScript
                controller.executar_javascript('window.scrollTo(0, document.body.scrollHeight);')
            """
            return self.driver.execute_script(script)

        def alternar_frame(self, seletor: str, valor: str, timeout: int = 10) -> None:
            """Muda o contexto para o frame especificado pelo elemento localizado."""
            el = self._encontrar_elemento(seletor, valor, timeout)

            self.driver.switch_to.frame(el)
            print(self.driver.page_source[:2000])
            print(f"IFRAMES:", self.driver.find_elements(By.TAG_NAME, "iframe"))
            print(f"FRAMES:", self.driver.find_elements(By.TAG_NAME, "frame"))

        def sair_frame(self) -> None:
            """Retorna o contexto para o documento principal (sai do frame)."""
            self.driver.switch_to.default_content()

        def alternar_frame_com_elemento(self, seletor: str, valor: str, timeout: int = 5) -> bool:
            """Retorna ao documento raiz e busca recursivamente o iFrame que contém o elemento.

            Percorre todos os iFrames e frames aninhados da página até localizar
            o elemento especificado. Ao retornar True, o contexto do driver já
            estará posicionado no frame correto para ações imediatas.

            Args:
                seletor (str): Tipo de seletor (id, xpath, css, name, class, tag).
                valor (str): O valor do seletor para localizar o elemento.
                timeout (int): Tempo de espera ao verificar cada frame. Padrão é 5.

            Returns:
                bool: True se o elemento foi encontrado (driver já está no frame correto),
                      False se não encontrado em nenhum frame/documento.

            Exemplo:
                if nav.alternar_frame_com_elemento("id", "nmUsuario"):
                    nav.definir_valor("id", "nmUsuario", usuario, timeout=5)
            """
            self.driver.switch_to.default_content()
            return self._buscar_elemento_nos_frames(seletor, valor, timeout)

        def _buscar_elemento_nos_frames(self, seletor: str, valor: str, timeout: int) -> bool:
            """Busca recursiva por um elemento nos frames do contexto atual.

            Tenta localizar o elemento no contexto atual; caso não encontre,
            entra em cada iframe/frame filho e repete o processo.
            Ao encontrar o elemento, o contexto permanece no frame correto.
            """
            # Verifica no contexto atual antes de entrar em frames filhos
            try:
                WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located(self._by(seletor, valor))
                )
                return True
            except TimeoutException:
               pass

            # Coleta todos os iframes e frames filhos do contexto atual
            frames = self.driver.find_elements(By.XPATH, ".//iframe | .//frame")
            logger.debug("Frames encontrados no contexto atual: %d", len(frames))

            for idx, frame in enumerate(frames):
                try:
                    self.driver.switch_to.frame(frame)
                    logger.debug("Entrando no frame %d de %d", idx + 1, len(frames))

                    if self._buscar_elemento_nos_frames(seletor, valor, timeout):
                        return True

                    # Elemento não encontrado neste frame; sobe para o pai
                    self.driver.switch_to.parent_frame()
                except Exception:
                    logger.debug("Falha ao entrar/sair do frame %d; tentando parent_frame", idx + 1)
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        pass

            return False

        def captura_tela(self, caminho: str) -> None:
            """Salva uma captura de tela no caminho especificado."""
            self.driver.save_screenshot(caminho)

        def tratar_alerta(self, aceitar: bool = True, timeout: int = 10) -> Optional[str]:
            """Caso exista um alerta, aceita ou descarta conforme o parâmetro e retorna o texto."""
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.alert_is_present())
                alert = self.driver.switch_to.alert
                texto = alert.text
                if aceitar:
                    alert.accept()
                else:
                    alert.dismiss()
                return texto
            except (TimeoutException, NoAlertPresentException):
                return None

        # Utilitários internos
        def _by(self, seletor: str, valor: str):
            """Mapeia um seletor textual para a tupla (By, valor) usada pelo Selenium."""
            mapa = {
                "id": By.ID,
                "xpath": By.XPATH,
                "css": By.CSS_SELECTOR,
                "name": By.NAME,
                "class": By.CLASS_NAME,
                "tag": By.TAG_NAME,
            }
            return (mapa[seletor], valor)

        def _encontrar_elemento(self, seletor: str, valor: str, timeout: int = 5):
            """Espera até que o elemento esteja presente no DOM e o retorna.

            Lança TimeoutException se não for encontrado dentro do timeout.
            """
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located(self._by(seletor, valor))
                )
            except TimeoutException:
                logger.error("Elemento não encontrado: %s=%s", seletor, valor)
                return False

        # Logging e helpers
        def log_info(self, mensagem: str) -> None:
            """Registra uma mensagem informativa no logger."""
            logger.info(mensagem)

        def log_erro(self, mensagem: str) -> None:
            """Registra uma mensagem de erro no logger."""
            logger.error(mensagem)

        # Suporte a gerenciador de contexto -------------------------------------------------
        def __enter__(self) -> "WebController":
            """Suporta o contexto 'with' retornando o próprio controlador."""
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            """Garante o fechamento do navegador ao sair do contexto 'with'."""
            try:
                self.fechar_navegador()
            except Exception:
                logger.exception("Erro ao fechar navegador no __exit__")


# ---------------------- Database client ----------------------------------
class DBClient:
    """Pequeno cliente Oracle movido para este módulo.

    Usa o driver `oracledb` quando disponível. O tipo `Config` é usado como
    forward reference.
    """

    def __init__(self, config: "Config") -> None:
        if oracledb is None:
            raise RuntimeError(
                "oracledb não está instalado. Instale via pip install oracledb"
            )

        # Build DSN from config (keeps previous behavior)
        dsn = oracledb.makedsn(config.db_host, int(
            config.db_port or 1521), service_name=config.db_service)

        # Helper: tenta inicializar o Oracle Instant Client se um lib_dir for fornecido
        def _try_init_instant_client(lib_dir: Optional[str]) -> bool:
            if not lib_dir:
                return False
            try:
                oracledb.init_oracle_client(lib_dir=lib_dir)
                logger.info(
                    "oracledb.init_oracle_client called with %s", lib_dir)
                return True
            except Exception:
                logger.exception("init_oracle_client failed for %s", lib_dir)
                return False

        # Tenta conexão em modo thin primeiro
        try:
            self.conn = oracledb.connect(
                user=config.db_user, password=config.db_password, dsn=dsn)
            return
        except Exception as e:
            #  Se o driver reclamar que init_oracle_client() precisa ser chamado primeiro
            #  ou que o verificador de senha não é compatível no modo thin (DPY-3015)
            msg = str(e)
            # DPY-2021 e DPY-3015 são casos conhecidos onde thick client/init_oracle_client é necessário
            if (
                "init_oracle_client() must be called first" in msg
                or "DPY-2021" in msg
                or "DPY-3015" in msg
                or "password verifier" in msg
            ):
                # Tenta localizar lib_dir da variável de ambiente ORACLE_INSTANT_CLIENT_DIR
                lib_dir = None
                try:
                    lib_dir = os.environ.get("ORACLE_INSTANT_CLIENT_DIR")
                except Exception:
                    lib_dir = None

                # Por conveniência, também verifica alguns nomes comuns dentro da raiz do projeto
                project_root = Path(__file__).resolve().parent
                common_paths = [
                    project_root / "instantclient",
                    project_root / "instantclient_23_9",
                    project_root / "instantclient_19_8",
                ]
                if not lib_dir:
                    for p in common_paths:
                        if p.exists():
                            lib_dir = str(p)
                            break

                if lib_dir and _try_init_instant_client(lib_dir):
                    try:
                        # tenta conexão novamente após init_oracle_client()
                        self.conn = oracledb.connect(
                            user=config.db_user, password=config.db_password, dsn=dsn)
                        return
                    except Exception:
                        logger.exception(
                            "conexão falhou mesmo após init_oracle_client")
                        raise
                else:
                    # relança o erro original se não conseguimos inicializar o cliente
                    logger.error(
                        "oracledb reported init_oracle_client required and no Instant Client found/configured")
                    raise
            else:
                # Erro desconhecido - relança
                raise

    def cursor(self):
        """Retorna um cursor Oracle padrão"""
        return self.conn.cursor()

    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Executa uma consulta SQL e retorna os resultados como uma lista de dicionários.

        Args:
            sql (str): A consulta SQL a ser executada.
            params (Optional[Tuple], optional): Tupla com os parâmetros da consulta. Padrão é None.

        Returns:
            List[Dict[str, Any]]: Lista de dicionários onde cada dicionário representa uma linha 
                                do resultado, com as chaves sendo os nomes das colunas em minúsculas.

        Exemplo:
            # Consulta simples sem parâmetros
            resultados = db.execute_query("SELECT id, nome FROM usuarios")

            # Consulta com parâmetros
            usuarios = db.execute_query(
                "SELECT id, nome FROM usuarios WHERE departamento = ?",
                ('TI',)
            )
            for usuario in usuarios:
                print(f"ID: {usuario['id']}, Nome: {usuario['nome']}")
        """
        logger.debug("Executando query: %s | params=%s", sql, params)
        cur = self.conn.cursor()
        cur.execute(sql) if not params else cur.execute(sql, params)
        cols = [c[0].lower()
                for c in cur.description] if cur.description else []
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        return rows

    def execute_scalar(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Executa uma consulta SQL e retorna um único valor.

        Args:
            sql (str): A consulta SQL a ser executada.
            params (Optional[Tuple], optional): Parâmetros da consulta. Padrão é None.

        Returns:
            Any: O primeiro valor da primeira linha do resultado, ou None se não houver resultados.

        Exemplo:
            total = db.execute_scalar("SELECT COUNT(*) FROM usuarios WHERE ativo = ?", (True,))
            print(f'Total de usuários ativos: {total}')
        """
        cur = self.conn.cursor()
        cur.execute(sql) if not params else cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None

    def execute_non_query(self, sql: str, params: Optional[Tuple] = None) -> None:
        cur = self.conn.cursor()
        cur.execute(sql) if not params else cur.execute(sql, params)
        self.conn.commit()
        cur.close()

    def call_procedure(self, name: str, params: Dict[str, Any]) -> None:
        """Executa uma procedure armazenada no banco de dados Oracle.

        Args:
            name (str): Nome da procedure a ser executada.
            params (Dict[str, Any]): Dicionário com os parâmetros da procedure.
                                   As chaves são os nomes dos parâmetros e os
                                   valores são os valores a serem passados.

        Returns:
            None

        Exemplo:
            db.call_procedure('atualizar_status', {
                'p_id': 123,
                'p_status': 'ATIVO'
            })
        """
        logger.debug("Chamando procedure %s com %s", name, params)
        cur = self.conn.cursor()
        cur.callproc(name, list(params.values()))
        self.conn.commit()
        cur.close()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            logger.exception("Erro ao fechar conexão com o banco")

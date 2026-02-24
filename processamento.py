
from __future__ import annotations

import oracledb
from trio import sleep
from logs.logger_config import logger
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable
from comandos import WebController, DBClient
from dotenv import load_dotenv

if load_dotenv:
    load_dotenv()


@runtime_checkable
class DatabaseProtocol(Protocol):
    def execute_query(
        self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]: ...

    def execute_scalar(
        self, sql: str, params: Optional[Tuple] = None) -> Any: ...

    def execute_non_query(
        self, sql: str, params: Optional[Tuple] = None) -> None: ...

    def call_procedure(self, name: str, params: Dict[str, Any]) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class BrowserProtocol(Protocol):
    def navegar(self, url: str) -> None: ...

    def aguardar_elemento_visivel(
        self, seletor: str, valor: str, timeout: int = 10) -> bool: ...

    def definir_valor(self, seletor: str, valor: str,
                      texto: str, timeout: int = 10) -> None: ...

    def click_elemento(self, seletor: str, valor: str,
                       timeout: int = 10) -> None: ...


@dataclass
class Config:
    caminho_padrao: Path
    dev_mode: bool
    db_user: str
    db_password: str
    db_host: str
    db_port: str
    db_service: str
    id_unidade: str
    id_projeto: str
    caminho_chrome_driver: str
    caminho_rede_anexo: str
    senha_rede_anexo: str
    usuario_tasy: str
    senha_tasy: str

    @classmethod
    def from_env(cls) -> "Config":
        caminho = os.environ.get("CAMINHO_PADRAO", " ")
        dev = os.environ.get("DEV", "False").lower() in ("1", "true", "yes")
        user = os.environ.get("BD_USUARIO", "")
        pwd = os.environ.get("BD_SENHA", "")
        lista = os.environ.get("AUSTA_BD_ORACLE", "")
        host, port, service = ("", "", "")
        id_unidade = os.environ.get("ID_UNIDADE", "")
        usuario_tasy = os.environ.get("USUARIO_TASY", "")
        senha_tasy = os.environ.get("SENHA_TASY", "")
        id_projeto = os.environ.get("ID_PROJETO", "")
        caminho_rede_anexo = os.environ.get("CAMINHO_REDE_ANEXO", "")
        senha_rede_anexo = os.environ.get("SENHA_REDE_ANEXO", "")
        driver = os.environ.get("CAMINHO_CHROME_DRIVER", "")

        if lista:
            parts = lista.split(",")
            host = parts[0] if len(parts) > 0 else ""
            port = parts[1] if len(parts) > 1 else ""
            service = parts[2] if len(parts) > 2 else ""

        return cls(
            caminho_padrao=Path(caminho),
            dev_mode=dev,
            db_user=user,
            db_password=pwd,
            db_host=host,
            db_port=port,
            db_service=service,
            id_unidade=id_unidade,
            id_projeto=id_projeto,
            caminho_rede_anexo=caminho_rede_anexo,
            senha_rede_anexo=senha_rede_anexo,
            caminho_chrome_driver=driver,
            usuario_tasy=usuario_tasy,
            senha_tasy=senha_tasy
        )


class Processamento:
    def __init__(self, config: Config, db: Optional[DatabaseProtocol] = None, browser: Optional[BrowserProtocol] = None) -> None:
        self.config = config
        self.db = db
        self.navegador = browser
        self._owns_db = db is None
        self._owns_browser = browser is None
        self.controle_execucao: Optional[int] = None

    def inicializar(self) -> None:
        logger.info("Inicializando automação")
        self.config.caminho_padrao.mkdir(parents=True, exist_ok=True)
        evidencia_dir = self.config.caminho_padrao / "Evidencia"
        evidencia_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        timestamp = now.strftime("%d.%m.%Y_%H.%M.%S")
        logger.debug("Data atual: %s -> %s", now.isoformat(), timestamp)

        if self.navegador is None:  # Instancia o navegador
            try:
                self.navegador = WebController()
                self._owns_browser = True
            except Exception as e:
                logger.exception("Falha ao instanciar o navegador: {e}")
                raise

        if self.db is None:  # Conecta ao banco de dados
            try:
                self.db = DBClient(self.config)
                logger.info("Conectado ao Oracle em %s:%s/%s", self.config.db_host,
                            self.config.db_port, self.config.db_service)
                self._owns_db = True
            except Exception as e:
                logger.exception("Falha ao conectar no Oracle: {e}")
                raise

        try:
            if self.db:
                # Obtém parâmetros do banco
                self.crm = self.proc_obter_parametro(
                    chave="CRM_PRE", id_projeto=1, id_unidade=1001, dev=False
                )

                self.caminho_padrao = self.proc_obter_parametro(
                    chave="CAMINHO_PADRAO", id_projeto=1, id_unidade=1001, dev=False)
                # Cria variável para receber o valor de saída
                cursor = self.db.cursor()
                id_execucao_out = cursor.var(oracledb.NUMBER)

                params = {
                    "P_UNIDADE": os.environ.get("UNIDADE", ""),
                    "P_PROJETO": os.environ.get("PROJETO", ""),
                    "P_SCRIPT": os.environ.get("RPA_SCRIPT_NAME", ""),
                    "P_ETAPA": "-",
                    "P_USUARIO": os.environ.get("USERNAME", ""),
                    "P_ID_EXECUCAO": id_execucao_out  # variável OUT
                }

                try:
                    self.db.call_procedure(
                        "ROBO_RPA.PR_CRIAR_CONTROLE_EXECUCAO", params)

                    self.controle_execucao = id_execucao_out.getvalue()

                    logger.info(
                        f"Controle de execução criado com sucesso: {self.controle_execucao}")

                except Exception as e:
                    logger.exception(
                        f"Erro ao criar o controle de execução: {e}")
        except Exception as e:
            logger.exception(f"Erro ao registrar controle de execução: {e}")

    def registrar_log(self, tipo_log: str, mensagem: str, tipo_registro: Optional[str] = None) -> None:
        if self.config.dev_mode:
            if "INFO" in tipo_log.upper():
                logger.info(mensagem)
            elif "WARN" in tipo_log.upper():
                logger.warning(mensagem)
            else:
                logger.error(mensagem)

        if self.db:
            try:
                params = {"p_id_execucao": self.controle_execucao or 0, "p_tipo_log": tipo_log,
                          "p_registro_id": tipo_registro or "", "p_mensagem": mensagem}
                self.db.call_procedure("ROBO_RPA.PR_REGISTRAR_LOG", params)
            except Exception as e:
                logger.exception(f"Falha ao registrar log no banco: {e}")

    def proc_obter_parametro(self, chave: str, id_unidade: int, id_projeto: int, dev: str) -> Optional[str]:

        if not id_unidade:
            id_unidade = int(self.config.id_unidade)
        if not id_projeto:
            id_projeto = int(self.config.id_projeto)
        if dev is None:
            dev = str(self.config.dev_mode)

        if not self.db:
            raise RuntimeError("Banco não conectado")

        try:
            cursor = self.db.cursor()
            out_valor = cursor.var(oracledb.DB_TYPE_VARCHAR)

            params = {
                "P_ID_UNIDADE": id_unidade,
                "P_ID_PROJETO": id_projeto,
                "P_CHAVE": chave,
                "P_DEV": str(dev),
                "P_VALOR": out_valor
            }

            self.db.call_procedure(
                "ROBO_RPA.RPA_PARAMETRO_OBTER", params)

            valor = out_valor.getvalue()
            return valor
        except Exception as e:
            logger.exception(f"Erro ao obter parâmetro {chave}: {e}")
            return None

    def bd_importar_contas(self) -> int:
        sql = (
            "SELECT cnpj, razao_social, seq_terceiro, nr_repasse, nr_titulo, dt_lib_titulo, email, dt_ult_envio_email, dt_lib_repasse,cd_estabelecimento "
            "FROM TASY.RPA_EMAIL_REPASSE_V "
            "WHERE DT_LIB_TITULO >= TO_DATE('01/09/2025', 'DD/MM/YYYY') and cd_estabelecimento = 4 "
            "ORDER BY DT_LIB_TITULO ASC "
            "FETCH FIRST 50 ROWS ONLY"
        )

        rows = self.db.execute_query(sql)
        qtd_importados = 0

        for row in rows:
            cnpj = row.get("cnpj")
            razao_social = (row.get("razao_social") or "").replace("'", "\'")
            seq_terceiro = row.get("seq_terceiro")
            nr_repasse = row.get("nr_repasse")
            nr_titulo = row.get("nr_titulo")
            dt_lib_titulo = row.get("dt_lib_titulo")
            email = row.get("email")
            dt_ult_envio_email = row.get("dt_ult_envio_email")
            dt_lib_repasse = row.get("dt_lib_repasse")
            cd_estabelecimento = row.get("cd_estabelecimento")

            sql_check = "SELECT 1 FROM hos_repasse_medico WHERE nr_repasse = :1"
            existe = self.db.execute_scalar(sql_check, (nr_repasse,))
            if existe:
                continue

            sql_insert = (
                "INSERT INTO hos_repasse_medico (cnpj, razao_social, seq_terceiro, nr_repasse, nr_titulo, dt_lib_titulo, email, dt_ult_envio_email, status, dt_lib_repasse, cd_estabelecimento) "
                "VALUES (:1, :2, :3, :4, :5, TO_DATE(:6, 'DD/MM/YYYY HH24:MI:SS'), :7, TO_DATE(:8, 'DD/MM/YYYY HH24:MI:SS'), 'P', TO_DATE(:9, 'DD/MM/YYYY HH24:MI:SS'), :10)"
            )
            params = (cnpj, razao_social, seq_terceiro, nr_repasse,
                      nr_titulo, dt_lib_titulo, email, dt_ult_envio_email, dt_lib_repasse, cd_estabelecimento)
            try:
                self.db.execute_non_query(sql_insert, params)
                qtd_importados += 1
                self.registrar_log(
                    "INFO", f"Inserido na tabela HOS_REPASSE_MEDICO: Terceiro: {seq_terceiro} - Repasse: {nr_repasse} - Título: {nr_titulo} - CNPJ: {cnpj} - Status: P - Estabelecimento: {cd_estabelecimento}", nr_repasse)
            except Exception as e:
                logger.exception("Falha ao inserir repasse %s", nr_repasse)

        self.registrar_log(
            "INFO", f"Dados Importados com Sucesso: [{qtd_importados}/{len(rows)}]")
        return qtd_importados

    def login(self) -> None:
        try:
            nav = self.navegador

            if not nav:
                raise RuntimeError("Navegador não iniciado")

            nav.navegar(self.url)

            encontrou = nav.alternar_frame_com_elemento(
                "id", "nmUsuario", timeout=5)

            if not encontrou:
                raise RuntimeError(
                    "Elemento não encontrado em nenhum frame da página.")

            nav.selecionar_opcao('id', 'tipoUsuario', 'Prestador', timeout=10)

            nav.definir_valor(
                "id", "nmUsuario", self.config.usuario_tasy, timeout=5)

            nav.definir_valor(
                "id", "dsSenha", self.config.senha_tasy, timeout=5)

            nav.click_elemento(
                "id", "btn_entrar", timeout=10)

            encontrou = nav.alternar_frame_com_elemento(
                "xpath", "//font[text()='Requisição para autorização']", timeout=5)

            encontrou_elemento = nav.aguardar_elemento_visivel(
                "xpath", "//font[text()='Requisição para autorização']", timeout=5)

            if not encontrou_elemento:

                logger.error(
                    f"[HOS_AUSTA_AUTORIZACAOPRE] #Conv:[Unimed] #NrAtend: {self.nr_atendimento} > Falha login: Elemento esperado não encontrado após o login.")
                raise RuntimeError(
                    "Falha no login: elemento esperado não encontrado após o login.")

            self.registrar_log("INFO", "Login realizado com sucesso.")

        except Exception as e:
            logger.exception("Erro durante o login: %s", e)
            self.registrar_log("ERROR", f"Erro durante o login: {e}")
            raise

    def executar(self) -> None:
        self.usuario = self.proc_obter_parametro(
            chave="USUARIO_UNIMED", id_projeto=self.config.id_projeto, id_unidade=self.config.id_unidade, dev=self.config.dev_mode)
        self.senha = self.proc_obter_parametro(
            chave="SENHA_UNIMED", id_projeto=self.config.id_projeto, id_unidade=self.config.id_unidade, dev=self.config.dev_mode)
        self.url = self.proc_obter_parametro(
            chave="URL_UNIMED", id_projeto=self.config.id_projeto, id_unidade=self.config.id_unidade, dev=self.config.dev_mode)

        self.registrar_log(
            "INFO", f"Inicio robô - Id Exec: {self.controle_execucao}")

        continuar_execucao = True
        while continuar_execucao:
            continuar_execucao = self.proc_obter_parametro(
                chave="CONTINUAR_EXECUCAO", id_projeto=self.config.id_projeto, id_unidade=self.config.id_unidade, dev=self.config.dev_mode)

            tabela = self.db.execute_query(
                "SELECT * FROM tasy.BPM_AUTORIZACOES_V bpm WHERE 1 = 1 AND ds_setor_origem = 'CM-Pronto Atendimento' AND ie_tipo_autorizacao IN (1, 6) AND cd_convenio IN (27) AND dt_entrada > TRUNC(SYSDATE) AND cd_estabelecimento = 4 AND nr_atendimento = 306465")

            if not tabela:
                sleep(5)
                continue

            self.login()

            for idx, row in enumerate(tabela, start=1):
                nr_atendimento = row.get("nr_atendimento")
                nr_sequencia = row.get("nr_sequencia")
                cd_convenio = row.get("cd_convenio")
                cod_carterinha = row.get("cod_carterinha")
                cd_categoria = row.get("cd_categoria")
                dt_inicio_vigencia_eup = row.get("dt_inicio_vigencia_eup")
                tipo_autorizacao = row.get("tipo_autorizacao")
                dt_entrada = row.get("dt_entrada")
                dt_autorizacao = row.get("dt_autorizacao")
                ds_tipo_acomodacao = row.get("ds_tipo_acomodacao")
                cd_estabelecimento = row.get("cd_estabelecimento")

                logger.info(f'Novo registro Unimed: {len(tabela)}')

                try:
                    nav = self.navegador

                    if not nav:
                        self.navegador.navegar(self.url_login)
                        raise RuntimeError("Navegador não iniciado")

                except Exception:
                    logger.exception(
                        "Erro ao processar autorização %s", nr_atendimento)
                    self.registrar_log(
                        "ERROR", f"Erro ao processar autorização {nr_atendimento}")

    def finalizar(self) -> None:
        self.registrar_log("INFO", "Fim Robô")
        if self.db:
            try:
                params = {"P_ID_EXECUCAO": self.controle_execucao or 0,
                          "P_STATUS": "Concluido", "P_OBSERVACOES": "-"}
                try:
                    self.db.call_procedure(
                        "ROBO_RPA.PR_FINALIZAR_EXECUCAO", params)
                except Exception:
                    logger.debug(
                        "PR_FINALIZAR_EXECUCAO não disponível em ambiente de teste")
            finally:
                if self._owns_db:
                    try:
                        self.db.close()
                    except Exception:
                        logger.exception("Erro ao fechar conexão com o banco")

        if self.navegador and self._owns_browser:
            try:
                if hasattr(self.navegador, "fechar_navegador"):
                    getattr(self.navegador, "fechar_navegador")()
            except Exception:
                logger.exception("Erro ao fechar navegador")

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
import random
import shutil
import string
import time
from pathlib import Path
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

# Status TASY gravado em casos de impedimento/falha no processamento.
_NR_STATUS_IMPEDIMENTO = 167

# Status TASY gravado quando a autorização é detectada como duplicata.

_NR_STATUS_DUPLICADO = 14

# ---------------------------------------------------------------------------
# Query de busca — parâmetros dinâmicos evitam SQL injection e hardcodes
# ---------------------------------------------------------------------------
_SQL_AUTORIZACOES_PENDENTES = """
    select *  FROM tasy.BPM_AUTORIZACOES_V bpm
        WHERE ds_setor_origem = 'CM-Pronto Atendimento'
          AND ie_tipo_autorizacao IN (1, 6)
          AND cd_convenio IN (27)
          AND dt_entrada > TRUNC(SYSDATE)
          AND cd_estabelecimento = :1
          AND ds_estagio = 'CM-Necessidade de Autorização - WS'
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
        self.nr_crm = self._controle.obter_parametro("CRM_PRE")
        self.cod_prestador = self._config.cod_prestador
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

        # Keep-alive: a cada _KEEP_ALIVE_IDLES ciclos ociosos (~5 min a 5s/ciclo)
        # clica em Dossiê Beneficiário para manter a sessão do portal.
        _KEEP_ALIVE_IDLES = 60
        idle_count = 0

        while self._deve_continuar():
            try:
                autorizacoes = self._buscar_autorizacoes_pendentes()

                if not autorizacoes:
                    idle_count += 1
                    if idle_count >= _KEEP_ALIVE_IDLES:
                        logger.info(
                            "Keep-alive: mantendo sessão do portal ativa.")
                        self._autorizacao.manter_sessao()
                        idle_count = 0
                    logger.info(
                        "Nenhuma autorização pendente. Aguardando 5s...")
                    time.sleep(5)
                    continue

                idle_count = 0
                logger.info(
                    "%d autorização(ões) encontrada(s) para processar.", len(autorizacoes))
                self._controle.registrar_log(
                    "INFO", f"{len(autorizacoes)} autorização(ões) encontrada(s)."
                )

                for autorizacao in autorizacoes:
                    self._processar_item(autorizacao)

            except Exception as e:
                logger.exception(
                    "Erro inesperado no ciclo principal — RPA continua: %s", e
                )
                self._controle.registrar_log(
                    "ERROR", f"Erro inesperado no ciclo principal: {e}"
                )
                if self._notificador:
                    self._notificador.notificar_erro(
                        f"[{self._config.rpa_script_name}] Erro no ciclo principal — RPA continua",
                        detalhes=str(e),
                    )
                time.sleep(5)

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
        """Consulta o banco para saber se o loop deve continuar.

        Se o parâmetro não puder ser obtido (falha temporária de BD),
        mantém o loop ativo para recuperação automática.
        """
        raw = self._controle.obter_parametro("CONTINUAR_EXECUCAO")
        if raw is None:
            logger.warning(
                "CONTINUAR_EXECUCAO não obtido (possível falha temporária no banco) "
                "— mantendo loop ativo."
            )
            return True
        continuar = str(raw).strip().upper() in (
            "1", "TRUE", "S", "SIM", "YES")
        if not continuar:
            logger.info("CONTINUAR_EXECUCAO=%s — encerrando loop.", raw)
        return continuar

    def _verificar_e_inserir_autorizacao(self, autorizacao: Autorizacao) -> bool:
        """Verifica duplicidade e registra a autorização na base de controle RPA.

        Se o mesmo nr_atendimento já foi processado nos últimos 5 minutos
        (STATUS='PENDENTE' ou DT_EXECUCAO recente) → cancela esta autorização.
        Caso contrário → INSERT STATUS='PENDENTE' e retorna True para processar.
        """
        try:
            atendimento_recente = self._db.execute_scalar(
                """SELECT COUNT(*)
                   FROM ROBO_RPA.HOS_AUTORIZACOES
                   WHERE NR_ATENDIMENTO     = :1
                     AND CD_ESTABELECIMENTO = :2
                     AND (
                         STATUS     = 'PENDENTE'
                         OR DT_EXECUCAO >= SYSDATE - INTERVAL '5' MINUTE
                     )""",
                (autorizacao.nr_atendimento, autorizacao.cd_estabelecimento),
            ) or 0
        except Exception as e:
            logger.warning(
                "Erro ao verificar duplicidade NrAtend=%s — continuando: %s",
                autorizacao.nr_atendimento, e,
            )
            return True

        if atendimento_recente:
            logger.warning(
                "Duplicata detectada — NrAtend=%s | Seq=%s — cancelando.",
                autorizacao.nr_atendimento, autorizacao.nr_sequencia,
            )
            self._controle.registrar_log(
                "WARN", "Autorização Cancelada - Duplicada", str(
                    autorizacao.nr_atendimento)
            )
            try:
                self._db.call_procedure(
                    "TASY.ATUALIZAR_AUTORIZACAO_CONVENIO",
                    {
                        "NR_SEQUENCIA_P":        autorizacao.nr_sequencia,
                        "NM_USUARIO_P":          "automacaotasy",
                        "NR_SEQ_ESTAGIO_P":      _NR_STATUS_DUPLICADO,
                        "IE_CONTA_PARTICULAR_P": "N",
                        "IE_CONTA_CONVENIO_P":   "N",
                        "IE_COMMIT_P":           "S",
                    },
                )
            except Exception as e:
                logger.error("Erro ao cancelar duplicata NrSeq=%s: %s",
                             autorizacao.nr_sequencia, e)
            if self._notificador:
                self._notificador.notificar_alerta(
                    f"[{self._config.rpa_script_name}] "
                    f"#NrAtend: {autorizacao.nr_atendimento}/{autorizacao.nr_sequencia} > "
                    f"Duplicata cancelada"
                )
            return False

        self._executar_sql(
            """INSERT INTO ROBO_RPA.HOS_AUTORIZACOES (
                   CONTROLE_EXECUCAO, NR_ATENDIMENTO, NR_SEQUENCIA,
                   DT_AUTORIZACAO, TIPO_AUTORIZACAO, SETOR_ORIGEM,
                   CD_CONVENIO, DS_CONVENIO, COD_CARTERINHA,
                   DT_ENTRADA, STATUS, CD_ESTABELECIMENTO
               ) VALUES (
                   :1, :2, :3, :4, :5, '**',
                   :6, :7, :8, :9, 'PENDENTE', :10
               )""",
            (
                self._controle.id_execucao,
                autorizacao.nr_atendimento,
                autorizacao.nr_sequencia,
                autorizacao.dt_autorizacao,
                autorizacao.tipo_autorizacao,
                autorizacao.cd_convenio,
                autorizacao.ds_convenio or "",
                autorizacao.cod_carterinha or "",
                autorizacao.dt_entrada,
                autorizacao.cd_estabelecimento,
            ),
            "INSERT HOS_AUTORIZACOES PENDENTE",
        )
        return True

    def _buscar_autorizacoes_pendentes(self) -> List[Autorizacao]:
        """Consulta autorizações pendentes no banco de dados."""
        try:
            rows = self._db.execute_query(
                _SQL_AUTORIZACOES_PENDENTES,
                (self._config.cd_estabelecimento,),
            )
            return [Autorizacao.from_row(r, nr_crm=self.nr_crm, cod_prestador=self.cod_prestador) for r in rows]
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
        if not self._verificar_e_inserir_autorizacao(autorizacao):
            return

        try:
            resultado = self._autorizacao.processar(autorizacao)
            if resultado:
                self._atualizar_resultado_banco(autorizacao, resultado)

                if self._notificador:
                    self._notificador.notificar_sucesso(
                        f"[{self._config.rpa_script_name}] "
                        f"#NrAtend: {autorizacao.nr_atendimento} > "
                        f"{resultado.get('status_portal', '')} - "
                        f"{resultado.get('mensagem', '')}"
                    )
                    self._autorizacao.fechar_popup_impressao(autorizacao)

            # manter_sessao após a atualização do banco — evita que uma falha
            # no keep-alive interfira no resultado já gravado.
            self._autorizacao.manter_sessao()

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

        except Exception as e:
            logger.exception(
                "Erro ao processar NrAtend=%s: %s", autorizacao.nr_atendimento, e
            )
            self._controle.registrar_log(
                "ERROR",
                f"Erro ao processar NrAtend={autorizacao.nr_atendimento}: {e}",
                str(autorizacao.nr_atendimento),
            )
            self._atualizar_falha_banco(autorizacao, str(e))
            if self._notificador:
                self._notificador.notificar_erro(
                    f"[{self._config.rpa_script_name}]\n"
                    f"#Falha no script\n"
                    f"NrAtendimento: {autorizacao.nr_atendimento} -\n\n"
                    f"MensagemErro: {e}"
                )

    # ------------------------------------------------------------------
    # Atualização de banco pós-SPSADT
    # ------------------------------------------------------------------

    def _atualizar_resultado_banco(
        self, autorizacao: Autorizacao, resultado: dict
    ) -> None:
        """Despacha para o método correto com base no status retornado pelo portal."""
        status = resultado.get("status_retorno_tasy", 0)
        cod_req = resultado.get("cod_requisicao", "")
        cod_guia = resultado.get("cod_guia", "")
        mensagem = resultado.get("mensagem", "")
        pdfs = resultado.get("pdfs_baixados", [])

        if status == 2:  # CM-Autorizado - WS
            self._registrar_aprovado(autorizacao, cod_req, cod_guia, pdfs)
        elif status == 6:  # CM-Encaminhado Convênio - WS
            self._registrar_em_analise(autorizacao, cod_req, 6)
        elif status == 29:  # CM-Em análise - WS
            self._registrar_em_analise(autorizacao, cod_req, 29, cod_guia)
        elif status == 7:  # CM-Negado - WS
            self._registrar_negado(autorizacao, cod_req)
        else:  # Impedimento (167 ou qualquer outro)
            self._registrar_impedimento(autorizacao, cod_req, mensagem)

    def _registrar_aprovado(
        self,
        autorizacao: Autorizacao,
        cod_requisicao: str,
        cod_guia: str,
        pdfs: list,
    ) -> None:
        """Executa todas as procedures TASY e atualiza RPA para status Aprovado (2)."""
        nr_seq = autorizacao.nr_sequencia
        nr_atend = autorizacao.nr_atendimento

        self._controle.registrar_log("INFO", "Status = 2 - Aprovado",
                                     str(nr_atend))

        # 1. Atualiza campos de guia e senha
        self._executar_sql(
            "BEGIN tasy.RPA_ATUALIZA_AUTORIZACAO_CONV("
            ":1,'automacaotasy',:2,:3,:4,SYSDATE+1); END;",
            (nr_seq, cod_guia, cod_requisicao, cod_guia),
            "RPA_ATUALIZA_AUTORIZACAO_CONV",
        )

        # 2. Atualiza guia principal na entrada única
        self._executar_sql(
            "BEGIN tasy.RPA_ATUALIZA_GUIA_PRINCIPAL(:1,:2); END;",
            (nr_atend, cod_guia),
            "RPA_ATUALIZA_GUIA_PRINCIPAL",
        )

        # 3. Obtém SEQ_TERCEIRO e atualiza evento/autor
        seq_terceiro = ""
        try:
            seq_terceiro = str(
                self._db.execute_scalar(
                    "SELECT SEQ_TERCEIRO FROM tasy.BPM_RELAC_MEDICO "
                    "WHERE NR_ATENDIMENTO = :1",
                    (nr_atend,),
                ) or ""
            )
        except Exception as e:
            logger.warning("Erro ao obter SEQ_TERCEIRO | NrAtend=%s: %s",
                           nr_atend, e)

        self._executar_sql(
            "BEGIN TASY.ATUALIZAR_EVENTO_AUTOR_CONV(:1,:2,:3,:4,:5); END;",
            (5, seq_terceiro, "", "", "automacaotasy"),
            "ATUALIZAR_EVENTO_AUTOR_CONV",
        )

        # 4. Atualiza estágio para 2 (Autorizado)
        self._executar_sql(
            "BEGIN TASY.ATUALIZAR_AUTORIZACAO_CONVENIO("
            ":1,'automacaotasy',2,'N','N','S'); END;",
            (nr_seq,),
            "ATUALIZAR_AUTORIZACAO_CONVENIO(2)",
        )

        # 5. Atualiza autorização TISS
        self._executar_sql(
            "BEGIN TASY.TISS_ATUALIZAR_AUTORIZACAO(:1,'automacaotasy'); END;",
            (nr_seq,),
            "TISS_ATUALIZAR_AUTORIZACAO",
        )

        # 6. Atualiza quantidade de procedimentos
        self._executar_sql(
            "BEGIN TASY.ATUALIZAR_QT_PROC_AUT(:1); END;",
            (nr_seq,),
            "ATUALIZAR_QT_PROC_AUT",
        )

        # 7. Anexa PDF da guia ao Tasy (somente se houve download)
        if pdfs:
            self._anexar_guia_tasy(autorizacao, pdfs)

        # 8. Atualiza base RPA
        self._executar_sql(
            """UPDATE ROBO_RPA.HOS_AUTORIZACOES
               SET STATUS    = 'AUTORIZADO',
                   MENSAGEM  = 'Autorização realizada com sucesso',
                   DT_EXECUCAO  = SYSTIMESTAMP,
                   CD_REQUISICAO = :1,
                   CD_GUIA      = :2,
                   CD_SENHA     = :3
               WHERE NR_SEQUENCIA = :4""",
            (cod_requisicao, cod_guia, cod_guia, nr_seq),
            "UPDATE HOS_AUTORIZACOES AUTORIZADO",
        )
        self._controle.registrar_log(
            "INFO", "Atualizou base RPA", str(nr_atend))

        # 9. Atualiza categoria do plano (apenas Unimed + SPSADT-PRE)
        ds_convenio = autorizacao.ds_convenio or ""
        if "Unimed" in ds_convenio and autorizacao.tipo_autorizacao == "SPSADT-PRE":
            self._atualizar_categoria_unimed(autorizacao, cod_guia)

    def _registrar_em_analise(
        self,
        autorizacao: Autorizacao,
        cod_requisicao: str,
        status: int,
        cod_guia: str = "",
    ) -> None:
        """Atualiza TASY e RPA para status Em Análise (6 ou 29)."""
        nr_seq = autorizacao.nr_sequencia
        nr_atend = autorizacao.nr_atendimento

        # Atualiza estágio no TASY
        self._executar_sql(
            "BEGIN TASY.ATUALIZAR_AUTORIZACAO_CONVENIO("
            ":1,'automacaotasy',:2,'N','N','S'); END;",
            (nr_seq, status),
            f"ATUALIZAR_AUTORIZACAO_CONVENIO({status})",
        )

        # Atualiza base RPA
        self._executar_sql(
            """UPDATE ROBO_RPA.HOS_AUTORIZACOES
               SET STATUS    = 'EM ANÁLISE',
                   MENSAGEM  = 'Em análise pela operadora',
                   DT_EXECUCAO  = SYSTIMESTAMP,
                   CD_REQUISICAO = :1
               WHERE NR_SEQUENCIA = :2""",
            (cod_requisicao, nr_seq),
            f"UPDATE HOS_AUTORIZACOES EM ANÁLISE ({status})",
        )

        # Para status 29 com guia, atualiza campos de guia
        if status == 29:
            cod_guia_efetivo = cod_guia or "0"
            self._executar_sql(
                "BEGIN tasy.RPA_ATUALIZA_AUTORIZACAO_CONV("
                ":1,'automacaotasy',:2,:3,:4,SYSDATE+30); END;",
                (nr_seq, cod_guia_efetivo, cod_requisicao, cod_guia_efetivo),
                "RPA_ATUALIZA_AUTORIZACAO_CONV(29)",
            )

        self._controle.registrar_log("INFO",
                                     f"Em análise ({status}) — base RPA atualizada",
                                     str(nr_atend))

    def _registrar_negado(
        self, autorizacao: Autorizacao, cod_requisicao: str
    ) -> None:
        """Atualiza TASY e RPA para status Negado (7)."""
        nr_seq = autorizacao.nr_sequencia

        self._executar_sql(
            "BEGIN TASY.ATUALIZAR_AUTORIZACAO_CONVENIO("
            ":1,'automacaotasy',7,'N','N','S'); END;",
            (nr_seq,),
            "ATUALIZAR_AUTORIZACAO_CONVENIO(7)",
        )

        self._executar_sql(
            """UPDATE ROBO_RPA.HOS_AUTORIZACOES
               SET STATUS    = 'NEGADO',
                   MENSAGEM  = 'Negado pela operadora',
                   DT_EXECUCAO  = SYSTIMESTAMP,
                   CD_REQUISICAO = :1
               WHERE NR_SEQUENCIA = :2""",
            (cod_requisicao, nr_seq),
            "UPDATE HOS_AUTORIZACOES NEGADO",
        )
        self._controle.registrar_log("INFO", "Negado — base RPA atualizada",
                                     str(autorizacao.nr_atendimento))

    def _registrar_impedimento(
        self, autorizacao: Autorizacao, cod_requisicao: str, mensagem: str
    ) -> None:
        """Atualiza TASY (status 167) e base RPA para Impedimento."""
        self._executar_sql(
            "BEGIN TASY.ATUALIZAR_AUTORIZACAO_CONVENIO("
            ":1,'automacaotasy',167,'N','N','S'); END;",
            (autorizacao.nr_sequencia,),
            "ATUALIZAR_AUTORIZACAO_CONVENIO(167)",
        )

        self._executar_sql(
            """UPDATE ROBO_RPA.HOS_AUTORIZACOES
               SET STATUS    = 'IMPEDIMENTO',
                   MENSAGEM  = :1,
                   DT_EXECUCAO  = SYSTIMESTAMP,
                   CD_REQUISICAO = :2
               WHERE NR_SEQUENCIA = :3""",
            (mensagem, cod_requisicao, autorizacao.nr_sequencia),
            "UPDATE HOS_AUTORIZACOES IMPEDIMENTO",
        )

    def _anexar_guia_tasy(self, autorizacao: Autorizacao, pdfs: list) -> None:
        """Renomeia o PDF, copia para o storage do Tasy e insere registro na tabela."""
        nr_atend = autorizacao.nr_atendimento
        nr_seq = autorizacao.nr_sequencia
        tasy_storage = Path(self._config.caminho_tasy_storage)

        cd_pessoa = ""
        try:
            cd_pessoa = str(
                self._db.execute_scalar(
                    "SELECT MAX(cd_pessoa_pf) FROM TASY.AMH_SING_PESSOA "
                    "WHERE nr_atendimento = :1",
                    (nr_atend,),
                ) or ""
            )
        except Exception as e:
            logger.warning("Erro ao obter cd_pessoa_pf | NrAtend=%s: %s",
                           nr_atend, e)

        for pdf in pdfs:
            pdf_path = Path(pdf)
            random_prefix = "".join(
                random.choices(string.ascii_letters + string.digits, k=10))
            nome_arquivo = (
                f"{random_prefix}_{cd_pessoa}_{nr_atend}_GUIA_SPSADT.pdf")
            novo_caminho = pdf_path.parent / nome_arquivo

            try:
                pdf_path.rename(novo_caminho)
                shutil.copy2(str(novo_caminho), str(tasy_storage))
                logger.info("PDF copiado para Tasy storage: %s | NrAtend=%s",
                            nome_arquivo, nr_atend)
            except Exception as e:
                logger.warning("Erro ao copiar PDF para Tasy storage: %s", e)
                continue

            ds_arquivo = (
                "tasy-storage://INSURANCE_AUTHORIZATION"
                ".f7dbe696-caa7-42c1-be04-0ac9f4e77811"
                f"/{nome_arquivo}?{nome_arquivo}"
            )
            self._executar_sql(
                """INSERT INTO tasy.AUTORIZACAO_CONVENIO_ARQ (
                       DT_ATUALIZACAO_NREC, IE_TIPO_DOCUMENTO_TISS, DS_OBSERVACAO,
                       NM_USUARIO, NR_SEQUENCIA, NM_USUARIO_NREC, IE_ANEXAR_EMAIL,
                       NR_SEQ_TIPO, NR_SEQUENCIA_AUTOR, DS_ARQUIVO, DT_ATUALIZACAO
                   ) VALUES (
                       sysdate,'16',null,'automacaotasy',
                       TASY.AUTORIZACAO_CONVENIO_ARQ_seq.NEXTVAL,
                       'automacaotasy','S',2,:1,:2,sysdate
                   )""",
                (str(nr_seq), ds_arquivo),
                "INSERT AUTORIZACAO_CONVENIO_ARQ",
            )
            self._controle.registrar_log("INFO", "Inseriu Anexo no Tasy",
                                         str(nr_atend))

    def _atualizar_categoria_unimed(
        self, autorizacao: Autorizacao, cod_guia: str
    ) -> None:
        """Determina e atualiza a categoria do plano Unimed com base no prefixo da guia.

        Mapeamento do IBM RPA:
          22... → categoria 1 (Pré-pagamento)
          23... → categoria 2 (Intercâmbio)
          21... → categoria 3 (CO Rio Preto)
        """
        nr_atend = autorizacao.nr_atendimento
        cd_categoria: int | None = None

        if cod_guia.startswith("22"):
            cd_categoria = 1
        elif cod_guia.startswith("23"):
            cd_categoria = 2
        elif cod_guia.startswith("21"):
            cd_categoria = 3

        self._controle.registrar_log(
            "INFO",
            f"Unimed — Categoria [{cd_categoria}] | Guia [{cod_guia}]",
            str(nr_atend),
        )

        if cd_categoria is None:
            logger.info("Categoria Unimed não identificada para guia %s | NrAtend=%s",
                        cod_guia, nr_atend)
            return

        dt_vigencia = (
            autorizacao.dt_inicio_vigencia_eup or autorizacao.dt_entrada
        )
        self._executar_sql(
            """BEGIN
                   TASY.RPA_ATUALIZA_ATEND_CATEGORIA(
                       :1,  -- w_nr_atendimento
                       :2,  -- w_cd_convenio
                       :3,  -- w_cd_categoria_antigo
                       :4,  -- w_dt_inicio_vigencia
                       'automacaotasy',
                       3,   -- p_cd_tipo_acomodacao_novo
                       :5   -- p_cd_categoria_novo
                   );
               END;""",
            (
                autorizacao.nr_atendimento,
                autorizacao.cd_convenio,
                autorizacao.cd_categoria or "",
                dt_vigencia,
                str(cd_categoria),
            ),
            "RPA_ATUALIZA_ATEND_CATEGORIA",
        )

    def _executar_sql(
        self, sql: str, params: tuple, descricao: str = ""
    ) -> None:
        """Executa SQL com log de erro sem interromper o fluxo."""
        try:
            self._db.execute_non_query(sql, params)
            if descricao:
                logger.debug("OK: %s", descricao)
        except Exception as e:
            logger.error("Erro em %s: %s", descricao or "SQL", e)

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

        if self._notificador:
            self._notificador.notificar_erro(
                f"[{self._config.rpa_script_name}]\n"
                f"#Falha no script\n"
                f"NrAtendimento: {autorizacao.nr_atendimento} -\n\n"
                f"MensagemErro: {mensagem}"
            )

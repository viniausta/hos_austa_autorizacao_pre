"""Page Object Model — Tela de SPSADT (PA) — portal Unimed/TASY.

Encapsula todos os seletores e ações da tela de SPSADT, isolando os
detalhes de UI do restante da aplicação (Padrão POM).

Como adicionar um novo passo:
  1. Declare o seletor como constante de classe (_SEL_*).
  2. Implemente o passo como método privado.
  3. Chame o método em `processar()` na ordem correta.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.entities.autorizacao import Autorizacao
from core.exceptions import SpsadtFalhouError
from core.ports.browser_port import BrowserPort

logger = logging.getLogger(__name__)


class SpsadtPage:
    """Representa a tela de SPSADT do portal TASY/Unimed.

    Todos os seletores e a sequência de interação ficam aqui.
    Se a UI mudar, apenas este arquivo precisa ser atualizado.
    """

    # ------------------------------------------------------------------
    # Seletores — navegação inicial até a tela SPSADT
    # ------------------------------------------------------------------

    _SEL_REQUISICAO_AUTORIZACAO = (
        "xpath", "//font[text()='Requisição para autorização']")
    _SEL_REQUISITAR_AUTORIZACAO = (
        "xpath", "//font[text()=' » Requisitar autorização']")
    _SEL_SELECIONAR_TELA = ("id", "ie_tipo_guia")

    # ------------------------------------------------------------------
    # Seletores — rotina "Consultar Beneficiário"
    # ------------------------------------------------------------------

    _SEL_CD_USUARIO_PLANO = ("id", "CD_USUARIO_PLANO")   # campo carteirinha
    # campo nome do beneficiário
    _SEL_NM_BENEFICIARIO = ("id", "NM_SEGURADO")
    # combobox tipo de acomodação
    _SEL_IE_ACOMODACAO = ("id", "ieAcomodacao")
    # botão salvar (popup cadastro)
    _SEL_BTN_SALVAR = ("id", "btnSalvar")

    # ------------------------------------------------------------------
    # Seletores — rotina "Preencher Dados SPSADT"
    # ------------------------------------------------------------------

    _SEL_CD_PRESTADOR = ("id", "cd_prestador")
    _SEL_NR_CRM = ("id", "nr_crm")
    _SEL_CHECK_URGENCIA = ("id", "idCheckUrg")
    _SEL_CARATER_ATENDIMENTO = ("css", "#carater_atend_servico")
    _SEL_TIPO_CONSULTA = ("id", "ie_tipo_consulta_serv")
    _SEL_TIPO_ATENDIMENTO = ("id", "ie_tipo_atendimento")
    _SEL_REGIME_ATENDIMENTO = ("id", "ie_regime_atendimento_servico")
    _SEL_NR_PRESTADOR_ENTRADA = ("id", "NR_PRESTADOR_ENTRADA_S")
    _SEL_INDICACAO_ACIDENTE = ("id", "tp_acidente_servico")
    _SEL_IND_CLINICA = ("id", "ds_ind_clinica_servico")
    _SEL_OBSERVACAO = ("id", "ds_observacao_servico")
    _SEL_MOTIVO_TOKEN = ("id", "cd_ausencia_val_benef_tiss")

    def __init__(self, browser: BrowserPort, dev_mode: bool = False) -> None:
        self._browser = browser
        self._dev_mode = dev_mode

    # ------------------------------------------------------------------
    # Ponto de entrada público — chamado pelo use case
    # ------------------------------------------------------------------

    def processar(self, autorizacao: Autorizacao) -> None:
        """Executa o fluxo completo de SPSADT para um atendimento.

        Args:
            autorizacao: Entidade com os dados do atendimento a autorizar.

        Raises:
            SpsadtFalhouError: Se qualquer etapa do fluxo falhar.
        """
        logger.info(
            "Iniciando SPSADT — NrAtend=%s | Convenio=%s | Tipo=%s",
            autorizacao.nr_atendimento,
            autorizacao.cd_convenio,
            autorizacao.tipo_autorizacao,
        )

        try:

            # Acessa a tela de SPSADT a partir do menu principal, garantindo que a página carregou
            self._acessar_tela_spsadt()
            # Consulta e valida o beneficiário pela carteirinha
            if not self._consultar_beneficiario(autorizacao):
                return False
            # Preenche os campos do formulário SPSADT
            self._preencher_dados_spsadt(autorizacao)

        except SpsadtFalhouError:
            raise
        except Exception as e:
            raise SpsadtFalhouError(
                f"Falha inesperada no SPSADT NrAtend={autorizacao.nr_atendimento}: {e}"
            ) from e

        logger.info("SPSADT concluído — NrAtend=%s",
                    autorizacao.nr_atendimento)

    def _acessar_tela_spsadt(self) -> None:
        # 1. Clica em "Requisição para autorização"
        with self._browser.frame_do_elemento(*self._SEL_REQUISICAO_AUTORIZACAO, timeout=10):
            self._browser.click_elemento(
                *self._SEL_REQUISICAO_AUTORIZACAO, timeout=10)

        # 2. Clica em "» Requisitar autorização"
        with self._browser.frame_do_elemento(*self._SEL_REQUISITAR_AUTORIZACAO, timeout=10):
            self._browser.click_elemento(
                *self._SEL_REQUISITAR_AUTORIZACAO, timeout=10)

        # 3. Aguarda tela carregar e seleciona tipo SPSADT (value="2")
        carregou = self._aguardar_tela_carregar(self._SEL_SELECIONAR_TELA)
        if not carregou:
            raise SpsadtFalhouError(
                "Tela de SPSADT não carregou após clicar em 'Requisitar autorização'."
            )

        with self._browser.frame_do_elemento(*self._SEL_SELECIONAR_TELA, timeout=10):
            self._browser.selecionar_opcao(
                *self._SEL_SELECIONAR_TELA, "2", por="value", timeout=10)

    def _consultar_beneficiario(self, autorizacao: Autorizacao) -> bool:
        """Preenche a carteirinha e valida o beneficiário no sistema.

        Fluxo:
          1. Preenche CD_USUARIO_PLANO com carteirinha (17 dígitos, zero-padded)
          2. Pressiona TAB para disparar validação do plano
          3. Trata alertas imediatos (beneficiário inativo / não cadastrado)
          4. Aguarda abertura da aba "Cadastro Beneficiário"
          5. Lê NM_SEGURADO diretamente dessa aba (driver já posicionado nela)
          6. Trata o popup (acomodação, salva, fecha aba)

        Raises:
            SpsadtFalhouError: Beneficiário inativo, não cadastrado ou aba não abriu.
        """
        cod_carterinha = str(autorizacao.cod_carterinha or "").zfill(17)
        logger.info(
            "Consultando beneficiário — Carteirinha=%s | NrAtend=%s",
            cod_carterinha,
            autorizacao.nr_atendimento,
        )

        # Preenche carteirinha e dispara validação com TAB
        with self._browser.frame_do_elemento(*self._SEL_CD_USUARIO_PLANO, timeout=15):
            self._browser.definir_valor(
                *self._SEL_CD_USUARIO_PLANO, cod_carterinha)
            self._browser.enviar_tecla(*self._SEL_CD_USUARIO_PLANO, "TAB")

        # Verifica alerta imediato após TAB (beneficiário inativo / não cadastrado)
        texto_alerta = self._browser.tratar_alerta(aceitar=True, timeout=2)
        if texto_alerta:
            self._tratar_alerta_beneficiario(
                texto_alerta, cod_carterinha, autorizacao.nr_atendimento
            )

        with self._browser.frame_do_elemento(*self._SEL_NM_BENEFICIARIO, timeout=5):
            nome_beneficiario = self._browser.obter_valor(
                *self._SEL_NM_BENEFICIARIO, timeout=5).strip()

        if not nome_beneficiario:
            if not self._tratar_popup_cadastro(autorizacao):
                return False
        return True

    def _tratar_alerta_beneficiario(
        self, texto: str, cod_carterinha: str, nr_atendimento: int
    ) -> None:
        """Analisa o texto do alerta e lança SpsadtFalhouError com mensagem adequada.

        Alertas enviados para: (status 167 = CM-Pendente de Intervenção):
          - "Sem permissão para atendimento de beneficiário com status: Inativo."
          - "Atenção: Não existe beneficiário cadastrado com a carteirinha"
        """
        if "Sem permissão para atendimento de beneficiário com status: Inativo" in texto:
            logger.info(
                "Beneficiário inativo — NrAtend=%s | Alerta: %s", nr_atendimento, texto
            )
            raise SpsadtFalhouError(
                f"Beneficiário inativo — NrAtend={nr_atendimento}: {texto}"
            )

        if "Não existe beneficiário cadastrado com a carteirinha" in texto:
            logger.info(
                "Beneficiário não cadastrado — Carteirinha=%s | NrAtend=%s",
                cod_carterinha, nr_atendimento,
            )
            raise SpsadtFalhouError(
                f"Beneficiário não cadastrado — Carteirinha={cod_carterinha} "
                f"| NrAtend={nr_atendimento}: {texto}"
            )

        # Alerta não mapeado — loga e continua (pode ser aviso não crítico)
        logger.warning(
            "Alerta não mapeado após TAB: '%s' | NrAtend=%s", texto, nr_atendimento
        )

    def _tratar_popup_cadastro(self, autorizacao: Autorizacao) -> bool:
        """Trata a aba 'Cadastro Beneficiário', preenchendo acomodação e salvando.


        Returns:
            True  — cadastro salvo sem alerta (sucesso).
            False — alerta após salvar ou erro inesperado.
        """
        try:
            # Aguarda a aba "Cadastro Beneficiário" abrir e switch para ela
            encontrou_popup = self._browser.localizar_ou_anexar_aba(
                titulo_contem="Cadastro Beneficiário", timeout=10
            )
            # Confirma que o driver está na aba correta antes de ler
            titulo_atual = self._browser.obter_titulo_aba()
            logger.debug("Aba ativa após switch: '%s'", titulo_atual)

            if not encontrou_popup:
                raise SpsadtFalhouError(
                    f"Aba 'Cadastro Beneficiário' não abriu — NrAtend={autorizacao.nr_atendimento} "
                    f"| Carteirinha={autorizacao.cod_carterinha} | Status: Pendente de Intervenção"
                )

            # Verifica e preenche acomodação se o campo existir e estiver vazio
            if self._browser.verificar_existencia_elemento(*self._SEL_IE_ACOMODACAO, timeout=2):
                with self._browser.frame_do_elemento(*self._SEL_IE_ACOMODACAO, timeout=5):
                    valor_atual = self._browser.obter_atributo(
                        *self._SEL_IE_ACOMODACAO, "value", timeout=3
                    )
                    if not valor_atual:
                        acomodacao = self._determinar_acomodacao(
                            autorizacao.ds_tipo_acomodacao)
                        self._selecionar_acomodacao(acomodacao)
                        logger.info(
                            "Acomodação definida: '%s' | NrAtend=%s",
                            acomodacao,
                            autorizacao.nr_atendimento,
                        )

            # Salva o cadastro e trata possível alerta
            self._browser.click_elemento(*self._SEL_BTN_SALVAR, timeout=5)
            texto_alerta = self._browser.tratar_alerta(
                aceitar=False, timeout=3)
            self._browser.fechar_aba()

            if texto_alerta:
                logger.warning(
                    "Alerta ao salvar cadastro: '%s' | NrAtend=%s",
                    texto_alerta, autorizacao.nr_atendimento,
                )
                self._tratar_alerta_beneficiario(
                    texto_alerta, str(autorizacao.cod_carterinha or "").zfill(
                        17), autorizacao.nr_atendimento)
                return False

            return True  # salvo sem alerta = sucesso

        except SpsadtFalhouError:
            raise
        except Exception as e:
            logger.warning(
                "Erro ao tratar popup de cadastro — NrAtend=%s: %s",
                autorizacao.nr_atendimento, e,
            )
            try:
                self._browser.fechar_aba()
            except Exception:
                pass
            return False

    def _preencher_dados_spsadt(self, autorizacao: Autorizacao) -> None:
        """Preenche os campos principais do formulário SPSADT.

        O frame do formulário é localizado uma única vez pelo primeiro campo;
        todos os demais campos são preenchidos no mesmo contexto sem reposicionar.
        O `finally` garante que o driver volta ao documento raiz ao sair.

        Sequência migrada do IBM RPA:
          1.  Prestador + TAB
          2.  CRM + TAB
          3.  Checkbox urgência (se ie_consulta_emergencia == 'S')
          4.  Caráter de atendimento
          5.  Tipo de consulta (se informado)
          6.  Tipo de atendimento
          7.  Regime de atendimento
          8.  Prestador de entrada + TAB
          9.  Indicação de acidente
          10. Indicação clínica e observação (somente convenio Austa)
          11. Motivo ausência token por value (somente convenio Austa) + TAB
          12. DEV mode + Unimed → loga simulação e retorna sem submeter
        """
        ds_convenio = autorizacao.ds_convenio or ""

        # Localiza o frame do formulário uma única vez pelo primeiro campo
        if not self._browser.alternar_frame_com_elemento(*self._SEL_CD_PRESTADOR, timeout=15):
            raise SpsadtFalhouError(
                f"Frame do formulário SPSADT não encontrado | NrAtend={autorizacao.nr_atendimento}"
            )

        try:
            # 1. Prestador
            self._browser.definir_valor(
                *self._SEL_CD_PRESTADOR, str(autorizacao.cd_prestador or ""))
            self._browser.enviar_tecla(*self._SEL_CD_PRESTADOR, "TAB")

            # 2. CRM
            self._browser.definir_valor(
                *self._SEL_NR_CRM, str(autorizacao.nr_crm or ""))
            self._browser.enviar_tecla(*self._SEL_NR_CRM, "TAB")

            # 3. Checkbox urgência (opcional)
            if str(autorizacao.ie_consulta_emergencia or "").upper() == "S":
                self._browser.click_elemento(*self._SEL_CHECK_URGENCIA)
                logger.info("Consulta de urgência marcada | NrAtend=%s",
                            autorizacao.nr_atendimento)

            # 4. Caráter de atendimento
            self._browser.selecionar_opcao(
                *self._SEL_CARATER_ATENDIMENTO, autorizacao.ds_carater_atendimento or "")

            # 5. Tipo de consulta (opcional)
            if autorizacao.ie_tipo_consulta:
                self._browser.selecionar_opcao(
                    *self._SEL_TIPO_CONSULTA, autorizacao.ie_tipo_consulta)

            # 6. Tipo de atendimento
            self._browser.selecionar_opcao(
                *self._SEL_TIPO_ATENDIMENTO, autorizacao.ie_tipo_atendimento or "")

            # 7. Regime de atendimento
            self._browser.selecionar_opcao(
                *self._SEL_REGIME_ATENDIMENTO, autorizacao.ie_regime_atendimento or "")

            # 8. Prestador de entrada + TAB
            self._browser.definir_valor(
                *self._SEL_NR_PRESTADOR_ENTRADA, str(autorizacao.cd_prestador or ""))
            self._browser.enviar_tecla(*self._SEL_NR_PRESTADOR_ENTRADA, "TAB")

            # 9. Indicação de acidente
            self._browser.selecionar_opcao(
                *self._SEL_INDICACAO_ACIDENTE, autorizacao.tp_acidente or "")

            # 10 + 11. Campos exclusivos do convenio Austa
            if "Austa" in ds_convenio:
                self._browser.definir_valor(
                    *self._SEL_IND_CLINICA, autorizacao.ds_ind_clinica or "")
                self._browser.definir_valor(
                    *self._SEL_OBSERVACAO, autorizacao.ds_observacao or "")
                self._browser.selecionar_opcao(
                    *self._SEL_MOTIVO_TOKEN,
                    autorizacao.cd_ausencia_val_benef or "",
                    por="value",
                )
                self._browser.enviar_tecla(*self._SEL_MOTIVO_TOKEN, "TAB")

            # 12. DEV mode — simula aprovação sem submeter (somente Unimed)
            if self._dev_mode and ds_convenio == "Unimed":
                logger.info(
                    "DEV mode — Simulando aprovação Unimed | NrAtend=%s",
                    autorizacao.nr_atendimento,
                )
                return

            logger.info("Dados SPSADT preenchidos | NrAtend=%s",
                        autorizacao.nr_atendimento)

        finally:
            self._browser.sair_frame()

    def _selecionar_acomodacao(self, acomodacao: str) -> None:
        """Seleciona o tipo de acomodação. Tenta 'Apartamento' e, se indisponível, 'Individual'."""
        try:
            self._browser.selecionar_opcao(
                *self._SEL_IE_ACOMODACAO, acomodacao)
        except Exception:
            if acomodacao == "Apartamento":
                logger.debug(
                    "'Apartamento' não disponível — tentando 'Individual'")
                self._browser.selecionar_opcao(
                    *self._SEL_IE_ACOMODACAO, "Individual")
            else:
                raise

    def _determinar_acomodacao(self, ds_tipo_acomodacao: Optional[str]) -> str:
        """Determina o tipo de acomodação com base na descrição do plano."""
        if ds_tipo_acomodacao and "Apartamento" in ds_tipo_acomodacao:
            return "Apartamento"
        return "Enfermaria"

    # ------------------------------------------------------------------
    # Utilitários internos
    # ------------------------------------------------------------------

    def _aguardar_tela_carregar(self, seletor: tuple[str, str]) -> None:
        """Aguarda o elemento indicador aparecer, sinalizando que a tela carregou."""
        encontrou = self._browser.alternar_frame_com_elemento(
            *seletor, timeout=15)
        if not encontrou:
            raise SpsadtFalhouError(
                f"Tela de SPSADT não carregou dentro do timeout esperado. Seletor: {seletor}"
            )
        logger.debug(f"Tela de SPSADT carregada. Seletor: {seletor}")

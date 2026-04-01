"""Modelos Pydantic para a API de autorizações — integração MAEZO (CIB Seven).

Estrutura FHIR-inspired:
    cobertura   → FHIR Coverage  (carteirinha, convênio)
    prestador   → FHIR Practitioner (CRM, cod_prestador)
    atendimento → FHIR Encounter  (nr_atendimento, estabelecimento, datas, tipo)
    procedimentos → FHIR ServiceRequest[] (códigos TUSS)
    diagnoses   → FHIR Condition[] (CID-10)

O RPA usa esses dados para preencher o portal Unimed (SPSADT) sem consultar
o Oracle para dados de entrada. Oracle é usado apenas para gravar o resultado
via procedures TASY.
"""
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Sub-modelos FHIR-inspired
# ---------------------------------------------------------------------------


class CoberturaFhir(BaseModel):
    """FHIR Coverage — dados do plano/convênio do beneficiário."""

    model_config = ConfigDict(extra="ignore")

    carteirinha: str = Field(..., description="Coverage.subscriberId (17 dígitos zero-padded)")
    cd_convenio: int  = Field(..., description="Coverage.class[group].value (27 = Unimed PA)")
    ds_convenio: str  = Field(..., description="Coverage.payor[0].display ('Unimed')")


class PrestadorFhir(BaseModel):
    """FHIR Practitioner + PractitionerRole — médico/prestador."""

    model_config = ConfigDict(extra="ignore")

    cd_prestador: str = Field(..., description="PractitionerRole.identifier[cd-prestador].value")
    nr_crm: str       = Field(..., description="Practitioner.identifier[crm].value")


class AtendimentoFhir(BaseModel):
    """FHIR Encounter — dados do atendimento hospitalar."""

    model_config = ConfigDict(extra="ignore")

    nr_atendimento: int         = Field(..., description="Encounter.identifier[tasy-nr-atendimento].value")
    nr_sequencia: int           = Field(..., description="Chave Oracle interna — necessária para procedures TASY")
    cd_estabelecimento: int     = Field(4,   description="Encounter.serviceProvider.identifier[cd-est].value")
    dt_entrada: str             = Field(..., description="Encounter.period.start (ISO 8601)")
    ds_carater_atendimento: str = Field(..., description="Encounter.priority.text ('Urgência/Emergência')")
    ie_consulta_emergencia: str = Field(..., description="Encounter.priority.code → 'True'/'False'")
    ie_tipo_consulta: str       = Field(..., description="Tipo de consulta ('Primeira consulta')")
    ie_tipo_atendimento: str    = Field(..., description="Encounter.type[0].text ('Consulta')")
    ie_regime_atendimento: str  = Field(..., description="Encounter.hospitalization.admitSource.text ('Pronto Socorro')")
    tp_acidente: str            = Field(..., description="Encounter.extension[tipo-acidente] ('Não acidente')")
    ds_ind_clinica: str         = Field("",  description="Portal Austa — clínica indicada")
    ds_observacao: str          = Field("",  description="Encounter.text.div")
    cd_ausencia_val_benef: str  = Field("",  description="Motivo ausência token beneficiário")


class ProcedimentoFhir(BaseModel):
    """FHIR ServiceRequest — procedimento a autorizar."""

    model_config = ConfigDict(extra="ignore")

    code: str      = Field(..., description="ServiceRequest.code.coding[tuss].code")
    display: str   = Field("",  description="ServiceRequest.code.coding[tuss].display")
    quantity: int  = Field(1,   description="ServiceRequest.quantity.value")
    category: str  = Field("",  description="ServiceRequest.category.text")


# ---------------------------------------------------------------------------
# Request / Response principais
# ---------------------------------------------------------------------------


class AutorizacaoFhirRequest(BaseModel):
    """Payload completo enviado pelo MAEZO para iniciar uma autorização.

    Todos os dados necessários para preencher o portal Unimed (SPSADT)
    são enviados pelo orquestrador. Campos extras são ignorados silenciosamente.
    """

    model_config = ConfigDict(extra="ignore")

    process_instance_id: str = Field(..., description="ID da instância no CIB Seven (correlação do callback)")
    message_name: str        = Field("AuthorizationCompleted", description="Nome da mensagem Camunda (receiveTask no BPMN)")
    rpa_type: str            = Field("autorizacao_pa", description="Tipo de RPA ('autorizacao_pa' | 'autorizacao_cirurgia' | 'autorizacao_exames')")
    tenant_id: str           = Field("",  description="Tenant do processo BPMN")

    cobertura: CoberturaFhir
    prestador: PrestadorFhir
    atendimento: AtendimentoFhir
    procedimentos: list[ProcedimentoFhir]
    diagnoses: list[str] = Field(default_factory=list, description="CID-10 codes")


class AutorizacaoAceita(BaseModel):
    """Resposta 202 — indica que a solicitação foi aceita e está sendo processada."""

    status: str = "accepted"
    nr_sequencia: int

"""Entidade de domínio — Autorização de PA (Pronto Atendimento)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Autorizacao:
    """Representa uma solicitação de autorização de internação/PA.

    Campos mapeados diretamente da view tasy.BPM_AUTORIZACOES_V.
    """

    nr_atendimento: int
    nr_sequencia: int
    cd_convenio: int
    cd_estabelecimento: int
    cod_carterinha: Optional[str] = None
    cd_categoria: Optional[str] = None
    tipo_autorizacao: Optional[str] = None
    ds_tipo_acomodacao: Optional[str] = None
    dt_entrada: Optional[datetime] = None
    dt_autorizacao: Optional[datetime] = None
    dt_inicio_vigencia_eup: Optional[datetime] = None

    # Campos do formulário SPSADT
    ds_convenio: Optional[str] = None
    cod_prestador: Optional[str] = None
    nr_crm: Optional[str] = None
    ie_consulta_emergencia: Optional[str] = None   # 'S' / 'N'
    ds_carater_atendimento: Optional[str] = None
    ie_tipo_consulta: Optional[str] = None
    ie_tipo_atendimento: Optional[str] = None
    ie_regime_atendimento: Optional[str] = None
    tp_acidente: Optional[str] = None
    ds_ind_clinica: Optional[str] = None
    ds_observacao: Optional[str] = None
    cd_ausencia_val_benef: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any], nr_crm: Optional[str] = None, cod_prestador: Optional[str] = None) -> "Autorizacao":
        """Constrói uma Autorizacao a partir de um dicionário de resultado SQL."""
        return cls(
            nr_crm=nr_crm,
            cod_prestador=cod_prestador,
            nr_atendimento=row["nr_atendimento"],
            nr_sequencia=row["nr_sequencia"],
            cd_convenio=row["cd_convenio"],
            cd_estabelecimento=row["cd_estabelecimento"],
            cod_carterinha=row.get("cod_carterinha"),
            cd_categoria=row.get("cd_categoria"),
            tipo_autorizacao="SPSADT-PRE",
            ds_tipo_acomodacao=row.get("de_tipo_acomodacao"),
            dt_entrada=row.get("dt_entrada"),
            dt_autorizacao=row.get("dt_autorizacao"),
            dt_inicio_vigencia_eup=row.get("dt_inicio_vigencia_eup"),
            ds_convenio=row.get("ds_convenio"),
            ie_consulta_emergencia="True",
            ds_carater_atendimento="Urgência/Emergência",
            ie_tipo_consulta="Primeira consulta",
            ie_tipo_atendimento="Consulta",
            ie_regime_atendimento="Pronto Socorro",
            tp_acidente="Não acidente",
            ds_ind_clinica=row.get("ds_ind_clinica"),
            ds_observacao=row.get("ds_observacao"),
            cd_ausencia_val_benef=row.get("cd_ausencia_val_benef"),
        )

    def __str__(self) -> str:
        return (
            f"Autorizacao(nr_atendimento={self.nr_atendimento}, "
            f"nr_sequencia={self.nr_sequencia}, "
            f"cd_convenio={self.cd_convenio})"
        )

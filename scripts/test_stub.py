"""Script de teste do fluxo completo RPA → Callback (payload FHIR-inspired).

Envia uma requisição de autorização com todos os dados do atendimento
para a API do RPA e monitora o callback recebido pelo stub do CIB Seven.

Pré-requisitos:
    docker compose -f docker-compose.yml -f docker-compose.stub.yml up --build

Uso:
    python scripts/test_stub.py [nr_sequencia] [nr_atendimento]

Exemplo:
    python scripts/test_stub.py 98765 316211
"""
from __future__ import annotations

import sys
import time

import httpx

RPA_URL  = "http://localhost:8000"
STUB_URL = "http://localhost:9000"


def aguardar_api(url: str, nome: str, tentativas: int = 20) -> None:
    print(f"⏳ Aguardando {nome} ({url}/health)...")
    for _ in range(tentativas):
        try:
            r = httpx.get(f"{url}/health", timeout=3)
            if r.status_code == 200:
                print(f"✅ {nome} está no ar.")
                return
        except Exception:
            pass
        time.sleep(3)
    print(f"❌ {nome} não respondeu. Verifique o Docker.")
    sys.exit(1)


def limpar_callbacks() -> None:
    httpx.delete(f"{STUB_URL}/callbacks", timeout=5)
    print("🧹 Callbacks anteriores limpos.")


def enviar_autorizacao(nr_sequencia: int, nr_atendimento: int) -> dict:
    """Envia payload FHIR-inspired completo para o RPA."""
    process_instance_id = f"stub-proc-{nr_sequencia}"

    payload = {
        "process_instance_id": process_instance_id,
        "message_name": "rpa_authorization_result",
        "rpa_type": "autorizacao_pa",
        "tenant_id": "HOSPITAL_A",
        # FHIR Coverage — convênio e carteirinha
        "cobertura": {
            "carteirinha": "00123456789012345",
            "cd_convenio": 27,
            "ds_convenio": "Unimed",
        },
        # FHIR Practitioner — médico
        "prestador": {
            "cd_prestador": "110020",
            "nr_crm": "12345",
        },
        # FHIR Encounter — atendimento
        "atendimento": {
            "nr_atendimento": nr_atendimento,
            "nr_sequencia": nr_sequencia,
            "cd_estabelecimento": 4,
            "dt_entrada": "2026-03-24T10:00:00",
            "ds_carater_atendimento": "Urgência/Emergência",
            "ie_consulta_emergencia": "True",
            "ie_tipo_consulta": "Primeira consulta",
            "ie_tipo_atendimento": "Consulta",
            "ie_regime_atendimento": "Pronto Socorro",
            "tp_acidente": "Não acidente",
            "ds_ind_clinica": "",
            "ds_observacao": "",
            "cd_ausencia_val_benef": "",
        },
        # FHIR ServiceRequest[] — procedimentos
        "procedimentos": [
            {"code": "10101012", "display": "Consulta PA", "quantity": 1, "category": "consulta"},
        ],
        # FHIR Condition[] — diagnósticos CID-10
        "diagnoses": ["K35"],
    }

    print(f"\n📤 Enviando payload FHIR para o RPA...")
    print(f"   process_instance  : {process_instance_id}")
    print(f"   nr_sequencia      : {nr_sequencia}")
    print(f"   nr_atendimento    : {nr_atendimento}")
    print(f"   carteirinha       : {payload['cobertura']['carteirinha']}")
    print(f"   convenio          : {payload['cobertura']['ds_convenio']}")

    r = httpx.post(f"{RPA_URL}/api/v1/authorize", json=payload, timeout=10)
    r.raise_for_status()

    resp = r.json()
    print(f"✅ RPA aceitou: {resp}  (HTTP {r.status_code})")
    return resp


def aguardar_callback(process_instance_id: str, timeout_s: int = 300) -> dict | None:
    print(f"\n⏳ Aguardando callback (timeout: {timeout_s}s)...")
    inicio = time.time()

    while time.time() - inicio < timeout_s:
        try:
            r = httpx.get(f"{STUB_URL}/callbacks/ultimo", timeout=5)
            data = r.json()
            if data.get("process_instance_id") == process_instance_id:
                return data
        except Exception:
            pass
        time.sleep(10)
        print(f"   ... {int(time.time() - inicio)}s aguardando RPA processar")

    return None


def main() -> None:
    nr_sequencia   = int(sys.argv[1]) if len(sys.argv) > 1 else 99999
    nr_atendimento = int(sys.argv[2]) if len(sys.argv) > 2 else 316211

    aguardar_api(RPA_URL,  "RPA API")
    aguardar_api(STUB_URL, "Stub CIB Seven")
    limpar_callbacks()

    enviar_autorizacao(nr_sequencia, nr_atendimento)

    process_instance_id = f"stub-proc-{nr_sequencia}"
    callback = aguardar_callback(process_instance_id)

    sep = "=" * 60
    print(f"\n{sep}")
    if callback:
        v = callback.get("variables", {})
        status = v.get("resultado", "?")
        emoji = {"2": "✅ APROVADO", "6": "🔄 EM ANÁLISE", "7": "❌ NEGADO"}.get(
            status, f"⚠️  STATUS {status}"
        )
        print(f"🎉 CALLBACK RECEBIDO — {emoji}")
        print(f"   resultado (TASY)  : {v.get('resultado')}")
        print(f"   mensagem          : {v.get('mensagem')}")
        print(f"   cod_guia          : {v.get('cod_guia')}")
        print(f"   cod_requisicao    : {v.get('cod_requisicao')}")
        print(f"   recebido em       : {callback.get('received_at')}")
    else:
        print("❌ Timeout — callback não chegou.")
        print("   Verifique: docker compose logs -f rpa")
        print("   VNC:       http://localhost:7900")
    print(sep)


if __name__ == "__main__":
    main()

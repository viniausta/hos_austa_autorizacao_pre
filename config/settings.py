"""Configurações imutáveis do robô RPA carregadas de variáveis de ambiente.

Uso:
    from config.settings import Settings
    config = Settings.from_env()
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Configurações imutáveis do robô. Use Settings.from_env() para instanciar."""

    # Infraestrutura de ambiente
    caminho_padrao: Path
    dev_mode: bool

    # Banco de dados Oracle
    db_user: str
    db_password: str
    db_host: str
    db_port: str
    db_service: str

    # Identificadores do projeto RPA
    id_unidade: int
    id_projeto: int
    cd_estabelecimento: int
    cod_prestador: int
    unidade: str
    projeto: str
    rpa_script_name: str
    username: str

    # Credenciais do sistema TASY
    usuario_tasy: str
    senha_tasy: str

    # Rede/anexos
    caminho_chrome_driver: str
    caminho_rede_anexo: str
    senha_rede_anexo: str
    caminho_backup_guia: str   # destino de cópia do PDF da Guia TISS
    caminho_tasy_storage: str  # diretório lido pelo Tasy para anexo da guia

    # Notificações Zoho Cliq (OAuth2)
    zoho_client_id: str
    zoho_client_secret: str
    zoho_refresh_token: str
    cliq_canal_normal: str     # Chat ID para alertas/sucesso/mensagens gerais
    cliq_canal_erro: str       # Chat ID dedicado a erros

    @classmethod
    def from_env(cls) -> "Settings":
        """Constrói Settings a partir das variáveis de ambiente (.env ou sistema)."""
        lista_oracle = os.environ.get("AUSTA_BD_ORACLE", "")
        host, port, service = "", "", ""
        if lista_oracle:
            parts = lista_oracle.split(",")
            host = parts[0] if len(parts) > 0 else ""
            port = parts[1] if len(parts) > 1 else ""
            service = parts[2] if len(parts) > 2 else ""

        return cls(
            caminho_padrao=Path(os.environ.get("CAMINHO_PADRAO", ".")),
            dev_mode=os.environ.get(
                "DEV", "False").lower() in ("1", "true", "yes"),
            db_user=os.environ.get("BD_USUARIO", ""),
            db_password=os.environ.get("BD_SENHA", ""),
            db_host=host,
            db_port=port,
            db_service=service,
            cod_prestador=int(os.environ.get("COD_PRESTADOR", "0")),
            id_unidade=int(os.environ.get("ID_UNIDADE", "0")),
            id_projeto=int(os.environ.get("ID_PROJETO", "0")),
            cd_estabelecimento=int(os.environ.get("CD_ESTABELECIMENTO", "4")),
            unidade=os.environ.get("UNIDADE", ""),
            projeto=os.environ.get("PROJETO", ""),
            rpa_script_name=os.environ.get("RPA_SCRIPT_NAME", ""),
            username=os.environ.get("USERNAME", ""),
            usuario_tasy=os.environ.get("USUARIO_TASY", ""),
            senha_tasy=os.environ.get("SENHA_TASY", ""),
            caminho_chrome_driver=os.environ.get("CAMINHO_CHROME_DRIVER", ""),
            caminho_rede_anexo=os.environ.get("CAMINHO_REDE_ANEXO", ""),
            senha_rede_anexo=os.environ.get("SENHA_REDE_ANEXO", ""),
            caminho_backup_guia=os.environ.get("CAMINHO_BACKUP_GUIA", ""),
            caminho_tasy_storage=os.environ.get("CAMINHO_TASY_STORAGE", ""),
            zoho_client_id=os.environ.get("ZOHO_CLIENT_ID", ""),
            zoho_client_secret=os.environ.get("ZOHO_CLIENT_SECRET", ""),
            zoho_refresh_token=os.environ.get("ZOHO_REFRESH_TOKEN", ""),
            cliq_canal_normal=os.environ.get("CLIQ_CANAL_NORMAL", ""),
            cliq_canal_erro=os.environ.get("CLIQ_CANAL_ERRO", ""),
        )

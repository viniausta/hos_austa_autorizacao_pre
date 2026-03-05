# Projeto: hos_austa_autorizacaopre

## Arquitetura
Clean Architecture / SOLID. Camadas: core → application → infrastructure → main.py

## Arquivos-chave
- `main.py` — composição de dependências e entry point
- `config/settings.py` — Settings dataclass frozen, carregada via `Settings.from_env()`
- `application/use_cases/processar_autorizacao.py` — caso de uso principal
- `application/services/controle_execucao_service.py` — logs e controle de execução no Oracle
- `infrastructure/notifications/cliq_notificador.py` — notificador Zoho Cliq (OAuth2)
- `infrastructure/database/oracle_client.py` — acesso Oracle
- `core/ports/notificador_port.py` — Protocol de notificação

## Notificador Zoho Cliq
- Usa OAuth2: `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`
- Dois canais: `CLIQ_CANAL_NORMAL` e `CLIQ_CANAL_ERRO`
- DEV mode (`DEV=True`) suprime envio completamente
- Endpoint: `https://cliq.zoho.com/api/v2/chats/{canal_id}/message`
- Auth header: `Zoho-oauthtoken {access_token}`
- Notificador só instanciado se todas as 5 credenciais estiverem preenchidas

## .env.example — variáveis Cliq
```
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REFRESH_TOKEN=
CLIQ_CANAL_NORMAL=
CLIQ_CANAL_ERRO=
```

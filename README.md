# Autorizações PA

Arquivos:
- `comandos.py`: implementa o controlador e métodos equivalentes aos comandos RPA.
- `main.py`: runner central da automação.
- `requirements.txt`: dependências sugeridas.

Como executar (Windows PowerShell):

# Projeto: Automação de Autorizações PA 

Este repositório contém um conjunto de utilitários para automação de tarefas
usando Selenium (controlador em `comandos.py`) e integração com um banco Oracle
via `oracledb`. O código principal de execução da automação está em
`processamento.py` e o runner central em `main.py`.

Visão geral dos arquivos
- `comandos.py` — `WebController` (wrapper Selenium) e `DBClient` (wrapper oracledb).
- `processamento.py` — lógica de orquestração do robô (fluxos, chamadas ao DB e navegador).
- `main.py` — runner central que inicializa `Config`, `DBClient` e `RepasseAutomation`.
- `requirements.txt` — dependências Python sugeridas.

Requisitos
- Python 3.11+ (o projeto foi testado em 3.13).
- Windows (instruções abaixo usam PowerShell). Outros OSs podem precisar de ajustes.
- Navegador Chrome/Edge/Firefox instalado (para uso com Selenium).
- `chromedriver` / `msedgedriver` / `geckodriver` compatível com a versão do navegador
	(ou usar gerenciador de drivers).
- Para conectar ao Oracle: `oracledb` (pode requerer Oracle Instant Client dependendo do modo).

Instalação — ambiente virtual e dependências

No PowerShell, na raiz do projeto:

```powershell
# 1) criar e ativar venv (faça apenas se ainda não tiver .venv)
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\.venv\Scripts\Activate.ps1

# 2) atualizar pip e instalar dependências
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configurar variáveis de ambiente (ou `.env`)

O projeto lê algumas variáveis do ambiente via `Config.from_env()` em
`processamento.py`. Para testes locais você pode criar um arquivo `.env` na
raiz com conteúdo como:

```ini
DEV=True
AUSTA_BD_ORACLE_DEV=host.example.com,1521,ORCL
BD_USUARIO=my_user
BD_SENHA=my_password
ID_UNIDADE=1001
ID_PROJETO=3
USERNAME=my_user
```

O módulo já tenta carregar `.env` se `python-dotenv` estiver instalado.

Drivers do navegador (Selenium)

- Baixe o `chromedriver.exe` que corresponde à sua versão do Chrome: https://chromedriver.chromium.org/
- Coloque o executável em um diretório no PATH, ou passe o caminho ao criar `WebController`.
- Alternativamente posso modificar `comandos.py` para usar `webdriver-manager` para baixar drivers automaticamente.

Oracle / oracledb

- `oracledb` está no `requirements.txt`. Em muitos casos o driver funciona no modo thin
	sem componentes nativos. Se der erro indicando falta de Instant Client, instale
	o Oracle Instant Client apropriado e coloque a pasta no PATH/LD_LIBRARY_PATH.

Executando o projeto

Recomendo executar usando `main.py` (o runner central). No PowerShell, com o venv
ativado e variáveis de ambiente configuradas:

```powershell
python main.py
```

Modo seguro para testes (sem base Oracle)

Se você não quer conectar ao banco durante testes, deixe as variáveis de DB
não configuradas — o código tentará instanciar `DBClient` e, caso falhe, irá
seguir em modo de teste (vai exibir um WARNING e o fluxo executa sem DB).

Debug e troubleshooting

- Erro ao importar `selenium` ou `oracledb`: instale-os com pip (veja `requirements.txt`).
- Erro ao iniciar navegador: verifique se o driver (`chromedriver`) está no PATH e sua versão corresponde ao navegador.
- Erro ao conectar ao Oracle: verifique `AUSTA_BD_ORACLE_DEV`, `BD_USUARIO`, `BD_SENHA` e se o driver precisa de Instant Client.
- Logs: o projeto usa `logging` com nível INFO; aumente para DEBUG em `main.py` se precisar de mais detalhes.


---
Licença / Observações




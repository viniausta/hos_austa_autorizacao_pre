"""Configuração centralizada de logging para o projeto RPA.

Características:
- Rotação diária automática (TimedRotatingFileHandler)
- Mantém 30 dias de histórico
- Nível DEBUG em arquivo, INFO no console
- Caminho absoluto — funciona independente de onde o script é executado
- Proteção contra handlers duplicados em múltiplas importações
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Raiz do projeto determinada pelo caminho deste arquivo (monitoring/ → raiz)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE = _LOG_DIR / "automacao.log"
_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configura o ROOT logger para que TODOS os módulos (logging.getLogger(__name__))
# propaguem automaticamente para os handlers de console e arquivo.
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)

if not _root.handlers:
    # Handler de console — nível INFO (operacional)
    _console = logging.StreamHandler()
    _console.setLevel(logging.INFO)

    # Handler de arquivo — nível DEBUG (diagnóstico completo)
    # Rotação à meia-noite, suffixo de data no arquivo rotacionado, 30 dias de retenção
    _file = TimedRotatingFileHandler(
        _LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    _file.setLevel(logging.DEBUG)
    _file.suffix = "%Y-%m-%d"

    _formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)
    _console.setFormatter(_formatter)
    _file.setFormatter(_formatter)

    _root.addHandler(_console)
    _root.addHandler(_file)

# Logger nomeado para uso direto no main.py e outros pontos de entrada
logger = logging.getLogger("automacao_rpa")

logger.info("=" * 80)
logger.info("Iniciando sessão de logs da automação RPA")
logger.info("Arquivo de log: %s", _LOG_FILE)
logger.info("=" * 80)

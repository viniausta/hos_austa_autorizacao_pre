"""
Wrapper para executável — garante que o projeto funciona quando compilado como .exe

Este arquivo é executado quando o .exe é rodado pelo Task Scheduler.
Trata erros e garante logging adequado.
"""
import sys
import os
from pathlib import Path

# Adiciona o diretório do script ao path (para imports funcionarem)
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# Carrega .env do diretório do .exe
env_path = script_dir / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
else:
    print(f"[WARN] Arquivo .env não encontrado em {env_path}")
    print("[WARN] Tentando carregar variáveis de ambiente do sistema...")

# Importa e executa o main
try:
    from main import main as app_main
    print("[INFO] Iniciando RPA Autorizações PA...")
    app_main()
except KeyboardInterrupt:
    print("[INFO] RPA interrompido pelo usuário.")
    sys.exit(0)
except Exception as e:
    print(f"[ERROR] Erro ao executar RPA: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

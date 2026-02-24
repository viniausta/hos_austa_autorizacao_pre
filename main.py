
from logs.logger_config import logger
from processamento import Config, Processamento
from comandos import DBClient
from typing import Optional
from processamento import DatabaseProtocol


def main() -> None:
    logger.info("Iniciando automação de autorização PA...")
    # 1. Carrega configurações de ambiente
    config = Config.from_env()
    # 2. Tenta conectar ao banco de dados
    db_client: Optional[DatabaseProtocol] = None
    try:
        db_client = DBClient(config)
        logger.info("Conexão com o banco estabelecida.")
    except Exception as e:
        logger.warning(f"Falha ao conectar ao banco de dados: {e}")
    # 3. Inicializa a automação
    rpa = Processamento(config, db=db_client, browser=None)
    # 4. Executa os fluxos da automação
    try:
        rpa.inicializar()
        # rpa.bd_importar_contas()
        rpa.executar()
        logger.info("✅ Automação concluída com sucesso.")
    except Exception:
        logger.exception("❌ Erro na execução da automação")
    finally:
        rpa.finalizar()
        logger.info("Automação finalizada.")


if __name__ == "__main__":
    main()

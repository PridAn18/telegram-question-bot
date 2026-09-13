import logging
import logging.handlers
import os
import sys

import config
from utils.constants import APP_NAME, LOG_BACKUP_COUNT, LOG_MAX_BYTES


def setup_logger() -> logging.Logger:
    os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root.addHandler(stdout_handler)
    root.addHandler(file_handler)

    logger = logging.getLogger(APP_NAME)
    logger.info("Логирование настроено: stdout + %s", config.LOG_PATH)
    return logger
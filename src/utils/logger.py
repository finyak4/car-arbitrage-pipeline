import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
APP_DIR = Path(os.environ["APP_DIR"])
LOG_DIR = APP_DIR / "logs"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    # Prevent duplicate logs if called multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    # Console Handler (What you see in terminal)
    c_handler = logging.StreamHandler(sys.stdout)
    c_format = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    c_handler.setFormatter(c_format)

    # File Handler (Saves to logs/ folder for debugging later)
    LOG_DIR.mkdir(exist_ok=True)
    f_handler = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
    f_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    f_handler.setFormatter(f_format)

    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logger

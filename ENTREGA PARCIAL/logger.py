# Simple rotating logger to file and console.
import logging, os
from logging.handlers import RotatingFileHandler

def get_logger(name: str):
    os.makedirs("logs", exist_ok=True)
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fh = RotatingFileHandler("logs/server.log", maxBytes=512000, backupCount=2, encoding="utf-8")
    ch = logging.StreamHandler()
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(ch)
    return log

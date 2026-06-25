"""日志记录：控制台 + autoloot.log 文件。"""
import logging
import sys


def get_logger(cfg=None, name="autoloot"):
    log = logging.getLogger(name)
    if log.handlers:
        return log

    level = logging.INFO
    if cfg and isinstance(cfg.get("logging"), dict):
        level = getattr(logging, str(cfg["logging"].get("level", "INFO")).upper(), logging.INFO)
    log.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    try:
        fh = logging.FileHandler("autoloot.log", encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except OSError:
        pass

    return log

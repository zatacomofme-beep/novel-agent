import logging


LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "[%(filename)s:%(lineno)d] %(message)s"
)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

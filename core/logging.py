"""Centralized logging configuration."""

import logging

FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def configure_logger(name: str) -> logging.Logger:
    """Configure and return a logger with the app's standard formatting."""
    logging.basicConfig(
        level=logging.INFO,
        format=FORMAT,
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger(name)

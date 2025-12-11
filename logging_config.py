"""Centralized logging configuration for the Spotify analytics application."""

import logging


def configure_logger(name: str) -> logging.Logger:
    """Configure and return a logger instance with standard formatting.

    Args:
        name: The name of the logger.

    Returns:
        logging.Logger: A configured logger instance.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger(name)

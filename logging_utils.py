"""Shared logging configuration for console output."""

import logging
import sys
from typing import Optional


def configure_logging(debug: bool = False, level: Optional[int] = None) -> logging.Logger:
    """Configure standardized console logging.

    Args:
        debug: Enable debug level if True.
        level: Optional logging level override.

    Returns:
        Root logger instance.
    """
    log_level = level if level is not None else (logging.DEBUG if debug else logging.INFO)
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Reset handlers to avoid duplicate logs when reconfiguring
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    return root_logger
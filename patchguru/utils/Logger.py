import logging
import os
from typing import Optional

import colorlog

from patchguru import Config


def get_logger(name: str, level: Optional[str] = None, log_file: Optional[str] = None) -> logging.Logger:
    """
    Get a colorful logger instance.

    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """

    #
    # Get log level from environment or use default
    log_level = level or os.getenv("LOG_LEVEL", Config.LOG_LEVEL).upper()

    # Create logger
    logger = colorlog.getLogger(name)

    # Avoid adding multiple handlers
    if not logger.handlers:
        # Create console handler with color formatting
        handler = colorlog.StreamHandler()
        handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
        )

        logger.addHandler(handler)

        # Add file handler if log_file is specified or LOG_FILE env var is set
        if log_file is None:
            log_file = os.getenv("LOG_FILE")
        if log_file:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
            )
            logger.addHandler(file_handler)

        logger.setLevel(getattr(logging, log_level))
        logger.propagate = False

    return logger

def format_info_frame(message: str, title: str = "INFO") -> str:
    """
    Formats an informational message with a beautified title.

    Args:
        message: The message to format.
        title: The title to display above the message.

    Returns:
        A string with the message formatted and titled.
    """
    separator = "=" * (len(title) + 8)
    title_line = f"*** {title.upper()} ***"
    formatted_message = f"{separator}\n{title_line}\n{separator}\n{message}\n{separator}"
    return formatted_message

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Setup global logging configuration.

    Args:
        level: Global log level
        log_file: Optional file path to save logs to
    """
    os.environ["LOG_LEVEL"] = level.upper()
    if log_file:
        os.environ["LOG_FILE"] = log_file

if __name__ == "__main__":
    # Example usage
    setup_logging("DEBUG", "logs/app.log")
    logger = get_logger(__name__)
    logger.info("Logger initialized successfully")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    framed_message = format_info_frame("This is a test message. Very long Very long Very long Very long", "Test Title")
    logger.info("\n\n" + framed_message)

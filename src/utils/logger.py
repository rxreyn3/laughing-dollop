"""Logging configuration for the application."""
import logging
import sys

import colorlog


def setup_logger(name: str = None, log_level: str = "INFO") -> logging.Logger:
    """Set up a colored logger with the specified name and level.
    
    Args:
        name: The logger name. If None, returns the root logger.
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        
    Returns:
        A configured logger instance.
    """
    # Create logger
    logger = logging.getLogger(name)

    # Only add handlers if they haven't been added before
    if not logger.handlers:
        logger.setLevel(getattr(logging, log_level))

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level))

        # Create a colorlog formatter
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )

        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Prevent logging from propagating to the root logger
        logger.propagate = False

    return logger


# Create default logger
logger = setup_logger("laughing_dollop")

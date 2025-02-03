"""Logging configuration for the application."""
import logging
import sys

import colorlog


def setup_logger(name: str = None) -> logging.Logger:
    """
    Set up a colored logger instance.
    
    Args:
        name: Logger name (defaults to root logger if None)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if logger.hasHandlers():
        return logger
        
    handler = colorlog.StreamHandler(sys.stdout)
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s %(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            reset=True,
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING': 'yellow',
                'ERROR':   'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    )
    
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    return logger

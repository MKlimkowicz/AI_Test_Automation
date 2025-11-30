import logging
import sys
from typing import Optional

_config = None

def _get_config():
    global _config
    if _config is None:
        from utils.config import config
        _config = config
    return _config


class ColoredFormatter(logging.Formatter):
    
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
        'RESET': '\033[0m',
    }
    
    SYMBOLS = {
        'DEBUG': '🔍',
        'INFO': '✓',
        'WARNING': '⚠',
        'ERROR': '✗',
        'CRITICAL': '💀',
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        symbol = self.SYMBOLS.get(record.levelname, '')
        reset = self.COLORS['RESET']
        
        original_msg = record.msg
        record.msg = f"{color}{symbol} {original_msg}{reset}"
        
        result = super().format(record)
        
        record.msg = original_msg
        
        return result


def setup_logger(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    config = _get_config()
    
    log_level = level or config.LOG_LEVEL
    log_file_path = log_file or config.LOG_FILE
    log_format = config.LOG_FORMAT
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    if log_file_path:
        try:
            project_root = config.get_project_root()
            full_log_path = project_root / log_file_path
            
            full_log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(full_log_path, mode='a')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(log_format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    return setup_logger(name)

import logging
import sys
from datetime import datetime
from functools import wraps
import os

LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

def get_log_level():
    env = os.getenv('FLASK_ENV', 'production')
    if env == 'development':
        return logging.DEBUG
    return logging.WARNING

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[34m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
        'RESET': '\033[0m',
        'BOLD': '\033[1m'
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{self.COLORS['BOLD']}{record.levelname}{self.COLORS['RESET']}"
        record.name = f"{self.COLORS['BOLD']}{record.name}{self.COLORS['RESET']}"
        return super().format(record)

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(get_log_level())

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(get_log_level())

    formatter = ColoredFormatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger

def log_request(logger):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request

            logger.info(f"→ {request.method} {request.path}")
            logger.debug(f"Headers: {dict(request.headers)}")

            if request.method in ['POST', 'PUT', 'PATCH'] and request.is_json:
                safe_data = {k: v for k, v in request.json.items() if k != 'password'}
                logger.debug(f"Body: {safe_data}")

            try:
                response = f(*args, **kwargs)
                logger.info(f"← {request.method} {request.path} - 200 OK")
                return response
            except Exception as e:
                logger.error(f"← {request.method} {request.path} - ERROR: {str(e)}")
                raise

        return decorated_function
    return decorator

def log_db_operation(logger, operation, model_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            logger.debug(f"DB {operation}: {model_name}")
            try:
                result = f(*args, **kwargs)
                logger.debug(f"DB {operation} {model_name} - Success")
                return result
            except Exception as e:
                logger.error(f"DB {operation} {model_name} - Failed: {str(e)}")
                raise
        return decorated_function
    return decorator

app_logger = setup_logger('MoneyMind')
auth_logger = setup_logger('MoneyMind.Auth')
transaction_logger = setup_logger('MoneyMind.Transactions')
budget_logger = setup_logger('MoneyMind.Budgets')
goal_logger = setup_logger('MoneyMind.Goals')
analytics_logger = setup_logger('MoneyMind.Analytics')
plaid_logger = setup_logger('MoneyMind.Plaid')
chat_logger = setup_logger('MoneyMind.Chat')
db_logger = setup_logger('MoneyMind.Database')

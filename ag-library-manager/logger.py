import logging
import os
import sys
from datetime import datetime


def setup_logger(log_name='app_log'):
    """
    Set up logging configuration with both file and console handlers.
    """
    logger = logging.getLogger()

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    def cleanup_old_logs():
        log_files = [f for f in os.listdir(log_dir) if f.startswith(f"{log_name}_") and f.endswith('.log')]
        log_files.sort(key=lambda f: os.path.getctime(os.path.join(log_dir, f)), reverse=True)

        for old_log in log_files[9:]:
            try:
                os.remove(os.path.join(log_dir, old_log))
            except OSError:
                pass

    cleanup_old_logs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{log_name}_{timestamp}.log")

    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    except (OSError, IOError) as e:
        print(f"Warning: Could not create log file {log_file}: {e}", file=sys.stderr)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized for '{log_name}'. Log file: {log_file}")

    return logger
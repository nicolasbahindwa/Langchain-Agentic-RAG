import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from core.config import config  # Assume this exposes a fully populated config object

try:
    from colorama import Fore, Style, init
    init(autoreset=True)  # Auto-reset colors after each print
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors using colorama."""
    
    # Color mapping for different log levels
    LEVEL_COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA + Style.BRIGHT,
    }
    
    def __init__(self, fmt=None, datefmt=None, use_colors=True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and COLORAMA_AVAILABLE
    
    def format(self, record):
        if not self.use_colors:
            return super().format(record)
        
        # Save original levelname
        original_levelname = record.levelname
        
        # Add color to levelname
        color = self.LEVEL_COLORS.get(record.levelname, '')
        if color:
            record.levelname = f"{color}{Style.BRIGHT}{record.levelname}{Style.RESET_ALL}"
        
        # Format the message
        formatted = super().format(record)
        
        # Restore original levelname for other handlers
        record.levelname = original_levelname
        
        return formatted


def create_console_handler() -> logging.Handler:
    """Create and return a colored console handler."""
    console_handler = logging.StreamHandler()
    
    # Check if colors should be enabled
    use_colors = getattr(config.logging, 'use_colors', True)
    
    format_type = config.logging.format_type.lower()
    formats = {
        "simple": "%(asctime)s - %(levelname)s - %(message)s",
        "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        "json": '{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}'
    }
    
    formatter = ColoredFormatter(
        fmt=formats.get(format_type, formats["simple"]),
        use_colors=use_colors
    )
    console_handler.setFormatter(formatter)
    
    return console_handler


# def create_file_handler(app_name: str) -> logging.Handler:
#     """Create and return a rotating file handler based on config."""
#     log_dir = config.logging.log_dir
#     Path(log_dir).mkdir(parents=True, exist_ok=True)
#     log_file_path = Path(log_dir) / f"{app_name}.log"

#     # Explicitly convert to int
#     try:
#         max_bytes = int(getattr(config.logging, "log_rotation_max_bytes", 10 * 1024 * 1024))
#         backup_count = int(getattr(config.logging, "log_rotation_backup_count", 5))
#     except ValueError as e:
#         raise ValueError(f"Invalid log rotation config values: {e}")

#     file_handler = RotatingFileHandler(
#         filename=log_file_path,
#         maxBytes=max_bytes,
#         backupCount=backup_count
#     )

#     format_type = config.logging.format_type.lower()
#     formats = {
#         "simple": "%(asctime)s - %(levelname)s - %(message)s",
#         "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
#         "json": '{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}'
#     }
#     # File handler uses regular formatter (no colors in files)
#     formatter = logging.Formatter(formats.get(format_type, formats["simple"]))
#     file_handler.setFormatter(formatter)

#     return file_handler

def create_file_handler(app_name: str) -> logging.Handler:
    """Create and return a rotating file handler based on config."""
    log_dir = config.logging.log_dir
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file_path = Path(log_dir) / f"{app_name}.log"

    # Get config values and clean them (remove comments and whitespace)
    try:
        max_bytes_raw = str(getattr(config.logging, "log_rotation_max_bytes", "10485760"))
        backup_count_raw = str(getattr(config.logging, "log_rotation_backup_count", "5"))
        
        # Clean values by removing comments and whitespace
        max_bytes_clean = max_bytes_raw.split('#')[0].strip()
        backup_count_clean = backup_count_raw.split('#')[0].strip()
        
        # Convert to int
        max_bytes = int(max_bytes_clean)
        backup_count = int(backup_count_clean)
        
    except (ValueError, AttributeError) as e:
        # Fallback to defaults if parsing fails
        max_bytes = 10 * 1024 * 1024  # 10 MB
        backup_count = 5
        print(f"Warning: Could not parse log rotation config, using defaults. Error: {e}")

    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count
    )

    format_type = config.logging.format_type.lower()
    formats = {
        "simple": "%(asctime)s - %(levelname)s - %(message)s",
        "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        "json": '{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}'
    }
    # File handler uses regular formatter (no colors in files)
    formatter = logging.Formatter(formats.get(format_type, formats["simple"]))
    file_handler.setFormatter(formatter)

    return file_handler

def setup_logging(app_name: str = "app"):
    """Setup logging using values from core.config.config."""

    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    log_to_console = config.logging.to_console
    log_to_file = config.logging.to_file

    handlers = []

    if log_to_console:
        handlers.append(create_console_handler())

    if log_to_file:
        handlers.append(create_file_handler(app_name))

    # Clear any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )

    # Get the specific logger for this app
    logger = logging.getLogger(app_name)
    use_colors = getattr(config.logging, 'use_colors', True)
    
    # Log initialization messages
    if use_colors and COLORAMA_AVAILABLE:
        logger.info(f"Logging initialized for '{app_name}' with colorama colors")
    elif use_colors:
        logger.warning(f"Colorama not available for '{app_name}', using plain text logging")
    else:
        logger.info(f"Logging initialized for '{app_name}' (colors disabled)")
    
    logger.info(f"Config: level={config.logging.level}, file={log_to_file}, console={log_to_console}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# Enhanced logger with emoji support
class EnhancedLogger:
    """Wrapper around logger with enhanced methods for better visual output."""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def success(self, msg: str, *args, **kwargs):
        """Log a success message with a checkmark."""
        self.logger.info(f"✅ {msg}", *args, **kwargs)
    
    def failure(self, msg: str, *args, **kwargs):
        """Log a failure message with an X mark."""
        self.logger.error(f"❌ {msg}", *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Log a warning with a warning emoji."""
        self.logger.warning(f"⚠️  {msg}", *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Log an info message with an info emoji."""
        self.logger.info(f"ℹ️  {msg}", *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        """Log a debug message with a bug emoji."""
        self.logger.debug(f"🐛 {msg}", *args, **kwargs)
    
    def performance(self, msg: str, *args, **kwargs):
        """Log performance metrics with a rocket emoji."""
        self.logger.info(f"🚀 {msg}", *args, **kwargs)
    
    def security(self, msg: str, *args, **kwargs):
        """Log security-related messages with a shield emoji."""
        self.logger.warning(f"🛡️  {msg}", *args, **kwargs)


def get_enhanced_logger(name: str) -> EnhancedLogger:
    """Get an enhanced logger with emoji support."""
    return EnhancedLogger(name)
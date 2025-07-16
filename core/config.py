"""
Simplified Enhanced Configuration System
Clean, organized structure with all features preserved
"""

import os
import sys
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()


# =============================================================================
# EXCEPTION CLASSES
# =============================================================================

class ConfigError(Exception):
    """Base configuration error with enhanced context"""
    
    def __init__(self, message: str, field: str = None, value: str = None, suggestion: str = None):
        super().__init__(message)
        self.field = field
        self.value = value
        self.suggestion = suggestion
    
    def __str__(self):
        parts = [f"Configuration Error: {super().__str__()}"]
        
        if self.field:
            parts.append(f"Field: {self.field}")
        if self.value:
            parts.append(f"Value: {self.value}")
        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")
        
        return "\n".join(parts)


class ValidationError(ConfigError):
    """Configuration validation error"""
    pass


class SecurityError(ConfigError):
    """Configuration security error"""
    pass


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def get_bool(key: str, default: bool = False) -> bool:
    """Convert environment variable to boolean"""
    value = os.getenv(key, '').lower().strip()
    
    if not value:
        return default
    
    true_values = ('true', '1', 'yes', 'on', 'enabled')
    false_values = ('false', '0', 'no', 'off', 'disabled')
    
    if value in true_values:
        return True
    elif value in false_values:
        return False
    else:
        raise ValidationError(
            f"Invalid boolean value for {key}",
            field=key, value=value,
            suggestion=f"Use: {', '.join(true_values[:3])} or {', '.join(false_values[:3])}"
        )


def get_int(key: str, default: int = 0, min_val: int = None, max_val: int = None) -> int:
    """Convert environment variable to integer with validation"""
    value = os.getenv(key)
    
    if value is None:
        return default
    
    try:
        int_value = int(value)
        
        if min_val is not None and int_value < min_val:
            raise ValidationError(
                f"Value {int_value} below minimum {min_val}",
                field=key, value=value, suggestion=f"Use value >= {min_val}"
            )
        
        if max_val is not None and int_value > max_val:
            raise ValidationError(
                f"Value {int_value} above maximum {max_val}",
                field=key, value=value, suggestion=f"Use value <= {max_val}"
            )
        
        return int_value
        
    except ValueError:
        raise ValidationError(
            f"Invalid integer value",
            field=key, value=value, suggestion="Use a valid integer"
        )


def get_list(key: str, separator: str = ',', required: bool = False) -> List[str]:
    """Convert environment variable to list"""
    value = os.getenv(key, '').strip()
    
    if not value:
        if required:
            raise ValidationError(
                f"Required list is empty",
                field=key, suggestion=f"Provide values like 'item1{separator}item2'"
            )
        return []
    
    items = [item.strip() for item in value.split(separator) if item.strip()]
    
    if required and not items:
        raise ValidationError(
            f"List contains no valid items",
            field=key, value=value, suggestion=f"Provide non-empty values"
        )
    
    return items


def validate_url(url: str, field: str) -> bool:
    """Validate URL format with better localhost/IP handling"""
    if not url:
        return False

    pattern = re.compile(
        r'^https?://'
        r'(?:'
        r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?'
        r'|localhost'
        r'|\d{1,3}(?:\.\d{1,3}){3}'
        r')'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)?$', re.IGNORECASE
    )

    if not pattern.match(url):
        raise ValidationError(
            "Invalid URL format",
            field=field, value=url,
            suggestion="Use format: https://example.com or http://localhost:3000"
        )
    return True


def validate_email(email: str, field: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    
    pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    if not pattern.match(email):
        raise ValidationError(
            "Invalid email format",
            field=field, value=email, suggestion="Use format: user@example.com"
        )
    
    return True


def validate_secret(secret: str, field: str, min_length: int = 32) -> bool:
    """Validate secret strength"""
    if not secret:
        raise SecurityError(
            f"Secret is required",
            field=field, suggestion=f"Generate random string of {min_length}+ characters"
        )
    
    if len(secret) < min_length:
        raise SecurityError(
            f"Secret too short ({len(secret)} chars, need {min_length})",
            field=field, suggestion=f"Use {min_length}+ character secret"
        )
    
    if secret.lower() in ['password', 'secret', '123456', 'admin']:
        raise SecurityError(
            "Secret uses weak pattern",
            field=field, suggestion="Use randomly generated secret"
        )
    
    return True


# =============================================================================
# VALIDATION RESULT
# =============================================================================

@dataclass
class ValidationResult:
    """Stores validation results"""
    is_valid: bool = True
    errors: List[ConfigError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: ConfigError):
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)


# =============================================================================
# CONFIGURATION SECTIONS
# =============================================================================

@dataclass
class AppInfo:
    """Application information"""
    name: str
    version: str
    environment: str
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        if not self.name or not self.name.strip():
            result.add_error(ValidationError(
                "App name required", field="APP_NAME",
                suggestion="Set meaningful application name"
            ))
        
        if len(self.name) > 50:
            result.add_warning("App name very long (>50 chars)")
        
        if not self.version:
            result.add_warning("App version not set")
        
        valid_envs = ['development', 'dev', 'staging', 'production', 'prod', 'test']
        if self.environment.lower() not in valid_envs:
            result.add_warning(f"Unknown environment '{self.environment}'")
        
        return result
    
    def is_development(self) -> bool:
        return self.environment.lower() in ('development', 'dev', 'local')
    
    def is_production(self) -> bool:
        return self.environment.lower() in ('production', 'prod')
    
    def is_staging(self) -> bool:
        return self.environment.lower() in ('staging', 'stage')



@dataclass
class LangchainConfig:
    """Langchain configuration"""
    tracing: bool
    project: str
    
    def validate(self) -> ValidationResult:  # Fixed typo: sefl -> self
        result = ValidationResult()
        
        # Validate project name
        if not self.project:
            result.add_error(ValidationError(
                "Project name is required", 
                field="LANGCHAIN_PROJECT",
                suggestion="Provide a project name for LangChain tracing"
            ))
        elif not self.project.strip():
            result.add_error(ValidationError(
                "Project name cannot be empty or whitespace only", 
                field="LANGCHAIN_PROJECT",
                suggestion="Use a meaningful project name"
            ))
        elif len(self.project) > 100:
            result.add_error(ValidationError(
                f"Project name too long ({len(self.project)} chars)", 
                field="LANGCHAIN_PROJECT",
                suggestion="Use a project name under 100 characters"
            ))
        
        # Validate tracing configuration
        if self.tracing and not self.project:
            result.add_error(ValidationError(
                "Project name required when tracing is enabled",
                field="LANGCHAIN_PROJECT", 
                suggestion="Set LANGCHAIN_PROJECT when LANGCHAIN_TRACING=true"
            ))

@dataclass
class ServerConfig:
    """Server configuration"""
    host: str
    port: int
    base_url: str
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        if not (1 <= self.port <= 65535):
            result.add_error(ValidationError(
                f"Invalid port {self.port}", field="PORT",
                suggestion="Use port 1-65535"
            ))
        
        if self.port < 1024:
            result.add_warning(f"Port {self.port} requires elevated privileges")
        
        if not self.host:
            result.add_error(ValidationError(
                "Host required", field="HOST",
                suggestion="Use '0.0.0.0' or '127.0.0.1'"
            ))
        
        if self.base_url:
            try:
                validate_url(self.base_url, "BASE_URL")
            except ValidationError as e:
                result.add_error(e)
        
        return result
    
    def get_listen_address(self) -> str:
        return f"{self.host}:{self.port}"

@dataclass
class DataProcessingConfig:
    """Data processing configuration"""
    raw_data_folder_path: str
    markdown_data_folder_path: str
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        # Validate raw data folder path
        if not self.raw_data_folder_path or not self.raw_data_folder_path.strip():
            result.add_error(ValidationError(
                "Raw data folder path required", 
                field="RAW_DATA_FOLDER_PATH",
                suggestion="Set path for raw data folder"
            ))
        else:
            try:
                raw_path = Path(self.raw_data_folder_path)
                raw_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                result.add_error(ValidationError(
                    f"Cannot create raw data folder: {e}", 
                    field="RAW_DATA_FOLDER_PATH",
                    suggestion="Use a valid, writable directory path"
                ))
        
        # Validate markdown data folder path
        if not self.markdown_data_folder_path or not self.markdown_data_folder_path.strip():
            result.add_error(ValidationError(
                "Markdown data folder path required", 
                field="MARKDOWN_DATA_FOLDER_PATH",
                suggestion="Set path for markdown data folder"
            ))
        else:
            try:
                markdown_path = Path(self.markdown_data_folder_path)
                markdown_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                result.add_error(ValidationError(
                    f"Cannot create markdown data folder: {e}", 
                    field="MARKDOWN_DATA_FOLDER_PATH",
                    suggestion="Use a valid, writable directory path"
                ))
        
        # Check if paths are the same
        if (self.raw_data_folder_path and self.markdown_data_folder_path and 
            Path(self.raw_data_folder_path).resolve() == Path(self.markdown_data_folder_path).resolve()):
            result.add_warning("Raw data and markdown folders are the same")
        
        return result
    
    def is_configured(self) -> bool:
        return bool(
            self.raw_data_folder_path and self.raw_data_folder_path.strip() and
            self.markdown_data_folder_path and self.markdown_data_folder_path.strip()
        )
    
    def get_raw_data_path(self) -> Path:
        return Path(self.raw_data_folder_path)
    
    def get_markdown_data_path(self) -> Path:
        return Path(self.markdown_data_folder_path)
    
@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    username: str
    password: str
    name: str
    ssl_enabled: bool
    connection_timeout: int
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        # Required fields
        required = {'host': self.host, 'username': self.username, 
                   'password': self.password, 'name': self.name}
        
        for field_name, value in required.items():
            if not value or not value.strip():
                result.add_error(ValidationError(
                    f"Database {field_name} required",
                    field=f"DB_{field_name.upper()}",
                    suggestion=f"Set database {field_name}"
                ))
        
        if not (1 <= self.port <= 65535):
            result.add_error(ValidationError(
                f"Invalid port {self.port}", field="DB_PORT",
                suggestion="PostgreSQL: 5432, MySQL: 3306"
            ))
        
        if self.connection_timeout <= 0:
            result.add_error(ValidationError(
                "Timeout must be positive", field="DB_CONNECTION_TIMEOUT",
                suggestion="Use 10-300 seconds"
            ))
        
        # Security warnings
        if self.password and len(self.password) < 8:
            result.add_warning("Database password < 8 characters")
        
        if not self.ssl_enabled:
            result.add_warning("SSL disabled - enable for production")
        
        return result
    
    def is_configured(self) -> bool:
        return all([
            self.host and self.host.strip(),
            1 <= self.port <= 65535,
            self.username and self.username.strip(),
            self.password and self.password.strip(),
            self.name and self.name.strip()
        ])
    
    def get_connection_url(self, include_password: bool = True) -> str:
        if not self.is_configured():
            raise ConfigError("Database not configured")
        
        password_part = f":{self.password}" if include_password and self.password else ""
        ssl_param = "?sslmode=require" if self.ssl_enabled else "?sslmode=disable"
        
        return f"postgresql://{self.username}{password_part}@{self.host}:{self.port}/{self.name}{ssl_param}"


@dataclass
class RedisConfig:
    """Redis configuration"""
    host: str
    port: int
    password: Optional[str]
    db: int
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        if not self.host or not self.host.strip():
            result.add_error(ValidationError(
                "Redis host required", field="REDIS_HOST",
                suggestion="Set Redis hostname/IP"
            ))
        
        if not (1 <= self.port <= 65535):
            result.add_error(ValidationError(
                f"Invalid port {self.port}", field="REDIS_PORT",
                suggestion="Redis default: 6379"
            ))
        
        if not (0 <= self.db <= 15):
            result.add_error(ValidationError(
                f"Invalid database {self.db}", field="REDIS_DB",
                suggestion="Use 0-15"
            ))
        
        if self.port != 6379:
            result.add_warning(f"Non-standard Redis port {self.port}")
        
        if not self.password:
            result.add_warning("Redis password not set")
        
        return result
    
    def is_configured(self) -> bool:
        return bool(self.host and self.host.strip() and 1 <= self.port <= 65535)


@dataclass
class SecurityConfig:
    """Security configuration"""
    jwt_secret: str
    session_secret: str
    cors_origins: List[str]
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        try:
            validate_secret(self.jwt_secret, "JWT_SECRET", 32)
        except SecurityError as e:
            result.add_error(e)
        
        try:
            validate_secret(self.session_secret, "SESSION_SECRET", 32)
        except SecurityError as e:
            result.add_error(e)
        
        for origin in self.cors_origins:
            try:
                validate_url(origin, "CORS_ORIGINS")
            except ValidationError:
                result.add_error(ValidationError(
                    f"Invalid CORS origin: {origin}",
                    field="CORS_ORIGINS", value=origin,
                    suggestion="Use valid URLs"
                ))
        
        if self.jwt_secret == self.session_secret:
            result.add_warning("JWT and session secrets identical")
        
        localhost_origins = [o for o in self.cors_origins if 'localhost' in o]
        if localhost_origins:
            result.add_warning(f"Localhost CORS origins: {localhost_origins}")
        
        return result
    
    def is_production_ready(self) -> bool:
        return (
            len(self.jwt_secret) >= 32 and
            len(self.session_secret) >= 32 and
            self.jwt_secret != self.session_secret and
            not any('localhost' in o for o in self.cors_origins)
        )


@dataclass
class OllamaConfig:
    """Ollama configuration"""
    base_url: str
    timeout: int
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        if not self.base_url or not self.base_url.strip():
            result.add_error(ValidationError(
                "Ollama URL required", field="OLLAMA_URL",
                suggestion="Set Ollama server URL (e.g., http://localhost:11434)"
            ))
        else:
            try:
                validate_url(self.base_url, "OLLAMA_URL")
            except ValidationError as e:
                result.add_error(e)
        
        if self.timeout <= 0:
            result.add_error(ValidationError(
                "Timeout must be positive", field="OLLAMA_TIMEOUT",
                suggestion="Use 30-300 seconds"
            ))
        
        # Default port warning
        if self.base_url and ':11434' not in self.base_url and 'localhost' in self.base_url:
            result.add_warning("Using non-standard Ollama port (default: 11434)")
        
        return result
    
    def is_configured(self) -> bool:
        return bool(self.base_url and self.base_url.strip())

@dataclass
class APIKeysConfig:
    """API keys configuration"""
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    langsmith_api_key: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        if self.openai_api_key:
            if not self.openai_api_key.startswith('sk-'):
                result.add_error(ValidationError(
                    "Invalid OpenAI API key", field="OPENAI_API_KEY",
                    suggestion="Should start with 'sk-'"
                ))
        
        if self.anthropic_api_key:
            if not self.anthropic_api_key.startswith('sk-ant-'):
                result.add_error(ValidationError(
                    "Invalid Anthropic API key", field="ANTHROPIC_API_KEY",
                    suggestion="Should start with 'sk-ant-'"
                ))
        
        # AWS validation
        if self.aws_access_key_id or self.aws_secret_access_key:
            if not (self.aws_access_key_id and self.aws_secret_access_key):
                result.add_error(ValidationError(
                    "AWS credentials incomplete",
                    suggestion="Need both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
                ))
        
        return result
    
    def get_configured_services(self) -> List[str]:
        services = []
        if self.openai_api_key:
            services.append('OpenAI')
        if self.anthropic_api_key:
            services.append('Anthropic')
        if self.aws_access_key_id and self.aws_secret_access_key:
            services.append('AWS')
        return services


@dataclass
class EmailConfig:
    """Email configuration"""
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        # If any email field set, validate all
        if any([self.smtp_host, self.smtp_user, self.smtp_password]):
            if not all([self.smtp_host, self.smtp_user, self.smtp_password]):
                result.add_error(ValidationError(
                    "Incomplete email config",
                    suggestion="Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD"
                ))
        
        if self.smtp_user:
            try:
                validate_email(self.smtp_user, "SMTP_USER")
            except ValidationError as e:
                result.add_error(e)
        
        common_ports = [25, 465, 587, 2525]
        if self.smtp_port not in common_ports:
            result.add_warning(f"Uncommon SMTP port {self.smtp_port}")
        
        return result
    
    def is_configured(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_password])


@dataclass
class LogConfig:
    """Logging configuration"""
    
    level: str
    to_file: bool
    to_console: bool
    log_dir: str
    format_type: str
    
    log_rotation_max_bytes: int
    log_rotation_backup_count: int
    
    def validate(self) -> ValidationResult:
        result = ValidationResult()
        
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.level not in valid_levels:
            result.add_error(ValidationError(
                f"Invalid log level '{self.level}'", field="LOG_LEVEL",
                suggestion=f"Use: {', '.join(valid_levels)}"
            ))
        
        valid_formats = ['simple', 'detailed', 'json']
        if self.format_type not in valid_formats:
            result.add_error(ValidationError(
                f"Invalid format '{self.format_type}'", field="LOG_FORMAT",
                suggestion=f"Use: {', '.join(valid_formats)}"
            ))
        
        if not self.to_file and not self.to_console:
            result.add_error(ValidationError(
                "No log output enabled",
                suggestion="Enable LOG_TO_FILE or LOG_TO_CONSOLE"
            ))
        
        if self.to_file:
            try:
                Path(self.log_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                result.add_error(ValidationError(
                    f"Cannot create log dir: {e}", field="LOG_DIR",
                    suggestion="Use writable directory"
                ))
        
        return result

# =============================================================================
# MAIN CONFIGURATION CLASS
# =============================================================================

class Config:
    """Main configuration class"""
    
    def __init__(self):
        self._load_all_config()
    
    def _load_all_config(self):
        """Load all configuration sections"""
        
        # App Info
        self.app_info = AppInfo(
            name=os.getenv('APP_NAME', 'Application'),
            version=os.getenv('APP_VERSION', '1.0.0'),
            environment=os.getenv('ENVIRONMENT', 'development')
        )
        
        # Server Config
        self.server = ServerConfig(
            host=os.getenv('HOST', '0.0.0.0'),
            port=get_int('PORT', 3000, min_val=1, max_val=65535),
            base_url=os.getenv('BASE_URL', 'http://localhost:3000')
        )
        
        # Database Config
        self.database = DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=get_int('DB_PORT', 5432, min_val=1, max_val=65535),
            username=os.getenv('DB_USERNAME', ''),
            password=os.getenv('DB_PASSWORD', ''),
            name=os.getenv('DB_NAME', ''),
            ssl_enabled=get_bool('DB_SSL_ENABLED', False),
            connection_timeout=get_int('DB_CONNECTION_TIMEOUT', 30, min_val=1, max_val=600)
        )
        
        # Redis Config
        self.redis = RedisConfig(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=get_int('REDIS_PORT', 6379, min_val=1, max_val=65535),
            password=os.getenv('REDIS_PASSWORD') or None,
            db=get_int('REDIS_DB', 0, min_val=0, max_val=15)
        )
        
        # Security Config
        self.security = SecurityConfig(
            jwt_secret=os.getenv('JWT_SECRET', ''),
            session_secret=os.getenv('SESSION_SECRET', ''),
            cors_origins=get_list('CORS_ORIGINS')
        )
        # Data Processing Config
        self.data_processing = DataProcessingConfig(
            raw_data_folder_path=os.getenv('RAW_DATA_FOLDER_PATH', 'documents/raw_data'),
            markdown_data_folder_path=os.getenv('MARKDOWN_DATA_FOLDER_PATH', 'documents/markdown')
        )
        # Ollama Config
        self.ollama = OllamaConfig(
            base_url=os.getenv('OLLAMA_URL', 'http://localhost:11434'),
            timeout=get_int('OLLAMA_TIMEOUT', 60, min_val=1, max_val=600)
        )
        
        self.langchain = LangchainConfig (
            tracing=os.getenv("LANGSMITH_TRACING"),
            project=os.getenv("LANGSMITH_PROJECT")
        )
        
        # API Keys Config
        self.api_keys = APIKeysConfig(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
            langsmith_api_key=os.getenv('LANGSMITH_API_KEY'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            aws_region=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # Email Config
        self.email = EmailConfig(
            smtp_host=os.getenv('SMTP_HOST'),
            smtp_port=get_int('SMTP_PORT', 587, min_val=1, max_val=65535),
            smtp_user=os.getenv('SMTP_USER'),
            smtp_password=os.getenv('SMTP_PASSWORD')
        )
        
        # Logging Config
        self.logging = LogConfig(
            level=os.getenv('LOG_LEVEL', 'INFO').upper(),
            to_file=get_bool('LOG_TO_FILE', True),
            to_console=get_bool('LOG_TO_CONSOLE', True),
            log_dir=os.getenv('LOG_DIR', 'logs'),
            format_type=os.getenv('LOG_FORMAT', 'simple').lower(),
            log_rotation_backup_count=os.getenv('LOG_ROTATE_BACKUP_COUNT'),
            log_rotation_max_bytes=os.getenv('LOG_ROTATE_MAX_BYTES', 5)
        )
    
    # =============================================================================
    # VALIDATION METHODS
    # =============================================================================
    
    def validate_all(self) -> ValidationResult:
        """Validate all configuration sections"""
        overall_result = ValidationResult()
        
        sections = [
            ("App", self.app_info),
            ("Server", self.server),
            ("Database", self.database),
            ("Data Processing", self.data_processing),
            ("Redis", self.redis),
            ("Security", self.security),
            ("Langchain", self.langchain),
            ("API Keys", self.api_keys),
            ("Email", self.email),
             ("Ollama", self.ollama),
            ("Logging", self.logging),
            
        ]
        
        # Validate each section
        for section_name, config_obj in sections:
            try:
                section_result = config_obj.validate()
                
                for error in section_result.errors:
                    if error.field and '.' not in error.field:
                        error.field = f"{section_name}.{error.field}"
                    overall_result.add_error(error)
                
                for warning in section_result.warnings:
                    overall_result.add_warning(f"{section_name}: {warning}")
                    
            except Exception as e:
                overall_result.add_error(ConfigError(f"{section_name} validation failed: {e}"))
        
        # Cross-section validation
        self._validate_cross_sections(overall_result)
        
        return overall_result
    
    def _validate_cross_sections(self, result: ValidationResult):
        """Validate relationships between sections"""
        
        # Production checks
        if self.app_info.is_production():
            if not self.server.base_url.startswith('https://'):
                result.add_error(SecurityError(
                    "Production must use HTTPS", field="BASE_URL",
                    suggestion="Change BASE_URL to https://"
                ))
            
            if not self.security.is_production_ready():
                result.add_error(SecurityError(
                    "Security not production ready",
                    suggestion="Strong secrets, no localhost CORS"
                ))
        
        # Storage checks
        if not self.database.is_configured() and not self.redis.is_configured():
            result.add_warning("No persistent storage configured")
        
        # API services check
        if not self.api_keys.get_configured_services():
            result.add_warning("No external APIs configured")
    
    # =============================================================================
    # CONVENIENCE METHODS
    # =============================================================================
    
    def is_development(self) -> bool:
        return self.app_info.is_development()
    
    def is_production(self) -> bool:
        return self.app_info.is_production()
    
    def get_service_status(self) -> Dict[str, bool]:
        """Get status of all services"""
        return {
            'database': self.database.is_configured(),
            'redis': self.redis.is_configured(),
            'email': self.email.is_configured(),
            'data_processing': self.data_processing.is_configured(), 
            'ollama': self.ollama.is_configured(),
            'openai': bool(self.api_keys.openai_api_key),
            'anthropic': bool(self.api_keys.anthropic_api_key),
            'aws': bool(self.api_keys.aws_access_key_id and self.api_keys.aws_secret_access_key)
        }
    
    def get_health_check(self) -> Dict[str, Any]:
        """Get health check report"""
        try:
            validation_result = self.validate_all()
            
            return {
                'status': 'healthy' if validation_result.is_valid else 'unhealthy',
                'errors': [str(error) for error in validation_result.errors],
                'warnings': validation_result.warnings,
                'services': self.get_service_status(),
                'environment': self.app_info.environment
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    # =============================================================================
    # DISPLAY METHODS
    # =============================================================================
    
    def print_summary(self):
        """Print configuration summary"""
        print("=" * 60)
        print(f"{self.app_info.name.upper()} CONFIGURATION")
        print("=" * 60)
        
        # Basic info
        print(f"📱 App: {self.app_info.name} v{self.app_info.version}")
        print(f"🌍 Environment: {self.app_info.environment}")
        print(f"🌐 Server: {self.server.base_url}")
        print(f"📡 Listen: {self.server.get_listen_address()}")
        print()
        
        # Health status
        health = self.get_health_check()
        status_icon = "✅" if health['status'] == 'healthy' else "❌"
        print(f"🏥 Status: {status_icon} {health['status'].title()}")
        
        if health.get('errors'):
            print(f"   Errors: {len(health['errors'])}")
        if health.get('warnings'):
            print(f"   Warnings: {len(health['warnings'])}")
        print()
        
        # Services
        print("🔧 Services:")
        for service, status in self.get_service_status().items():
            icon = "✅" if status else "❌"
            print(f"   {icon} {service.title()}")
        
        # APIs
        apis = self.api_keys.get_configured_services()
        if apis:
            print(f"   📡 APIs: {', '.join(apis)}")
        print()
        
        print("=" * 60)
    
    def print_validation_report(self):
        """Print detailed validation report"""
        validation_result = self.validate_all()
        
        if validation_result.is_valid and not validation_result.warnings:
            print("✅ Configuration is valid!")
            return
        
        print("🔍 VALIDATION REPORT")
        print("=" * 40)
        
        if validation_result.errors:
            print(f"❌ ERRORS ({len(validation_result.errors)}):")
            for i, error in enumerate(validation_result.errors, 1):
                print(f"{i}. {error}")
            print()
        
        if validation_result.warnings:
            print(f"⚠️  WARNINGS ({len(validation_result.warnings)}):")
            for i, warning in enumerate(validation_result.warnings, 1):
                print(f"{i}. {warning}")
            print()
        
        print("=" * 40)


# =============================================================================
# GLOBAL CONFIG INSTANCE
# =============================================================================

def create_config() -> Config:
    """Create and validate configuration"""
    try:
        config_instance = Config()
        
        # Validate
        validation_result = config_instance.validate_all()
        
        if not validation_result.is_valid:
            print("⚠️  Configuration has errors!")
            config_instance.print_validation_report()
            
            if config_instance.is_production():
                raise ConfigError("Invalid configuration in production")
        
        return config_instance
        
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        raise


# Create global instance
try:
    config = create_config()
except Exception as e:
    print(f"❌ FATAL: Cannot start - {e}")
    sys.exit(1)

 
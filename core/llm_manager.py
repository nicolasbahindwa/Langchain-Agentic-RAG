# llm_manager.py
from .config import config  # Import your global config instance
from enum import Enum
from typing import Dict, Any, Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
# from langchain_community.chat_models import ChatOllama
from langchain_ollama import ChatOllama
from utils.logger import get_enhanced_logger

class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

class LLMManager:
    """LLM Manager integrated with your configuration system"""
    
    def __init__(self):
        self.logger = get_enhanced_logger("LLMManager")
        
        self.logger.performance("Initializing LLM Manager...")
        self.provider_configs = self._load_provider_configs()
        self.logger.success("LLM Manager initialized")

    def _load_provider_configs(self) -> Dict[LLMProvider, Dict[str, Any]]:
        """Load configurations from your central config"""
        return {
            LLMProvider.OLLAMA: {
                'enabled': config.ollama.is_configured(),
                'base_url': config.ollama.base_url,
                'default_model': 'llama3.1'
            },
            LLMProvider.ANTHROPIC: {
                'enabled': bool(config.api_keys.anthropic_api_key),
                'api_key': config.api_keys.anthropic_api_key or "",
                'default_model': 'claude-3-haiku-20240307'
            },
            LLMProvider.OPENAI: {
                'enabled': bool(config.api_keys.openai_api_key),
                'api_key': config.api_keys.openai_api_key or "",
                'default_model': 'gpt-3.5-turbo'
            }
        }

    def get_chat_model(
        self,
        provider: LLMProvider,
        model: Optional[str] = None,
        **kwargs
    ) -> BaseChatModel:
        """Get a LangChain chat model for the specified provider"""
        if not self.provider_configs[provider]['enabled']:
            raise ValueError(f"{provider.value} provider is disabled or not configured")

        model_name = model or self.provider_configs[provider]['default_model']
        self.logger.info(f"Creating {provider.value} model: {model_name}")

        if provider == LLMProvider.OLLAMA:
            return ChatOllama(
                base_url=self.provider_configs[provider]['base_url'],
                model=model_name,
                **kwargs
            )
            
        elif provider == LLMProvider.ANTHROPIC:
            return ChatAnthropic(
                api_key=self.provider_configs[provider]['api_key'],
                model=model_name,
                **kwargs
            )
            
        elif provider == LLMProvider.OPENAI:
            return ChatOpenAI(
                api_key=self.provider_configs[provider]['api_key'],
                model=model_name,
                **kwargs
            )
            
        raise ValueError(f"Unsupported provider: {provider}")

    def get_available_providers(self) -> List[str]:
        """Get list of enabled providers"""
        return [
            p.value for p, cfg in self.provider_configs.items() 
            if cfg['enabled']
        ]
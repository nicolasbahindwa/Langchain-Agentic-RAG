# """
# Fast LLM Manager with Lazy Fallback Logic using LangChain
# Simplified and improved version with better error handling and cleaner code
# """

import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

# LangChain imports
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama
    
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Import config and logging
from core.config import config
from utils.logger import get_logger


class LLMProvider(Enum):
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    tokens: Optional[int] = None
    response_time: Optional[float] = None


class LLMError(Exception):
    """Base LLM error"""
    pass


class ProviderStatus:
    """Track provider health with simple circuit breaker pattern"""
    
    def __init__(self, cooldown_minutes: int = 2):
        self.is_healthy = True
        self.last_failure = None
        self.failure_count = 0
        self.cooldown_period = timedelta(minutes=cooldown_minutes)
    
    def mark_success(self):
        """Mark provider as healthy"""
        self.is_healthy = True
        self.failure_count = 0
        self.last_failure = None
    
    def mark_failure(self):
        """Mark provider as failed"""
        self.is_healthy = False
        self.failure_count += 1
        self.last_failure = datetime.now()
    
    def should_try(self) -> bool:
        """Check if we should try this provider"""
        if self.is_healthy:
            return True
        
        # Give it another chance after cooldown period
        if self.last_failure and datetime.now() - self.last_failure > self.cooldown_period:
            return True
        
        return False


class LLMManager:
    """Fast LLM Manager with lazy evaluation and smart fallback using LangChain"""
    
    def __init__(self):
        """Initialize LLM Manager with automatic config loading"""
        
        self.logger = get_logger("LLMManager")
        self.logger.info("Initializing LLM Manager...")
        
        # Get timeout from config with fallback
        self.timeout = self._get_config_value('ollama.timeout', 30)
        
        # Load provider configurations
        self.provider_configs = self._load_all_provider_configs()
        self._log_configuration_status()
        
        # LangChain instances (lazy initialization)
        self._llm_instances = {}
        
        # Provider health tracking
        self.provider_status = {
            provider: ProviderStatus() for provider in LLMProvider
        }
        
        # Provider order (try Ollama first for speed, then others)
        self.provider_order = [LLMProvider.OLLAMA, LLMProvider.ANTHROPIC, LLMProvider.OPENAI]
        self.last_successful_provider = None
        
        self.logger.info("LLM Manager initialized successfully")
    
    def _get_config_value(self, path: str, default: Any = None) -> Any:
        """Safely get nested config value using dot notation"""
        try:
            parts = path.split('.')
            value = config
            for part in parts:
                value = getattr(value, part)
            return value if value is not None else default
        except (AttributeError, TypeError):
            return default
    
    def _load_provider_config(self, provider: LLMProvider) -> Dict[str, Any]:
        """Load configuration for a single provider"""
        
        if provider == LLMProvider.OLLAMA:
            base_url = self._get_config_value('ollama.base_url')
            enabled = bool(base_url and base_url.strip())
            
            return {
                'enabled': enabled,
                'base_url': base_url.rstrip('/') if base_url else '',
                'default_model': 'mistral'
            }
        
        elif provider == LLMProvider.ANTHROPIC:
            api_key = self._get_config_value('api_keys.anthropic_api_key')
            enabled = bool(api_key and api_key.strip())
            
            return {
                'enabled': enabled,
                'api_key': api_key or '',
                'default_model': 'claude-3-haiku-20240307'
            }
        
        elif provider == LLMProvider.OPENAI:
            api_key = self._get_config_value('api_keys.openai_api_key')
            enabled = bool(api_key and api_key.strip())
            
            return {
                'enabled': enabled,
                'api_key': api_key or '',
                'default_model': 'gpt-3.5-turbo'
            }
        
        else:
            return {'enabled': False, 'default_model': 'unknown'}
    
    def _load_all_provider_configs(self) -> Dict[LLMProvider, Dict[str, Any]]:
        """Load configurations for all providers with error handling"""
        configs = {}
        
        for provider in LLMProvider:
            try:
                config_data = self._load_provider_config(provider)
                configs[provider] = config_data
                
                if config_data['enabled']:
                    self.logger.info(f"{provider.value.title()} provider enabled")
                else:
                    self.logger.warning(f"{provider.value.title()} provider disabled - missing configuration")
                    
            except Exception as e:
                self.logger.error(f"Error loading {provider.value} config: {e}")
                configs[provider] = {'enabled': False, 'default_model': 'unknown'}
        
        return configs
    
    def _log_configuration_status(self):
        """Log the current configuration status"""
        enabled_providers = [p for p, c in self.provider_configs.items() if c['enabled']]
        enabled_count = len(enabled_providers)
        total_count = len(self.provider_configs)
        
        self.logger.info("Provider Configuration Status:")
        for provider, config_data in self.provider_configs.items():
            status = "[ENABLED]" if config_data['enabled'] else "[DISABLED]"
            self.logger.info(f"  {provider.value.upper()}: {status}")
        
        if enabled_count == 0:
            self.logger.error("NO PROVIDERS ENABLED! Check your configuration.")
        else:
            self.logger.info(f"[SUCCESS] {enabled_count}/{total_count} providers enabled")
    
    def _get_llm_instance(self, provider: LLMProvider, model: Optional[str] = None):
        """Get or create LangChain LLM instance with caching"""
        
        cache_key = f"{provider.value}_{model or 'default'}"
        
        # Return cached instance if available
        if cache_key in self._llm_instances:
            return self._llm_instances[cache_key]
        
        # Validate provider is enabled
        config_data = self.provider_configs[provider]
        if not config_data['enabled']:
            raise LLMError(f"{provider.value} is not enabled (missing configuration)")
        
        # Create new instance
        self.logger.debug(f"Creating new LLM instance for {provider.value}")
        
        try:
            llm = self._create_llm_instance(provider, model, config_data)
            self._llm_instances[cache_key] = llm
            self.logger.info(f"Successfully initialized {provider.value} instance")
            return llm
            
        except Exception as e:
            error_msg = f"Failed to initialize {provider.value}: {e}"
            self.logger.error(error_msg)
            raise LLMError(error_msg)
    
    def _create_llm_instance(self, provider: LLMProvider, model: Optional[str], config_data: Dict[str, Any]):
        """Create the actual LLM instance based on provider type"""
        
        model_name = model or config_data['default_model']
        
        if provider == LLMProvider.OLLAMA:
            return ChatOllama(
                base_url=config_data['base_url'],
                model=model_name,
                timeout=self.timeout
            )
        
        elif provider == LLMProvider.ANTHROPIC:
            return ChatAnthropic(
                api_key=config_data['api_key'],
                model=model_name,
                timeout=self.timeout
            )
        
        elif provider == LLMProvider.OPENAI:
            return ChatOpenAI(
                api_key=config_data['api_key'],
                model=model_name,
                timeout=self.timeout
            )
        
        else:
            raise LLMError(f"Unknown provider: {provider}")
    
    def _convert_messages(self, messages: List[Dict[str, str]]):
        """Convert dict messages to LangChain message objects"""
        langchain_messages = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                self.logger.warning(f"Unknown message role '{role}', treating as user message")
                langchain_messages.append(HumanMessage(content=content))
        
        return langchain_messages
    
    def _get_optimal_provider_order(self, preferred: Optional[LLMProvider]) -> List[LLMProvider]:
        """Get optimal provider order for fastest response"""
        
        # If specific provider requested, try it first
        if preferred:
            order = [preferred]
            order.extend([p for p in self.provider_order if p != preferred])
            return order
        
        # If we have a recently successful provider, try it first
        if (self.last_successful_provider and 
            self.provider_status[self.last_successful_provider].is_healthy):
            order = [self.last_successful_provider]
            order.extend([p for p in self.provider_order if p != self.last_successful_provider])
            return order
        
        # Default order, but only healthy providers
        return [p for p in self.provider_order if self.provider_status[p].should_try()]
    
    def _categorize_error(self, error: Exception, provider: LLMProvider, model: Optional[str]) -> str:
        """Categorize error for better user feedback"""
        error_msg = str(error).lower()
        
        if 'rate limit' in error_msg or '429' in error_msg:
            return "Rate limit exceeded"
        elif 'timeout' in error_msg:
            return "Request timeout"
        elif 'authentication' in error_msg or '401' in error_msg:
            return "Authentication failed"
        elif '404' in error_msg and 'model' in error_msg:
            model_name = model or self.provider_configs[provider]['default_model']
            return f"Model '{model_name}' not found"
        elif 'connection' in error_msg or 'network' in error_msg:
            return "Connection error"
        else:
            return f"Provider error: {error}"
    
    def generate(self,
                prompt: str,
                system: Optional[str] = None,
                model: Optional[str] = None,
                temperature: float = 0.7,
                max_tokens: Optional[int] = None,
                provider: Optional[LLMProvider] = None) -> LLMResponse:
        """Generate response with smart fallback"""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        return self.chat(messages, model, temperature, max_tokens, provider)
    
    def chat(self,
             messages: List[Dict[str, str]],
             model: Optional[str] = None,
             temperature: float = 0.7,
             max_tokens: Optional[int] = None,
             provider: Optional[LLMProvider] = None) -> LLMResponse:
        """Generate response with intelligent provider selection"""
        
        self.logger.info(f"Chat request - {len(messages)} messages, provider: {provider or 'auto'}")
        
        # Get provider order
        provider_order = self._get_optimal_provider_order(provider)
        
        if not provider_order:
            raise LLMError("No healthy providers available")
        
        last_error = None
        
        # Try each provider in order
        for attempt, prov in enumerate(provider_order, 1):
            # Skip disabled providers
            if not self.provider_configs[prov]['enabled']:
                continue
                
            # Skip unhealthy providers
            if not self.provider_status[prov].should_try():
                continue
            
            try:
                self.logger.info(f"Attempt {attempt}: Trying {prov.value}")
                response = self._generate_with_provider(prov, messages, model, temperature, max_tokens)
                
                # Mark success
                self.provider_status[prov].mark_success()
                self.last_successful_provider = prov
                
                self.logger.info(f"[SUCCESS] {prov.value} responded in {response.response_time:.2f}s")
                return response
                
            except Exception as e:
                # Mark failure and categorize error
                self.provider_status[prov].mark_failure()
                error_description = self._categorize_error(e, prov, model)
                
                self.logger.warning(f"[FAILED] {prov.value}: {error_description}")
                last_error = e
        
        # All providers failed
        error_msg = f"All available providers failed. Last error: {last_error}"
        self.logger.error(error_msg)
        raise LLMError(error_msg)
    
    def _generate_with_provider(self,
                               provider: LLMProvider,
                               messages: List[Dict[str, str]],
                               model: Optional[str],
                               temperature: float,
                               max_tokens: Optional[int]) -> LLMResponse:
        """Generate response using specific provider"""
        
        start_time = time.time()
        
        # Get LLM instance
        llm = self._get_llm_instance(provider, model)
        
        # Configure parameters
        llm.temperature = temperature
        if max_tokens and hasattr(llm, 'max_tokens'):
            llm.max_tokens = max_tokens
        
        # Convert and invoke
        langchain_messages = self._convert_messages(messages)
        response = llm.invoke(langchain_messages)
        
        # Process response
        content = response.content.strip()
        if not content:
            raise LLMError(f"Empty response from {provider.value}")
        
        # Extract metadata
        response_model = getattr(response, 'model', model or self.provider_configs[provider]['default_model'])
        tokens = self._extract_token_count(response)
        response_time = time.time() - start_time
        
        self.logger.debug(f"Generated {len(content)} chars, {tokens or 'unknown'} tokens")
        
        return LLMResponse(
            content=content,
            provider=provider.value,
            model=response_model,
            tokens=tokens,
            response_time=response_time
        )
    
    def _extract_token_count(self, response) -> Optional[int]:
        """Extract token count from response metadata"""
        # Try different possible locations for token count
        if hasattr(response, 'usage_metadata'):
            return getattr(response.usage_metadata, 'output_tokens', None)
        
        if hasattr(response, 'response_metadata'):
            usage = response.response_metadata.get('usage', {})
            return usage.get('output_tokens') or usage.get('completion_tokens')
        
        return None
    
    def get_available_models(self, provider: LLMProvider) -> List[str]:
        """Get list of available models for a provider"""
        
        if not self.provider_configs[provider]['enabled']:
            return []
        
        model_lists = {
            LLMProvider.OLLAMA: [
                'llama3.2', 'llama3.1', 'llama3', 'mistral', 'codellama', 'gemma', 'phi3'
            ],
            LLMProvider.ANTHROPIC: [
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229', 
                'claude-3-haiku-20240307'
            ],
            LLMProvider.OPENAI: [
                'gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-3.5-turbo-16k'
            ]
        }
        
        return model_lists.get(provider, [])
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all providers"""
        status = {}
        
        for provider in LLMProvider:
            config_data = self.provider_configs[provider]
            health = self.provider_status[provider]
            
            status[provider.value] = {
                'enabled': config_data['enabled'],
                'healthy': health.is_healthy,
                'failure_count': health.failure_count,
                'default_model': config_data['default_model'],
                'available_models': self.get_available_models(provider)
            }
        
        return status
    
    def test_provider(self, provider: LLMProvider, model: Optional[str] = None) -> Dict[str, Any]:
        """Test a specific provider with a simple prompt"""
        try:
            self.logger.info(f"Testing {provider.value} provider...")
            start_time = time.time()
            
            response = self.generate(
                "Respond with exactly one word: 'Hello'",
                provider=provider,
                model=model
            )
            
            test_time = time.time() - start_time
            
            result = {
                'success': True,
                'response_time': test_time,
                'model': response.model,
                'content_length': len(response.content),
                'tokens': response.tokens
            }
            
            self.logger.info(f"[SUCCESS] {provider.value} test completed in {test_time:.2f}s")
            return result
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
            
            self.logger.error(f"[FAILED] {provider.value} test failed: {e}")
            return result
    
    def test_all_providers(self) -> Dict[str, Dict[str, Any]]:
        """Test all enabled providers"""
        results = {}
        
        for provider in LLMProvider:
            if self.provider_configs[provider]['enabled']:
                results[provider.value] = self.test_provider(provider)
            else:
                results[provider.value] = {
                    'success': False,
                    'error': 'Provider not enabled',
                    'error_type': 'ConfigurationError'
                }
        
        return results
    
    def reset_provider_health(self, provider: Optional[LLMProvider] = None):
        """Reset provider health status"""
        if provider:
            self.provider_status[provider] = ProviderStatus()
            self.logger.info(f"Reset health status for {provider.value}")
        else:
            self.provider_status = {p: ProviderStatus() for p in LLMProvider}
            self.logger.info("Reset health status for all providers")
    
    def clear_cache(self):
        """Clear LLM instance cache"""
        self._llm_instances.clear()
        self.logger.info("Cleared LLM instance cache")

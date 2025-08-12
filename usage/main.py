from core.config import config
from utils.logger import get_logger, setup_logging
from core.llm_manager import LLMManager, LLMProvider, LLMError

if __name__ == "__main__":
    # Setup logging
    logger = setup_logging("Chat")
    
    # Initialize LLM Manager (now with proper logging)
    llm = LLMManager()
    
    # Debug configuration if needed
    # llm.debug_configuration()
    
    try:
        response = llm.generate("What is Python?")
        print(f"Response from {response.provider}: {response.content}")
    except LLMError as e:
        logger.error(f"LLM Error: {e}")
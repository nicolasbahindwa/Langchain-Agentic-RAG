"""Simplified web scraping tool with proper async handling."""

import asyncio
import urllib.parse
import random
import os
import subprocess
import sys
from typing import List, Dict, Any, Tuple, Literal, Optional

from bs4 import BeautifulSoup, SoupStrainer
from langchain_core.documents import Document
from langchain_tavily import TavilySearch
from langchain_community.utilities.duckduckgo_search import DuckDuckGoSearchAPIWrapper
from langchain_community.document_loaders import (
    PlaywrightURLLoader,
    SeleniumURLLoader,
    WebBaseLoader,
    WikipediaLoader,
)

# Constants
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
]

DEFAULT_TIMEOUT = 30.0
FALLBACK_TIMEOUT = 15.0

def get_random_user_agent() -> str:
    """Get a random user agent to avoid detection."""
    return random.choice(USER_AGENTS)


def check_playwright_available(logger) -> bool:
    """Simple sync check for Playwright availability."""
    try:
        import playwright
        # Try to get the executable path without async context
        import subprocess
        result = subprocess.run([
            sys.executable, "-c", 
            "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            if os.path.exists(path):
                logger.success(f"Playwright Chromium available at: {path}")
                return True
        
        logger.debug("Playwright browser not found")
        return False
        
    except Exception as e:
        logger.debug(f"Playwright check failed: {e}")
        return False


def check_selenium_available(logger) -> bool:
    """Check if Selenium is available."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        logger.debug("Selenium modules available")
        return True
    except ImportError:
        logger.debug("Selenium not installed")
        return False


def install_playwright_browsers(logger) -> bool:
    """Install Playwright browsers."""
    try:
        logger.info("Installing Playwright browsers...")
        result = subprocess.run([
            sys.executable, "-m", "playwright", "install", "chromium"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.success("Playwright browsers installed successfully")
            return True
        else:
            logger.warning(f"Installation failed: {result.stderr}")
            return False
    except Exception as e:
        logger.warning(f"Installation error: {e}")
        return False


class SimpleBrowserManager:
    """Simple browser manager without async complications."""
    
    def __init__(self, logger):
        self.logger = logger
        self.playwright_available = False
        self.selenium_available = False
        self._check_browsers()
    
    def _check_browsers(self):
        """Check which browsers are available."""
        self.playwright_available = check_playwright_available(self.logger)
        self.selenium_available = check_selenium_available(self.logger)
        
        # Try to install Playwright if not available
        if not self.playwright_available:
            self.logger.debug("Attempting to install Playwright browsers...")
            if install_playwright_browsers(self.logger):
                self.playwright_available = check_playwright_available(self.logger)
    
    def get_config(self) -> Dict[str, Any]:
        """Get recommended configuration."""
        if self.playwright_available:
            return {
                "load_js": True,
                "use_playwright": True,
                "use_selenium": False,
                "reason": "Playwright available"
            }
        elif self.selenium_available:
            return {
                "load_js": True,
                "use_playwright": False,
                "use_selenium": True,
                "reason": "Selenium available (Playwright unavailable)"
            }
        else:
            return {
                "load_js": False,
                "use_playwright": False,
                "use_selenium": False,
                "reason": "No JavaScript browsers available, using static loading"
            }
    
    def log_status(self):
        """Log browser status."""
        self.logger.info("=== Browser Availability Status ===")
        self.logger.info(f"Playwright: {'✅ Available' if self.playwright_available else '❌ Not available'}")
        self.logger.info(f"Selenium: {'✅ Available' if self.selenium_available else '❌ Not available'}")
        
        config = self.get_config()
        self.logger.info(f"Recommended: {config['reason']}")


def _clean_text_lines(text: str, min_length: int = 15) -> List[str]:
    """Clean and filter text lines."""
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if len(line) > min_length and line.count(" ") > 2:
            lines.append(line)
    return lines


def _clean_html_content(html: str, base_url: str) -> str:
    """Extract and clean HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove unwanted elements
    for element in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "button", "input", "form"]):
        element.decompose()
    
    # Extract text
    text = soup.get_text(separator="\n", strip=True)
    lines = _clean_text_lines(text)
    return "\n\n".join(lines)


def _create_error_document(url: str, error_msg: str) -> Document:
    """Create error document."""
    return Document(
        page_content="",
        metadata={"source": url, "error": error_msg, "media": []}
    )


async def _safe_load_with_fallback(urls: List[str], user_agent: str, load_js: bool, use_playwright: bool, use_selenium: bool, logger) -> List[Document]:
    """Load documents with proper fallback handling."""
    
    # Try primary loader
    try:
        if load_js and use_playwright:
            logger.info("Using Playwright loader")
            loader = PlaywrightURLLoader(
                urls=urls,
                remove_selectors=["script", "style", "nav", "footer", "header"],
                continue_on_failure=True,
                headless=True
            )
        elif load_js and use_selenium:
            logger.info("Using Selenium loader")
            loader = SeleniumURLLoader(
                urls=urls,
                headless=True,
                arguments=[f'user-agent={user_agent}']
            )
        else:
            logger.info("Using WebBase loader (static)")
            loader = WebBaseLoader(
                web_paths=urls,
                requests_kwargs={
                    "headers": {"User-Agent": user_agent},
                    "timeout": DEFAULT_TIMEOUT,
                }
            )
        
        # Load with timeout
        if hasattr(loader, 'alazy_load'):
            docs = []
            async for doc in loader.alazy_load():
                if doc and hasattr(doc, "page_content") and doc.page_content.strip():
                    docs.append(doc)
            return docs
        else:
            return await asyncio.wait_for(
                asyncio.to_thread(loader.load),
                timeout=DEFAULT_TIMEOUT
            )
            
    except Exception as e:
        logger.warning(f"Primary loader failed: {e}")
        
        # Fallback to simple WebBaseLoader
        try:
            logger.info("Using fallback WebBase loader")
            fallback_loader = WebBaseLoader(
                web_paths=urls,
                requests_kwargs={
                    "headers": {"User-Agent": user_agent},
                    "timeout": FALLBACK_TIMEOUT,
                }
            )
            return await asyncio.wait_for(
                asyncio.to_thread(fallback_loader.load),
                timeout=FALLBACK_TIMEOUT
            )
        except Exception as fallback_error:
            logger.failure(f"All loaders failed: {fallback_error}")
            return [_create_error_document(url, f"Loading failed: {str(fallback_error)}") for url in urls]


async def simple_fetch(urls: List[str], logger, user_agent: str = None, **kwargs) -> List[Document]:
    """Simplified fetch function."""
    
    if user_agent is None:
        user_agent = get_random_user_agent()
    
    # Auto-detect browser capabilities
    browser_manager = SimpleBrowserManager(logger)
    browser_manager.log_status()
    config = browser_manager.get_config()
    
    logger.info(f"Using configuration: {config['reason']}")
    
    # Load documents
    logger.info(f"Fetching {len(urls)} URLs")
    raw_docs = await _safe_load_with_fallback(
        urls=urls,
        user_agent=user_agent,
        load_js=config["load_js"],
        use_playwright=config["use_playwright"], 
        use_selenium=config["use_selenium"],
        logger=logger
    )
    
    # Process documents
    processed_docs = []
    for doc in raw_docs:
        if not doc or not hasattr(doc, "page_content"):
            continue
        
        # Clean content if it looks like HTML
        if "<html" in doc.page_content.lower() or "<body" in doc.page_content.lower():
            base_url = doc.metadata.get("source", urls[0])
            doc.page_content = _clean_html_content(doc.page_content, base_url)
        
        # Add metadata
        doc.metadata["media"] = []
        processed_docs.append(doc)
    
    logger.success(f"Successfully processed {len(processed_docs)} documents")
    return processed_docs


async def simple_search(query: str, provider: str = "duckduckgo", max_results: int = 5, tavily_api_key: str = None, logger=None) -> Dict[str, Any]:
    """Simple search function."""
    try:
        if provider == "duckduckgo":
            tool = DuckDuckGoSearchAPIWrapper(max_results=max_results)
            results = await asyncio.to_thread(tool.run, query)
            logger.success(f"Search completed for: {query}")
            return {"provider": provider, "results": results, "query": query}
        elif provider == "tavily":
            # Pass API key directly if provided
            if tavily_api_key:
                tool = TavilySearch(max_results=max_results, api_key=tavily_api_key)
            else:
                # Fall back to environment variable
                tool = TavilySearch(max_results=max_results)
            results = await tool.ainvoke(query)
            logger.success(f"Search completed for: {query}")
            return {"provider": provider, "results": results, "query": query}
    except Exception as e:
        logger.failure(f"Search failed: {e}")
        return {"provider": provider, "results": [], "query": query, "error": str(e)}


async def simple_load_data(
    logger,
    urls: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    search_provider: str = "duckduckgo",
    search_max_results: int = 5,
    tavily_api_key: Optional[str] = None,  # Add API key parameter
    **kwargs
) -> Dict[str, Any]:
    """Simple data loading function."""
    
    result = {
        "documents": [],
        "search_results": {},
        "summary": {
            "urls_fetched": 0,
            "search_performed": False,
            "total_documents": 0,
            "errors": []
        }
    }
    
    # Fetch URLs if provided
    if urls:
        try:
            documents = await simple_fetch(urls, logger, **kwargs)
            result["documents"] = documents
            result["summary"]["urls_fetched"] = len([d for d in documents if "error" not in d.metadata])
            
            # Collect errors  
            errors = [d.metadata.get("error") for d in documents if "error" in d.metadata]
            result["summary"]["errors"].extend([e for e in errors if e])
            
        except Exception as e:
            logger.failure(f"URL fetching failed: {e}")
            result["summary"]["errors"].append(f"URL fetching failed: {str(e)}")
    
    # Perform search if requested
    if search_query:
        result["summary"]["search_performed"] = True
        try:
            search_results = await simple_search(
                query=search_query,
                provider=search_provider,
                max_results=search_max_results,
                tavily_api_key=tavily_api_key,  # Pass API key
                logger=logger
            )
            result["search_results"] = search_results
        except Exception as e:
            logger.failure(f"Search failed: {e}")
            result["summary"]["errors"].append(f"Search failed: {str(e)}")
    
    # Calculate totals
    result["summary"]["total_documents"] = len(result["documents"])
    
    # Log summary
    summary = result["summary"]
    if summary["total_documents"] > 0:
        logger.success(f"Data loading completed: {summary['total_documents']} documents")
    else:
        logger.warning("No documents were loaded")
    
    if summary["errors"]:
        logger.warning(f"Encountered {len(summary['errors'])} errors")
    
    return result


async def main():
    """Simple test function."""
    class SimpleLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def success(self, msg): print(f"SUCCESS: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def failure(self, msg): print(f"ERROR: {msg}")
        def debug(self, msg): print(f"DEBUG: {msg}")
    
    logger = SimpleLogger()
    
    logger.info("=== Testing Simplified Web Scraper ===")
    
    try:
        # Example 1: Using DuckDuckGo (no API key needed)
        logger.info("--- Test 1: DuckDuckGo Search ---")
        result1 = await simple_load_data(
            logger=logger,
            urls=["https://httpbin.org/html"],
            search_query="python web scraping",
            search_provider="duckduckgo",
            search_max_results=2
        )
        
        logger.info(f"DuckDuckGo results: {result1['summary']}")
        
        # Example 2: Using Tavily with API key (if you have one)
        logger.info("--- Test 2: Tavily Search with API Key ---")
        
        # Replace with your actual API key or load from config
        tavily_key = "your-tavily-api-key-here"  # Or load from config
        
        result2 = await simple_load_data(
            logger=logger,
            search_query="barack obama biography",
            search_provider="tavily",
            search_max_results=3,
            tavily_api_key=tavily_key  # Pass API key directly
        )
        
        logger.info(f"Tavily results: {result2['summary']}")
        
        # Show search results structure
        if 'error' not in result1['search_results']:
            logger.success("✅ DuckDuckGo search successful")
        if 'error' not in result2['search_results']:
            logger.success("✅ Tavily search successful")
        else:
            logger.warning("❌ Tavily search failed (check API key)")
            
    except Exception as e:
        logger.failure(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
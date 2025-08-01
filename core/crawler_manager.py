import asyncio
import urllib.parse
import random
import os
import subprocess
import sys
import time
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add the root directory to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PlaywrightURLLoader,
    SeleniumURLLoader,
    WebBaseLoader,
)

from utils.logger import get_enhanced_logger

# Constants
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
]

DEFAULT_TIMEOUT = 30.0


@dataclass
class CrawlResult:
    """Result of a crawling operation"""
    url: str
    success: bool
    content: str
    metadata: Dict[str, Any]
    error: Optional[str] = None
    loader_used: Optional[str] = None
    processing_time: Optional[float] = None


class BrowserManager:
    """Manages browser availability and configuration"""
    
    def __init__(self, logger):
        self.logger = logger
        self.playwright_available = self._check_playwright_available()
        self.selenium_available = self._check_selenium_available()
        
        # Try to install Playwright if not available
        if not self.playwright_available:
            if self._install_playwright_browsers():
                self.playwright_available = self._check_playwright_available()
    
    def _check_playwright_available(self) -> bool:
        """Check if Playwright is available with browsers installed"""
        try:
            import playwright
            result = subprocess.run([
                sys.executable, "-c", 
                "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                return os.path.exists(path)
            return False
            
        except Exception:
            return False
    
    def _check_selenium_available(self) -> bool:
        """Check if Selenium is available"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            return True
        except ImportError:
            return False
    
    def _install_playwright_browsers(self) -> bool:
        """Install Playwright browsers"""
        try:
            self.logger.info("Installing Playwright browsers...")
            result = subprocess.run([
                sys.executable, "-m", "playwright", "install", "chromium"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.logger.success("Playwright browsers installed successfully")
                return True
            else:
                self.logger.warning(f"Installation failed: {result.stderr}")
                return False
        except Exception as e:
            self.logger.warning(f"Installation error: {e}")
            return False
    
    def get_loader_preference(self) -> str:
        """Get recommended loader"""
        if self.playwright_available:
            return "playwright"
        elif self.selenium_available:
            return "selenium"
        else:
            return "webbase"
    
    def get_status(self) -> Dict[str, bool]:
        """Get browser availability status"""
        return {
            "playwright": self.playwright_available,
            "selenium": self.selenium_available,
            "webbase": True
        }


class ContentProcessor:
    """Handles content cleaning and processing"""
    
    @staticmethod
    def get_random_user_agent() -> str:
        """Get a random user agent"""
        return random.choice(USER_AGENTS)
    
    @staticmethod
    def clean_text_lines(text: str, min_length: int = 15) -> List[str]:
        """Clean and filter text lines"""
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > min_length and line.count(" ") > 2:
                lines.append(line)
        return lines
    
    @staticmethod
    def clean_html_content(html: str, base_url: str = "") -> str:
        """Extract and clean HTML content"""
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove unwanted elements
        unwanted_tags = [
            "script", "style", "noscript", "nav", "header", "footer", 
            "aside", "button", "input", "form", "iframe", "object", "embed"
        ]
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove navigation elements
        unwanted_selectors = [
            {"class": ["nav", "navigation", "menu", "sidebar"]},
            {"id": ["nav", "navigation", "menu", "sidebar", "header", "footer"]}
        ]
        
        for selector in unwanted_selectors:
            for key, values in selector.items():
                for value in values:
                    for element in soup.find_all(attrs={key: lambda x: x and value in str(x).lower()}):
                        element.decompose()
        
        # Extract and clean text
        text = soup.get_text(separator="\n", strip=True)
        lines = ContentProcessor.clean_text_lines(text)
        return "\n\n".join(lines)
    
    @staticmethod
    def is_html_content(content: str) -> bool:
        """Check if content appears to be HTML"""
        return any(tag in content.lower() for tag in ["<html", "<body", "<div"])
    
    @staticmethod
    def is_security_blocked(content: str) -> bool:
        """Check if content indicates security blocking"""
        blocking_indicators = [
            "verifying you are human", "cloudflare", "ddos protection",
            "please wait while we verify", "security check", "human verification",
            "captcha", "bot detection"
        ]
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in blocking_indicators)
    
    @staticmethod
    def extract_metadata(content: str, url: str) -> Dict[str, Any]:
        """Extract metadata from content"""
        metadata = {
            "source": url,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(content),
            "is_html": ContentProcessor.is_html_content(content),
            "is_blocked": ContentProcessor.is_security_blocked(content)
        }
        
        if metadata["is_html"]:
            try:
                soup = BeautifulSoup(content, "html.parser")
                
                # Extract title
                title_tag = soup.find("title")
                if title_tag:
                    metadata["title"] = title_tag.get_text().strip()
                
                # Extract meta description
                desc_tag = soup.find("meta", attrs={"name": "description"})
                if desc_tag:
                    metadata["description"] = desc_tag.get("content", "").strip()
                
                # Extract language
                html_tag = soup.find("html")
                if html_tag and html_tag.get("lang"):
                    metadata["language"] = html_tag.get("lang")
                
            except Exception:
                pass
        
        return metadata


class WebCrawlerManager:
    """Main web crawler manager"""
    
    def __init__(self, logger=None):
        self.logger = logger or get_enhanced_logger("crawler_manager")
        self.browser_manager = BrowserManager(self.logger)
        self.content_processor = ContentProcessor()
        self._crawl_stats = {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "blocked": 0,
            "loaders_used": {}
        }
    
    def _create_error_result(self, url: str, error_msg: str, loader_used: str = None) -> CrawlResult:
        """Create error result"""
        return CrawlResult(
            url=url,
            success=False,
            content="",
            metadata={"source": url, "error": error_msg, "timestamp": datetime.now().isoformat()},
            error=error_msg,
            loader_used=loader_used
        )
    
    async def _load_with_playwright(self, urls: List[str], user_agent: str) -> List[Document]:
        """Load URLs using Playwright"""
        loader = PlaywrightURLLoader(
            urls=urls,
            remove_selectors=["script", "style", "nav", "footer", "header", "aside"],
            continue_on_failure=True,
            headless=True
        )
        
        return await asyncio.wait_for(
            asyncio.to_thread(loader.load),
            timeout=DEFAULT_TIMEOUT + 10
        )
    
    async def _load_with_selenium(self, urls: List[str], user_agent: str) -> List[Document]:
        """Load URLs using Selenium"""
        selenium_args = [
            f'--user-agent={user_agent}',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--headless',
            '--window-size=1920,1080'
        ]
        
        loader = SeleniumURLLoader(
            urls=urls,
            headless=True,
            arguments=selenium_args
        )
        
        return await asyncio.wait_for(
            asyncio.to_thread(loader.load),
            timeout=DEFAULT_TIMEOUT
        )
    
    async def _load_with_webbase(self, urls: List[str], user_agent: str) -> List[Document]:
        """Load URLs using WebBase loader"""
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        loader = WebBaseLoader(
            web_paths=urls,
            requests_kwargs={
                "headers": headers,
                "timeout": DEFAULT_TIMEOUT,
                "allow_redirects": True,
            }
        )
        
        return await asyncio.wait_for(
            asyncio.to_thread(loader.load),
            timeout=DEFAULT_TIMEOUT
        )
    
    async def _load_with_fallback(self, urls: List[str], user_agent: str, 
                                 preferred_loader: str = None) -> List[Document]:
        """Load documents with automatic fallback"""
        status = self.browser_manager.get_status()
        
        # Determine loader order
        if preferred_loader and status.get(preferred_loader):
            loader_order = [preferred_loader]
        else:
            preference = self.browser_manager.get_loader_preference()
            loader_order = [preference]
        
        # Add fallback loaders
        all_loaders = ["playwright", "selenium", "webbase"]
        for loader in all_loaders:
            if loader not in loader_order and status.get(loader, True):
                loader_order.append(loader)
        
        # Try each loader
        for loader_name in loader_order:
            try:
                if loader_name == "playwright":
                    docs = await self._load_with_playwright(urls, user_agent)
                elif loader_name == "selenium":
                    docs = await self._load_with_selenium(urls, user_agent)
                else:  # webbase
                    docs = await self._load_with_webbase(urls, user_agent)
                
                # Check for blocking
                if docs:
                    blocked_count = sum(1 for doc in docs 
                                      if hasattr(doc, 'page_content') and 
                                      self.content_processor.is_security_blocked(doc.page_content))
                    
                    # If all documents are blocked, try next loader
                    if blocked_count == len(docs) and loader_name != loader_order[-1]:
                        self.logger.warning(f"All content blocked with {loader_name}, trying next loader")
                        continue
                
                # Update stats and metadata
                self._crawl_stats["loaders_used"][loader_name] = self._crawl_stats["loaders_used"].get(loader_name, 0) + len(urls)
                for doc in docs:
                    if hasattr(doc, 'metadata'):
                        doc.metadata["loader_used"] = loader_name
                
                return docs
                
            except Exception as e:
                self.logger.warning(f"{loader_name} loader failed: {e}")
                continue
        
        # All loaders failed
        return [Document(
            page_content="",
            metadata={"source": url, "error": "All loaders failed", "loader_used": "none"}
        ) for url in urls]
    
    def _process_documents(self, docs: List[Document]) -> List[CrawlResult]:
        """Process loaded documents into CrawlResults"""
        results = []
        
        for doc in docs:
            if not doc or not hasattr(doc, "page_content"):
                continue
            
            url = doc.metadata.get("source", "unknown")
            loader_used = doc.metadata.get("loader_used", "unknown")
            
            # Check for errors
            if "error" in doc.metadata:
                result = self._create_error_result(url, doc.metadata["error"], loader_used)
                results.append(result)
                continue
            
            # Process content
            content = doc.page_content
            if self.content_processor.is_html_content(content):
                content = self.content_processor.clean_html_content(content, url)
            
            # Extract metadata
            metadata = self.content_processor.extract_metadata(doc.page_content, url)
            metadata.update(doc.metadata)
            
            # Check if blocked
            is_blocked = metadata.get("is_blocked", False)
            if is_blocked:
                self._crawl_stats["blocked"] += 1
            
            # Create result
            result = CrawlResult(
                url=url,
                success=not is_blocked,
                content=content,
                metadata=metadata,
                loader_used=loader_used
            )
            results.append(result)
        
        return results
    
    async def crawl_urls(self, urls: Union[str, List[str]], 
                        user_agent: str = None,
                        preferred_loader: str = None,
                        **kwargs) -> List[CrawlResult]:
        """
        Crawl one or more URLs
        
        Args:
            urls: Single URL string or list of URLs
            user_agent: Custom user agent (optional)
            preferred_loader: Preferred loader ("playwright", "selenium", "webbase")
            
        Returns:
            List of CrawlResult objects
        """
        # Normalize URLs input
        if isinstance(urls, str):
            urls = [urls]
        
        if not urls:
            return []
        
        # Set user agent
        if user_agent is None:
            user_agent = self.content_processor.get_random_user_agent()
        
        # Update stats
        self._crawl_stats["total_attempts"] += len(urls)
        
        self.logger.info(f"Crawling {len(urls)} URLs")
        start_time = datetime.now()
        
        try:
            # Load documents
            docs = await self._load_with_fallback(urls, user_agent, preferred_loader)
            
            # Process results
            results = self._process_documents(docs)
            
            # Update stats
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            self._crawl_stats["successful"] += successful
            self._crawl_stats["failed"] += failed
            
            # Add processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            for result in results:
                result.processing_time = processing_time / len(results)
            
            self.logger.success(f"Crawl completed: {successful} successful, {failed} failed")
            return results
            
        except Exception as e:
            self.logger.failure(f"Crawl failed: {e}")
            return [self._create_error_result(url, f"Crawl failed: {str(e)}") for url in urls]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get crawling statistics"""
        return self._crawl_stats.copy()
    
    def reset_stats(self):
        """Reset crawling statistics"""
        self._crawl_stats = {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "blocked": 0,
            "loaders_used": {}
        }


# Convenience functions
async def crawl_single_url(url: str, logger=None, **kwargs) -> CrawlResult:
    """Convenience function to crawl a single URL"""
    crawler = WebCrawlerManager(logger)
    results = await crawler.crawl_urls([url], **kwargs)
    return results[0] if results else None


async def crawl_multiple_urls(urls: List[str], logger=None, **kwargs) -> List[CrawlResult]:
    """Convenience function to crawl multiple URLs"""
    crawler = WebCrawlerManager(logger)
    return await crawler.crawl_urls(urls, **kwargs)


# Test function for running the script directly
async def test_crawler():
    """Test the crawler with a simple URL"""
    print("Testing Enhanced Web Crawler Manager")
    
    crawler = WebCrawlerManager()
    test_url = "https://httpbin.org/html"
    
    print(f"Crawling: {test_url}")
    results = await crawler.crawl_urls([test_url])
    
    if results:
        result = results[0]
        print(f"Success: {result.success}")
        print(f"Loader used: {result.loader_used}")
        print(f"Content length: {len(result.content)} characters")
        if result.content:
            preview = result.content[:200].replace('\n', ' ')
            print(f"Content preview: {preview}...")
    else:
        print("No results returned")


if __name__ == "__main__":
    asyncio.run(test_crawler())
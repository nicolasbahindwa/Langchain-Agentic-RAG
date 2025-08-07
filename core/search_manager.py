import json
import re
from typing import Dict, List, Optional, Any, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import wikipedia
from ddgs import DDGS

# LangChain imports
try:
    from langchain_tavily import TavilySearch as TavilySearchResults
except ImportError:
    try:
        # Fallback to community version if langchain_tavily not available
        from langchain_community.tools.tavily_search import TavilySearchResults
    except ImportError:
        TavilySearchResults = None

from langchain_core.documents.base import Document
from langchain_core.tools import BaseTool
from .config import config


@dataclass
class SearchResult:
    """Standardized search result structure"""
    title: str
    url: str
    content: str
    snippet: str
    source: str
    metadata: Dict[str, Any]
    score: Optional[float] = None
    published_date: Optional[str] = None


class SearchProvider(ABC):
    """Abstract base class for search providers - pure search functionality only"""
    
    @abstractmethod
    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """Perform search and return clean, standardized results"""
        pass
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common artifacts
        text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
        text = re.sub(r'\[edit\]', '', text)  # Remove Wikipedia edit links
        text = re.sub(r'\[\d+\]', '', text)   # Remove reference numbers
        
        return text
    
    def _create_search_result(self, title: str, url: str, content: str, 
                            metadata: Dict[str, Any], snippet: str = None) -> SearchResult:
        """Create a standardized search result"""
        clean_content = self._clean_text(content)
        clean_title = self._clean_text(title)
        clean_snippet = self._clean_text(snippet) if snippet else clean_content[:300] + "..."
        
        return SearchResult(
            title=clean_title,
            url=url,
            content=clean_content,
            snippet=clean_snippet,
            source=metadata.get("source", "unknown"),
            metadata=metadata,
            score=metadata.get("score"),
            published_date=metadata.get("published_date")
        )
    
    def _create_document(self, search_result: SearchResult) -> Document:
        """Convert SearchResult to LangChain Document"""
        return Document(
            page_content=search_result.content,
            metadata={
                "title": search_result.title,
                "url": search_result.url,
                "source": search_result.source,
                "snippet": search_result.snippet,
                "score": search_result.score,
                "published_date": search_result.published_date,
                **search_result.metadata
            }
        )


class TavilySearchProvider(SearchProvider):
    """Tavily search provider - returns clean search results only"""
    
    def __init__(self):
        if TavilySearchResults is None:
            raise ImportError("Tavily search not available. Install with: pip install langchain-tavily")
        
        try:
            # Initialize TavilySearch with API key
            self.tool = TavilySearchResults(api_key=config.api_keys.tavily_api_key)
        except Exception as e:
            raise ImportError(f"Could not initialize Tavily search: {e}")
    
    def search(self, query: str, max_results: int = 5, search_depth: str = "advanced", 
               include_images: bool = False, **kwargs) -> Dict[str, Any]:
        """Search using Tavily - returns clean search results only"""
        try:
            # Handle different API versions and methods
            raw_results = None
            
            try:
                # Method 1: Try with invoke method and string query
                raw_results = self.tool.invoke(query)
                print(f"Debug: Tavily invoke(query) returned: {type(raw_results)} - {raw_results}")
            except Exception as e1:
                try:
                    # Method 2: Try with invoke method and dict
                    raw_results = self.tool.invoke({"query": query})
                    print(f"Debug: Tavily invoke(dict) returned: {type(raw_results)} - {raw_results}")
                except Exception as e2:
                    try:
                        # Method 3: Try with run method
                        raw_results = self.tool.run(query)
                        print(f"Debug: Tavily run() returned: {type(raw_results)} - {raw_results}")
                    except Exception as e3:
                        try:
                            # Method 4: Try with search method if available
                            if hasattr(self.tool, 'search'):
                                raw_results = self.tool.search(query, max_results=max_results)
                                print(f"Debug: Tavily search() returned: {type(raw_results)} - {raw_results}")
                            else:
                                print(f"Debug: Available methods: {[m for m in dir(self.tool) if not m.startswith('_')]}")
                                raise Exception(f"All invoke methods failed: {e1}, {e2}, {e3}")
                        except Exception as e4:
                            raise Exception(f"All Tavily methods failed: {e1}, {e2}, {e3}, {e4}")
            
            # Process results based on what we got back
            search_results = []
            documents = []
            
            if raw_results is None:
                pass  # No results
            elif isinstance(raw_results, str):
                # If it's just a string, create a single result
                metadata = {
                    "source": "tavily",
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                }
                
                search_result = self._create_search_result(
                    title=f"Tavily Result for: {query}",
                    url="",
                    content=raw_results,
                    metadata=metadata
                )
                
                search_results.append(search_result)
                documents.append(self._create_document(search_result))
                
            elif isinstance(raw_results, list):
                # If it's a list of results
                for result in raw_results:
                    if isinstance(result, dict):
                        metadata = {
                            "source": "tavily",
                            "query": query,
                            "search_depth": search_depth,
                            "score": result.get("score", 0.0),
                            "published_date": result.get("published_date", ""),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        search_result = self._create_search_result(
                            title=result.get("title", ""),
                            url=result.get("url", ""),
                            content=result.get("content", "") or result.get("snippet", ""),
                            metadata=metadata
                        )
                        
                        search_results.append(search_result)
                        documents.append(self._create_document(search_result))
                    elif isinstance(result, str):
                        # Handle string results in list
                        metadata = {
                            "source": "tavily",
                            "query": query,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        search_result = self._create_search_result(
                            title=f"Tavily Result for: {query}",
                            url="",
                            content=result,
                            metadata=metadata
                        )
                        
                        search_results.append(search_result)
                        documents.append(self._create_document(search_result))
                        
            elif isinstance(raw_results, dict):
                # If it's a single dict result
                if "results" in raw_results:
                    # Handle nested results
                    for result in raw_results["results"]:
                        metadata = {
                            "source": "tavily",
                            "query": query,
                            "search_depth": search_depth,
                            "score": result.get("score", 0.0),
                            "published_date": result.get("published_date", ""),
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        search_result = self._create_search_result(
                            title=result.get("title", ""),
                            url=result.get("url", ""),
                            content=result.get("content", "") or result.get("snippet", ""),
                            metadata=metadata
                        )
                        
                        search_results.append(search_result)
                        documents.append(self._create_document(search_result))
                else:
                    # Handle direct dict result
                    metadata = {
                        "source": "tavily",
                        "query": query,
                        "search_depth": search_depth,
                        "score": raw_results.get("score", 0.0),
                        "published_date": raw_results.get("published_date", ""),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    search_result = self._create_search_result(
                        title=raw_results.get("title", ""),
                        url=raw_results.get("url", ""),
                        content=raw_results.get("content", "") or raw_results.get("snippet", ""),
                        metadata=metadata
                    )
                    
                    search_results.append(search_result)
                    documents.append(self._create_document(search_result))
            
            return {
                "provider": "tavily",
                "query": query,
                "search_results": search_results,
                "documents": documents,
                "status": "success",
                "count": len(search_results),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "provider": "tavily",
                "query": query,
                "search_results": [],
                "documents": [],
                "error": f"Tavily API error: {str(e)}",
                "status": "error",
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }


class WikipediaSearchProvider(SearchProvider):
    """Wikipedia search provider - returns clean search results only"""
    
    def __init__(self, language: str = "en"):
        self.language = language
        wikipedia.set_lang(language)
    
    def search(self, query: str, max_results: int = 5, auto_suggest: bool = True, 
               full_content: bool = False, summary_sentences: int = 3, **kwargs) -> Dict[str, Any]:
        """Search Wikipedia - returns clean search results only"""
        try:
            # Search for articles
            search_titles = wikipedia.search(query, results=max_results, suggestion=auto_suggest)
            
            if not search_titles:
                return {
                    "provider": "wikipedia",
                    "query": query,
                    "search_results": [],
                    "documents": [],
                    "status": "success",
                    "count": 0,
                    "message": "No Wikipedia articles found for query",
                    "timestamp": datetime.now().isoformat()
                }
            
            search_results = []
            documents = []
            
            for title in search_titles:
                # Handle case where title might be a list or other type
                if isinstance(title, list):
                    if len(title) > 0:
                        title = str(title[0])  # Take first element
                    else:
                        continue
                elif not isinstance(title, str):
                    title = str(title)  # Convert to string
                
                # Clean and validate title
                title = title.strip() if title else ""
                if not title:
                    continue
                    
                try:
                    # Get page summary first to avoid issues
                    summary = wikipedia.summary(title, sentences=summary_sentences, auto_suggest=False)
                    
                    # Then get the full page if needed
                    if full_content:
                        page = wikipedia.page(title, auto_suggest=False)
                        content = page.content
                        page_url = page.url
                        page_title = page.title
                    else:
                        content = summary
                        # Create URL manually if we don't have the page object
                        page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        page_title = title
                    
                    metadata = {
                        "source": "wikipedia",
                        "query": query,
                        "language": self.language,
                        "content_type": "full" if full_content else "summary",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    search_result = self._create_search_result(
                        title=page_title,
                        url=page_url,
                        content=content,
                        metadata=metadata
                    )
                    
                    search_results.append(search_result)
                    documents.append(self._create_document(search_result))
                    
                except wikipedia.exceptions.DisambiguationError as e:
                    # Handle disambiguation by taking first option
                    if e.options and len(e.options) > 0:
                        try:
                            first_option = str(e.options[0])
                            summary = wikipedia.summary(first_option, sentences=summary_sentences, auto_suggest=False)
                            page_url = f"https://en.wikipedia.org/wiki/{first_option.replace(' ', '_')}"
                            
                            metadata = {
                                "source": "wikipedia",
                                "query": query,
                                "language": self.language,
                                "disambiguation_resolved": True,
                                "original_query": title,
                                "resolved_to": first_option,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            search_result = self._create_search_result(
                                title=first_option,
                                url=page_url,
                                content=summary,
                                metadata=metadata
                            )
                            
                            search_results.append(search_result)
                            documents.append(self._create_document(search_result))
                        except Exception as inner_e:
                            print(f"Warning: Could not resolve disambiguation for {title}: {inner_e}")
                            continue
                            
                except wikipedia.exceptions.PageError as e:
                    print(f"Warning: Wikipedia page not found for {title}: {e}")
                    continue
                except Exception as e:
                    print(f"Warning: Error processing Wikipedia result for {title}: {e}")
                    continue
            
            return {
                "provider": "wikipedia",
                "query": query,
                "search_results": search_results,
                "documents": documents,
                "status": "success",
                "count": len(search_results),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "provider": "wikipedia",
                "query": query,
                "search_results": [],
                "documents": [],
                "error": str(e),
                "status": "error",
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }


class DuckDuckGoSearchProvider(SearchProvider):
    """DuckDuckGo search provider - returns clean search results only"""
    
    def __init__(self):
        self.ddgs = DDGS()
    
    def search(self, query: str, max_results: int = 5, region: str = "wt-wt", 
               safesearch: str = "moderate", timelimit: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Search using DuckDuckGo - returns clean search results only"""
        try:
            # Call ddgs.text() with query as first positional argument
            search_results = []
            documents = []
            
            # Pass query as positional argument, others as keyword args
            for result in self.ddgs.text(
                query,
                region=region,
                safesearch=safesearch,
                max_results=max_results,
                timelimit=timelimit
            ):
                metadata = {
                    "source": "duckduckgo",
                    "query": query,
                    "region": region,
                    "safesearch": safesearch,
                    "published": result.get("published", ""),
                    "timestamp": datetime.now().isoformat()
                }
                
                search_result = self._create_search_result(
                    title=result.get("title", ""),
                    url=result.get("href", ""),
                    content=result.get("body", ""),
                    metadata=metadata
                )
                
                search_results.append(search_result)
                documents.append(self._create_document(search_result))
            
            return {
                "provider": "duckduckgo",
                "query": query,
                "search_results": search_results,
                "documents": documents,
                "status": "success",
                "count": len(search_results),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "provider": "duckduckgo",
                "query": query,
                "search_results": [],
                "documents": [],
                "error": str(e),
                "status": "error",
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }

class SearchManager:
    """Pure search manager - returns clean search results only, no decision making"""
    
    def __init__(self):
        self.providers = {}
    
    def add_provider(self, name: str, provider: SearchProvider):
        """Add a search provider"""
        self.providers[name] = provider
    
    def search(self, query: str, provider: str = "duckduckgo", **kwargs) -> Dict[str, Any]:
        """
        Perform search using specified provider - returns clean results only
        
        Args:
            query: Search query string
            provider: Name of the provider to use
            **kwargs: Provider-specific arguments
        """
        if provider not in self.providers:
            return {
                "provider": provider,
                "query": query,
                "error": f"Provider '{provider}' not found",
                "available_providers": list(self.providers.keys()),
                "status": "error",
                "search_results": [],
                "documents": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        result = self.providers[provider].search(query, **kwargs)
        # Ensure provider key is always present
        if "provider" not in result:
            result["provider"] = provider
        return result
    
    def multi_search(self, query: str, providers: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Search across multiple providers - returns aggregated clean results only
        
        Args:
            query: Search query string
            providers: List of provider names to use (defaults to all available)
            **kwargs: Common arguments for all providers
        """
        if providers is None:
            providers = list(self.providers.keys())
        
        all_search_results = []
        all_documents = []
        results_by_provider = {}
        total_count = 0
        
        for provider in providers:
            if provider in self.providers:
                result = self.search(query, provider, **kwargs)
                results_by_provider[provider] = result
                
                if result.get("status") == "success":
                    all_search_results.extend(result.get("search_results", []))
                    all_documents.extend(result.get("documents", []))
                    total_count += result.get("count", 0)
        
        return {
            "query": query,
            "search_results": all_search_results,
            "documents": all_documents,
            "results_by_provider": results_by_provider,
            "total_count": total_count,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_available_providers(self) -> List[str]:
        """Get list of available search providers"""
        return list(self.providers.keys())


class ResultCleaner:
    """Utility class for cleaning and formatting search results"""
    
    @staticmethod
    def deduplicate_results(search_results: List[SearchResult], 
                          similarity_threshold: float = 0.9) -> List[SearchResult]:
        """Remove duplicate search results based on URL and title similarity"""
        if not search_results:
            return []
        
        cleaned_results = []
        seen_urls = set()
        seen_titles = set()
        
        for result in search_results:
            # Skip if URL already seen
            if result.url and result.url in seen_urls:
                continue
            
            # Skip if title is very similar to existing
            title_lower = result.title.lower()
            if any(ResultCleaner._similarity_score(title_lower, seen_title) > similarity_threshold 
                   for seen_title in seen_titles):
                continue
            
            cleaned_results.append(result)
            if result.url:
                seen_urls.add(result.url)
            seen_titles.add(title_lower)
        
        return cleaned_results
    
    @staticmethod
    def _similarity_score(text1: str, text2: str) -> float:
        """Simple similarity score between two text strings"""
        if not text1 or not text2:
            return 0.0
        
        # Simple word-based similarity
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    @staticmethod
    def filter_by_quality(search_results: List[SearchResult], 
                         min_content_length: int = 100,
                         require_url: bool = True) -> List[SearchResult]:
        """Filter search results by quality metrics"""
        filtered = []
        
        for result in search_results:
            # Check minimum content length
            if len(result.content) < min_content_length:
                continue
            
            # Check if URL is required and present
            if require_url and not result.url:
                continue
            
            # Check for meaningful title
            if not result.title or len(result.title.strip()) < 3:
                continue
            
            filtered.append(result)
        
        return filtered
    
    @staticmethod
    def sort_by_relevance(search_results: List[SearchResult]) -> List[SearchResult]:
        """Sort search results by relevance (score if available, otherwise by content length)"""
        def sort_key(result):
            if result.score is not None:
                return result.score
            return len(result.content)  # Fallback to content length
        
        return sorted(search_results, key=sort_key, reverse=True)


# Setup function
def create_search_manager(wikipedia_language: str = "en") -> SearchManager:
    """
    Create a search manager with all available providers
    
    Args:
        wikipedia_language: Language for Wikipedia searches
    """
    manager = SearchManager()
    
    # Add DuckDuckGo provider (no API key required)
    manager.add_provider("duckduckgo", DuckDuckGoSearchProvider())
    
    # Add Wikipedia provider
    manager.add_provider("wikipedia", WikipediaSearchProvider(language=wikipedia_language))
    
    # Add Tavily provider if available
    if TavilySearchResults is not None:
        try:
            if hasattr(config, 'api_keys') and hasattr(config.api_keys, 'tavily_api_key') and config.api_keys.tavily_api_key:
                manager.add_provider("tavily", TavilySearchProvider())
                print("Info: Tavily provider initialized successfully.")
            else:
                print("Info: Tavily API key not configured in config.py. Tavily provider not available.")
        except Exception as e:
            print(f"Warning: Could not initialize Tavily provider: {e}")
    else:
        print("Info: langchain-tavily not installed. Run 'pip install langchain-tavily' for Tavily search support.")
    
    available_providers = manager.get_available_providers()
    print(f"Search manager initialized with providers: {available_providers}")
    return manager


# Example usage
if __name__ == "__main__":
    print("=== TESTING SEARCH MANAGER ===")
    
    # Initialize search manager
    search_manager = create_search_manager()
    
    # Test single provider searches
    query = "japan economy current state"
    print(f"\n🔍 Testing query: '{query}'")
    
    # Test each provider individually
    for provider in search_manager.get_available_providers():
        print(f"\n--- Testing {provider.upper()} ---")
        results = search_manager.search(query, provider=provider, max_results=2)
        
        print(f"Status: {results.get('status', 'unknown')}")
        print(f"Results Count: {results.get('count', 0)}")
        
        if results.get('status') == 'error':
            print(f"❌ Error: {results.get('error', 'Unknown error')}")
        elif results.get('status') == 'success' and results.get('search_results'):
            print("✅ Success! Sample results:")
            for i, search_result in enumerate(results['search_results'][:1], 1):  # Show only first result
                print(f"  {i}. {search_result.title}")
                print(f"     URL: {search_result.url}")
                print(f"     Preview: {search_result.snippet[:100]}...")
        else:
            print("⚠️  No results found")
    
    # Test multi-provider search if at least one provider works
    working_providers = []
    for provider in search_manager.get_available_providers():
        test_result = search_manager.search("test", provider=provider, max_results=1)
        if test_result.get('status') == 'success':
            working_providers.append(provider)
    
    if len(working_providers) > 1:
        print(f"\n{'='*60}")
        print("🔄 MULTI-PROVIDER SEARCH TEST")
        print(f"{'='*60}")
        
        multi_results = search_manager.multi_search(query, providers=working_providers[:2])  # Test with 2 providers
        
        if multi_results.get('status') == 'success' and multi_results.get('search_results'):
            # Clean and filter results
            cleaner = ResultCleaner()
            clean_results = cleaner.deduplicate_results(multi_results['search_results'])
            quality_results = cleaner.filter_by_quality(clean_results, min_content_length=50)
            sorted_results = cleaner.sort_by_relevance(quality_results)
            
            print(f"✅ Multi-search successful!")
            print(f"   Original results: {multi_results.get('total_count', 0)}")
            print(f"   After cleaning: {len(sorted_results)}")
            
            if sorted_results:
                print("   Top result:")
                top_result = sorted_results[0]
                print(f"   - {top_result.title}")
                print(f"   - Source: {top_result.source}")
                print(f"   - Preview: {top_result.snippet[:150]}...")
        else:
            print("❌ Multi-search failed:")
            if 'results_by_provider' in multi_results:
                for provider, result in multi_results['results_by_provider'].items():
                    if result.get('status') == 'error':
                        print(f"   {provider}: {result.get('error', 'Unknown error')}")
    else:
        print(f"\n⚠️  Only {len(working_providers)} provider(s) working, skipping multi-search test")
    
    print(f"\n{'='*60}")
    print("📊 SEARCH MANAGER SUMMARY")
    print(f"{'='*60}")
    print(f"Available providers: {search_manager.get_available_providers()}")
    print(f"Working providers: {working_providers}")
    print("Search manager ready for production use!")
    print(f"{'='*60}")
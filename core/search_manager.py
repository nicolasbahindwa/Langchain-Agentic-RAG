# core/search_manager.py
from .config import config
from langchain_tavily import TavilySearch
from langchain_community.document_loaders import WikipediaLoader

class SearchManager:
    def __init__(self):
        self.tavily_api_key = config.api_keys.tavily_api_key

    def get_web_search(self, max_results=3):
        """Returns a configured Tavily search tool"""
        # Updated TavilySearch initialization
        return TavilySearch(
            max_results=max_results,
            api_key=self.tavily_api_key
        )

    def get_wikipedia_loader(self, query: str, load_max_docs=2):
        """Returns a configured Wikipedia loader"""
        return WikipediaLoader(
            query=query,
            load_max_docs=load_max_docs
        )
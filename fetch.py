"""Web scraping and search tools."""

import logging
import asyncio

from typing import List, Dict, Any, Literal

from bs4 import BeautifulSoup, SoupStrainer
from langchain_tavily import TavilySearch
from langchain_community.document_loaders import (
    PlaywrightURLLoader,
    SeleniumURLLoader,
    WebBaseLoader,
)
from langchain_community.document_loaders.recursive_url_loader import (
    RecursiveUrlLoader,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
from langchain_community.utilities.duckduckgo_search import (
    DuckDuckGoSearchAPIWrapper,
)


async def _load_docs_async(loader, text_extractor):
    """Helper function to load documents asynchronously with proper error handling."""
    docs = []
    async for doc in loader.alazy_load():
        if (
            doc
            and hasattr(doc, "page_content")
            and doc.page_content.strip()
        ):
            # Apply additional text cleaning
            cleaned_content = text_extractor(doc.page_content)
            if cleaned_content:
                doc.page_content = cleaned_content
                docs.append(doc)
    return docs


async def fetch(
    url_paths: List[str],
    user_agent: str,
    recursive: bool = False,
    depth: int = 4,
    load_js: bool = True,
    use_playwright: bool = True,
    use_selenium: bool = False,
) -> List:
    """
    Load and extract clean text content from URLs.
    Removes all unnecessary elements and focuses on readable text.
    """

    def _clean_text_extractor(html: str) -> str:
        """Extract only clean text content from HTML"""
        soup = BeautifulSoup(html, "html.parser")

        # Remove all unwanted elements
        for element in soup(
            [
                "script",
                "style",
                "noscript",
                "meta",
                "link",
                "img",
                "svg",
                "video",
                "audio",
                "canvas",
                "iframe",
                "embed",
                "object",
                "nav",
                "header",
                "footer",
                "aside",
                "menu",
                "button",
                "input",
                "select",
                "textarea",
                "form",
                "label",
                "ad",
                "advertisement",
                "banner",
                "popup",
                "modal",
            ]
        ):
            element.decompose()

        # Remove elements with common ad/navigation classes
        for element in soup.find_all(attrs={"class": True}):
            classes = " ".join(element.get("class", [])).lower()
            if any(
                word in classes
                for word in [
                    "ad",
                    "advertisement",
                    "banner",
                    "sidebar",
                    "widget",
                    "social",
                    "share",
                    "follow",
                    "subscribe",
                    "newsletter",
                    "comment",
                    "review",
                    "navigation",
                    "menu",
                    "breadcrumb",
                ]
            ):
                element.decompose()

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up the text
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            # Keep only meaningful lines
            if (
                len(line) > 15  # Minimum length
                and not line.lower().startswith(
                    ("click", "menu", "navigation", "skip to")
                )
                and line.count(" ") > 2
            ):  # Must have multiple words
                lines.append(line)

        return "\n\n".join(lines)

    try:
        if recursive:
            loader = RecursiveUrlLoader(
                url=url_paths[0],
                max_depth=depth,
                use_async=True,
                extractor=_clean_text_extractor,
                headers={"User-Agent": user_agent},
            )
            return await loader.aload()

        if load_js:
            if use_playwright:
                loader = PlaywrightURLLoader(
                    urls=url_paths,
                    remove_selectors=[
                        "script",
                        "style",
                        "noscript",
                        "img",
                        "svg",
                        "video",
                        "audio",
                        "iframe",
                        "nav",
                        "header",
                        "footer",
                        "aside",
                        "button",
                        "input",
                        "form",
                        "[class*='ad']",
                        "[class*='banner']",
                    ],
                    continue_on_failure=True,
                    headless=True,
                )
            elif use_selenium:
                loader = SeleniumURLLoader(
                    urls=url_paths,
                    headless=True,
                    arguments=[f'user-agent={user_agent}']
                )
            else:
                loader = PlaywrightURLLoader(
                    urls=url_paths,
                    remove_selectors=[
                        "script",
                        "style",
                        "img",
                        "nav",
                        "footer",
                    ],
                    continue_on_failure=True,
                    browser_kwargs={"user_agent": user_agent},
                )
        else:
            loader = WebBaseLoader(
                web_paths=url_paths,
                requests_kwargs={
                    "headers": {"User-Agent": user_agent},
                    "timeout": 30,
                },
                bs_kwargs={"parse_only": SoupStrainer()},
                bs_get_text_kwargs={"separator": " ", "strip": True},
            )

        # Load and filter content with timeout
        docs = []
        try:
            # Add timeout for async loading to prevent hanging
            if hasattr(loader, "alazy_load"):
                docs = await asyncio.wait_for(
                    _load_docs_async(loader, _clean_text_extractor), 
                    timeout=30.0  # 30 second timeout
                )
            else:
                # Add timeout for synchronous loading too
                docs = await asyncio.wait_for(
                    asyncio.to_thread(loader.load),
                    timeout=30.0  # 30 second timeout
                )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout with {loader.__class__.__name__}, falling back to WebBaseLoader")
            # Fallback to simple WebBaseLoader
            try:
                fallback_loader = WebBaseLoader(
                    web_paths=url_paths,
                    requests_kwargs={
                        "headers": {"User-Agent": user_agent},
                        "timeout": 15,
                    },
                )
                docs = await asyncio.wait_for(
                    asyncio.to_thread(fallback_loader.load),
                    timeout=15.0
                )
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                return [{"error": "Timeout loading URLs, fallback failed", "urls": url_paths}]
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")
            # Also try fallback for other errors
            try:
                fallback_loader = WebBaseLoader(
                    web_paths=url_paths,
                    requests_kwargs={
                        "headers": {"User-Agent": user_agent},
                        "timeout": 15,
                    },
                )
                docs = await asyncio.wait_for(
                    asyncio.to_thread(fallback_loader.load),
                    timeout=15.0
                )
                logger.info(f"Fallback WebBaseLoader succeeded after {loader.__class__.__name__} failed")
            except Exception as fallback_error:
                logger.error(f"Both primary and fallback loaders failed: {e}, {fallback_error}")
                return [{"error": f"Failed to load URLs: {str(e)}", "urls": url_paths}]

        # Clean all documents
        cleaned_docs = []
        for doc in docs:
            if (
                doc
                and hasattr(doc, "page_content")
                and doc.page_content.strip()
            ):
                if (
                    not load_js
                ):  # Only apply extractor if not using JS loaders
                    cleaned_content = _clean_text_extractor(doc.page_content)
                    if cleaned_content:
                        doc.page_content = cleaned_content
                        cleaned_docs.append(doc)
                else:
                    cleaned_docs.append(doc)

        return cleaned_docs

    except Exception as e:
        logger.error(f"Error in fetch: {e}")
        return [{"error": f"Failed to load URLs: {str(e)}"}]


async def search(
    query: str,
    max_results: int,
    provider: Literal["tavily", "duckduckgo"] = "tavily",
) -> Dict[str, Any]:
    """
    Web search tool for LangGraph integration.

    Args:
        query (str): The search query string
        max_results (int): Maximum number of results to return
        provider (str): Search provider: 'tavily', 'duckduckgo'

    Returns:
        List[Dict[str, Any]]: Search results with title, url, snippet, provider
    """
    if not query.strip():
        return {}

    if provider == "tavily":
        tool = TavilySearch(max_results=max_results)
        results = await tool.ainvoke(query)
        return {"provider": "tavily", "results": results}

    elif provider == "duckduckgo":
        tool = DuckDuckGoSearchAPIWrapper(max_results=max_results)
        results = await asyncio.to_thread(tool.run, query)
        return {"provider": "duckduckgo", "results": results}


    return {}


async def main():
    urls = [
        "https://www.almanac.com/plant/tomatoes",
        
    ]
    user_agent = "Mozilla/5.0 (compatible; MyBot/1.0; +http://mybot.com/bot)"
    
    # Call fetch with your URLs, user agent, and optional parameters
    documents = await fetch(
        url_paths=urls,
        user_agent=user_agent,
        recursive=False,  # set True if you want recursive crawling
        depth=2,          # max depth for recursive crawling
        load_js=True,     # whether to use JS-enabled loaders like Playwright
        use_playwright=True,
        use_selenium=False
    )
    
    for i, doc in enumerate(documents):
        print(f"Document {i + 1} content snippet:")
        print(doc.page_content[:500])  
        print("-" * 80)

# Run the async main function
asyncio.run(main())
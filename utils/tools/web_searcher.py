import json
import logging
from typing import List, Dict, Any
from urllib.parse import quote_plus

import feedparser
from langchain.tools import tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FreeWebSearcher:
    """
    Free, reliable web search using RSS feeds.
    Works without scraping or paid APIs.
    """

    def _encode(self, query: str) -> str:
        return quote_plus(query)

    def search_bing_news(self, query: str, max_results: int) -> List[Dict[str, str]]:
        logger.info("Searching Bing News RSS")
        q = self._encode(query)
        url = f"https://www.bing.com/news/search?q={q}&format=rss"

        feed = feedparser.parse(url)
        results = []

        for entry in feed.entries[:max_results]:
            results.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "description": entry.get("summary", ""),
                "source": "Bing News",
            })

        return results

    def search_google_news(self, query: str, max_results: int) -> List[Dict[str, str]]:
        logger.info("Searching Google News RSS")
        q = self._encode(query)
        url = (
            "https://news.google.com/rss/search"
            f"?q={q}&hl=en-US&gl=US&ceid=US:en"
        )

        feed = feedparser.parse(url)
        results = []

        for entry in feed.entries[:max_results]:
            results.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "description": entry.get("summary", ""),
                "source": "Google News",
            })

        return results

    def search_reddit(self, query: str, max_results: int) -> List[Dict[str, str]]:
        logger.info("Searching Reddit RSS")
        q = self._encode(query)
        url = f"https://www.reddit.com/search.rss?q={q}"

        feed = feedparser.parse(url)
        results = []

        for entry in feed.entries[:max_results]:
            results.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "description": entry.get("summary", ""),
                "source": "Reddit",
            })

        return results

    def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        logger.info(f"Starting RSS-based search: {query}")

        for method in (
            self.search_bing_news,
            self.search_google_news,
            self.search_reddit,
        ):
            try:
                results = method(query, max_results)
                if results:
                    return {
                        "success": True,
                        "query": query,
                        "count": len(results),
                        "results": results,
                    }
            except Exception as e:
                logger.warning(f"Search source failed: {e}")

        return {
            "success": False,
            "query": query,
            "results": [],
            "message": "No results found from RSS sources.",
        }


# ---------------------------------------------------------------------
# LangChain Tool
# ---------------------------------------------------------------------
@tool(
    "web_search",
    parse_docstring=True,
    description="Free web search using Bing News, Google News, and Reddit RSS."
)
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web and return results as JSON.

    Args:
        query: Search query string.
        max_results: Maximum number of results.
    """
    searcher = FreeWebSearcher()
    result = searcher.search(query, max_results)
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------
# Local test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    print(web_search.invoke({"query": "latest innovations in drums 2024", "max_results": 5}))

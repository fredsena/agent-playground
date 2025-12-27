import requests
from bs4 import BeautifulSoup
import time
import random
import json
from typing import List, Dict, Any
from langchain.tools import tool

from langchain.tools import tool, ToolRuntime
from typing import List, Dict, Any


headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }


def _clean_text(text: str) -> str:
    """Cleans up whitespace and newlines from scraped text."""
    if not text:
        return ""
    return " ".join(text.split())

def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches DuckDuckGo using the 'lite' version (no JavaScript required).
    """
    url = "https://lite.duckduckgo.com/lite/"
    # DuckDuckGo Lite uses a POST request for the search query
    payload = {"q": query}
    
    try:
        # Small delay to be respectful
        time.sleep(random.uniform(0.5, 1.5))
        response = requests.post(url, data=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # DuckDuckGo Lite results are structured in tables.
        # The first few tables are headers/ads. The results table is usually the 3rd or 4th.
        tables = soup.find_all("table")
        if len(tables) < 3:
            return []

        # We look for the table containing the results
        result_table = None
        for table in tables:
            if table.find("a", class_="result-link"):
                result_table = table
                break
        
        if not result_table:
            return []

        rows = result_table.find_all("tr")
        
        # DuckDuckGo Lite result structure:
        # Row N: Title and Link
        # Row N+1: Snippet/Description
        # Row N+2: Metadata (URL, etc.)
        # Row N+3: Spacer
        for i in range(0, len(rows) - 1, 4):
            if len(results) >= max_results:
                break
                
            title_row = rows[i]
            snippet_row = rows[i+1] if i+1 < len(rows) else None
            
            link_tag = title_row.find("a", class_="result-link")
            if link_tag:
                title = _clean_text(link_tag.get_text())
                href = link_tag["href"]
                
                # Handle internal DDG redirects if necessary
                if href.startswith("//"):
                    href = "https:" + href
                
                snippet = ""
                if snippet_row:
                    snippet = _clean_text(snippet_row.get_text())
                
                # Skip obvious ad results if they don't have a snippet or look like ads
                if not snippet and "ad_provider" in href:
                    continue

                results.append({
                    "title": title,
                    "url": href,
                    "description": snippet,
                    "source": "DuckDuckGo"
                })
        
        return results
    except Exception as e:
        # In a production tool, you might want to log this
        return []

def search_google(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Fallback search using Google. Note: Highly susceptible to rate limiting.
    """
    url = "https://www.google.com/search"
    params = {"q": query, "hl": "en"}
    
    try:
        time.sleep(random.uniform(1.0, 2.0))
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 429:
            return [] # Rate limited
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # Google's CSS classes change frequently, but 'g' is a common container for results
        for g in soup.find_all("div", class_="g"):
            if len(results) >= max_results:
                break
                
            title_tag = g.find("h3")
            link_tag = g.find("a")
            
            # Snippet classes are very volatile, we try a few common ones
            snippet_tag = g.find("div", {"style": "-webkit-line-clamp:2"}) or \
                            g.find("div", class_="VwiC3b") or \
                            g.find("span", class_="aCOpRe")
            
            if title_tag and link_tag:
                url = link_tag["href"]
                if url.startswith("/url?q="):
                    url = url.split("/url?q=")[1].split("&")[0]
                
                results.append({
                    "title": _clean_text(title_tag.get_text()),
                    "url": url,
                    "description": _clean_text(snippet_tag.get_text()) if snippet_tag else "",
                    "source": "Google"
                })
        
        return results
    except Exception:
        return []


@tool(
    "get_web_links",
    parse_docstring=True,
    description=("get web links using DuckDuckGo and Google.")
)
def get_web_links(query: str, max_results: int = 5) -> str:
    """Search the web for the given query and return web links as a JSON string.
    
    Args:
        query: The search query string.
        max_results: Maximum number of results to return. Defaults to 5.

    """
    # searcher = FreeWebSearcher()
    # results = searcher.search(query, max_results=max_results)

    """
    The primary method to perform a web search.
    Tries DuckDuckGo first, then Google as a fallback.
    """
    # 1. Try DuckDuckGo Lite (most reliable for scraping)
    results = search_duckduckgo(query, max_results)
    
    # 2. If no results, try Google
    if not results:
        results = search_google(query, max_results)
        
    return json.dumps(results, indent=2)

if __name__ == "__main__":
    # Quick test    
    search_results = get_web_links.invoke({"query": "Latests advancements in Drums", "max_results": 10})
    print(search_results)

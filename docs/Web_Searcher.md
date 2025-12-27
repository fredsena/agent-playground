# Free Python Web Searcher

A lightweight, reliable, and free web search tool implemented in Python. This tool is designed to be used as a function calling mechanism for AI agents or as a standalone utility for programmatic web searching without the need for expensive API subscriptions.

## Features

- **No API Keys Required**: Works out of the box without any paid subscriptions.
- **Dual-Source Reliability**: Uses DuckDuckGo Lite as the primary source and Google as a fallback.
- **Scraper-Friendly**: Specifically targets non-JavaScript endpoints (like DDG Lite) to ensure high reliability and speed.
- **Clean Output**: Returns structured JSON data including titles, URLs, and snippets.
- **Respectful Scraping**: Includes randomized delays and realistic headers to minimize the risk of being blocked.

## Requirements

- Python 3.7+
- `requests`
- `beautifulsoup4`

## Installation

```bash
pip install requests beautifulsoup4
```

## Usage

### As a Python Class

```python
from free_web_searcher import FreeWebSearcher

searcher = FreeWebSearcher()
results = searcher.search("Python programming", max_results=5)

for res in results:
    print(f"Title: {res['title']}")
    print(f"URL: {res['url']}")
    print(f"Snippet: {res['description']}\n")
```

### As a Function (Ideal for Function Calling)

```python
import json
from free_web_searcher import web_search

# Returns a JSON string of results
json_results = web_search("Latest AI news", max_results=3)
print(json_results)
```

## How it Works

1. **DuckDuckGo Lite**: The tool first attempts to scrape `lite.duckduckgo.com`. This version of DuckDuckGo is designed for low-bandwidth and non-JS environments, making it extremely stable for programmatic access.
2. **Google Fallback**: If DuckDuckGo fails to return results, the tool falls back to a basic Google search.
3. **Data Parsing**: It uses `BeautifulSoup` to extract the relevant information from the HTML response and packages it into a clean list of dictionaries.

## Disclaimer

This tool is for educational and personal use. Please respect the Terms of Service of the search engines and do not use it for high-volume automated scraping that could disrupt their services.

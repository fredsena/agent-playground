# Free Python Web Data Retriever

A powerful, free, and reliable web page content extractor implemented in Python. This tool is designed to extract the "useful" part of a web page (main text, metadata, etc.) while stripping away noise like ads, navigation bars, and footers.

## Features

- **High-Quality Extraction**: Uses the `Trafilatura` library, which consistently outperforms other open-source tools in extracting main content.
- **Metadata Support**: Automatically extracts titles, authors, dates, and site names.
- **Multiple Formats**: Supports output in Markdown, Plain Text, XML, and JSON.
- **Smart Fallback**: If the main content extraction fails, it falls back to a full-text extraction to ensure you always get data.
- **No Subscriptions**: Completely free and open-source.

## Requirements

- Python 3.7+
- `trafilatura`
- `lxml_html_clean` (required for modern trafilatura versions)

## Installation

```bash
pip install trafilatura lxml_html_clean
```

## Usage

### As a Python Class

```python
from free_web_retriever import FreeWebRetriever

retriever = FreeWebRetriever()
result = retriever.retrieve("https://example.com/article")

if result["status"] == "success":
    print(f"Title: {result['metadata']['title']}")
    print(f"Content: {result['content']}")
```

### As a Function (Ideal for Function Calling)

```python
import json
from free_web_retriever import get_web_data

# Returns a JSON string with metadata and content
json_data = get_web_data("https://example.com/article", output_format="markdown")
print(json_data)
```

## How it Works

1. **Download**: The tool fetches the HTML content of the URL using `trafilatura.fetch_url`.
2. **Metadata Extraction**: It extracts structured metadata (title, author, etc.) using specialized algorithms.
3. **Content Extraction**: It uses a "readability" style algorithm to identify the main body of the text, discarding non-essential elements.
4. **Formatting**: The extracted content is converted into the requested format (defaulting to Markdown for best readability).

## Disclaimer

This tool is for educational and personal use. Please respect the `robots.txt` and Terms of Service of the websites you are retrieving data from.

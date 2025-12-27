import trafilatura
import json
import time
import random
from typing import Dict, Any, Optional

class FreeWebRetriever:
    """
    A reliable, free web page data retriever implemented in Python.
    Designed for use as a function calling tool for AI agents.
    Uses Trafilatura for high-quality main content and metadata extraction.
    """

    def __init__(self, user_agent: Optional[str] = None):
        # Realistic user agent to avoid being blocked
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def retrieve(self, url: str, output_format: str = "markdown", include_comments: bool = False) -> Dict[str, Any]:
        """
        Retrieves the main content and metadata from a given URL.
        
        Args:
            url: The URL of the web page to retrieve.
            output_format: The format of the extracted content ('markdown', 'txt', 'xml', 'json').
            include_comments: Whether to include comments in the extraction.
            
        Returns:
            A dictionary containing metadata and the extracted content.
        """
        try:
            # Respectful delay
            time.sleep(random.uniform(0.5, 1.5))
            
            # Download the page
            # Note: In newer versions of trafilatura, fetch_url might not take user_agent directly
            # or it might be handled differently. Let's use the default or check docs.
            # Actually, trafilatura uses its own internal management for headers.
            downloaded = trafilatura.fetch_url(url)
            
            if downloaded is None:
                return {
                    "status": "error",
                    "message": f"Failed to download content from {url}. The site might be blocking automated access or is currently down.",
                    "url": url
                }

            # Extract metadata
            metadata_obj = trafilatura.extract_metadata(downloaded)
            metadata = {}
            if metadata_obj:
                metadata = {
                    "title": metadata_obj.title,
                    "author": metadata_obj.author,
                    "date": metadata_obj.date,
                    "description": metadata_obj.description,
                    "sitename": metadata_obj.sitename,
                    "language": metadata_obj.language
                }

            # Extract main content
            content = trafilatura.extract(
                downloaded, 
                output_format=output_format, 
                include_comments=include_comments,
                with_metadata=False # We already have metadata separately
            )

            if not content:
                # Fallback: try to get all text if main content extraction fails
                content = trafilatura.html2txt(downloaded)
                source_type = "full_text_fallback"
            else:
                source_type = "main_content"

            return {
                "status": "success",
                "url": url,
                "metadata": metadata,
                "content": content,
                "extraction_method": source_type
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "url": url
            }

# Example usage for function calling
def get_web_data(url: str, output_format: str = "markdown") -> str:
    """
    Retrieve useful data from a web page and return it as a JSON string.
    """
    retriever = FreeWebRetriever()
    data = retriever.retrieve(url, output_format=output_format)
    return json.dumps(data, indent=2)

if __name__ == "__main__":
    # Quick test
    test_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    print(f"Retrieving data from: {test_url}...")
    result = get_web_data(test_url)
    
    # Print a summary of the result
    data = json.loads(result)
    if data["status"] == "success":
        print(f"Successfully retrieved: {data['metadata'].get('title', 'No Title')}")
        print(f"Content length: {len(data['content'])} characters")
        print("\nSnippet:")
        print(data["content"][:300] + "...")
    else:
        print(f"Error: {data['message']}")

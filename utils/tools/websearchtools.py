#from typing_extensions import runtime
import httpx
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import lru_cache
from langchain.tools import tool, ToolRuntime
from pydantic import BaseModel, Field
from rich.console import Console

from utils.console import console


# ============================================================================
# DATA MODELS & ENUMS
# ============================================================================

class SearchSourceType(str, Enum):
    """Source type identifier."""
    WIKIPEDIA = "wikipedia"
    DUCKDUCKGO = "duckduckgo"
    HYBRID = "hybrid"

class ResultRelevanceLevel(str, Enum):
    """Relevance scoring levels."""
    EXACT = "exact"        # Direct match to query
    HIGH = "high"          # Very relevant
    MEDIUM = "medium"      # Relevant
    LOW = "low"           # Tangentially relevant

@dataclass
class SearchResult:
    """Unified search result structure."""
    title: str
    url: str
    snippet: str
    source: SearchSourceType
    relevance_score: float  # 0.0 to 1.0
    relevance_level: ResultRelevanceLevel
    timestamp: datetime
    domain: str = ""
    result_type: str = "article"  # 'article', 'instant_answer', 'definition'
    
    def __post_init__(self):
        """Extract domain from URL."""
        if self.url:
            self.domain = self.url.split('/')[2] if '//' in self.url else "unknown"

class HybridSearchInput(BaseModel):
    """Advanced input schema for hybrid search."""
    query: str = Field(
        description="Search query (2+ chars). Use natural language or keywords."
    )
    search_mode: Literal["hybrid", "wikipedia_first", "web_first", "wikipedia_only", "web_only"] = Field(
        default="hybrid",
        description="Search strategy: 'hybrid' blends both sources, 'wikipedia_first' prioritizes facts, 'web_first' for current info"
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Total results to return (1-15). Automatically balanced between sources."
    )
    summary_length: Literal["brief", "normal", "detailed"] = Field(
        default="normal",
        description="Result summary length: 'brief'=1 sentence, 'normal'=2-3 sentences, 'detailed'=4-5 sentences"
    )
    include_sources: bool = Field(
        default=True,
        description="Include source information and URLs in results"
    )
    recency_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for recent results (0=ignore date, 1=heavily prioritize recent). For trending topics, increase this."
    )
    timeout_seconds: int = Field(
        default=10,
        ge=5,
        le=30,
        description="API timeout in seconds"
    )
    allow_cache: bool = Field(
        default=True,
        description="Use cached results if available (within 1 hour)"
    )

# ============================================================================
# HYBRID SEARCH TOOL
# ============================================================================

@tool(
    "web_hybrid_search",
    parse_docstring=True,
    description=(
        "Advanced web hybrid search combining Wikipedia (trusted facts) and DuckDuckGo (current info). "
        "Intelligently blends sources based on query type. Supports multiple search modes, "
        "relevance ranking, result caching, and real-time progress streaming. "
        "Perfect for research, fact-checking, and finding latest information."
    ),
)
def web_hybrid_search(
    query: str,
    search_mode: str = "hybrid",
    max_results: int = 5,
    summary_length: str = "normal",
    include_sources: bool = True,
    recency_weight: float = 0.3,
    timeout_seconds: int = 10,
    allow_cache: bool = True,
    #runtime: Optional[ToolRuntime] = None,
) -> str:
    """Advanced hybrid search combining Wikipedia and DuckDuckGo.

    This tool intelligently searches both Wikipedia (for verified, factual information)
    and DuckDuckGo (for current, trending information), then ranks and deduplicates
    results for maximum relevance.

    Args:
        query (str): Search query (minimum 2 characters). Use natural language.
        search_mode (str): One of 'hybrid' (blend both sources, recommended), 
            'wikipedia_first' (prioritize Wikipedia for facts/history/science), 
            'web_first' (prioritize DuckDuckGo for current events/products), 
            'wikipedia_only' (only search Wikipedia), or 
            'web_only' (only search DuckDuckGo).
        max_results (int): Total results to return (1-15, default: 5).
        summary_length (str): 'brief' (1 sent), 'normal' (2-3), 'detailed' (4-5).
        include_sources (bool): Include source information and URLs (default: True).
        recency_weight (float): Weight for recent results (0-1, default: 0.3).
            Use 0.7+ for trending/current topics, 0.0 for timeless queries.
        timeout_seconds (int): API timeout (5-30 seconds, default: 10).
        allow_cache (bool): Use cached results if available (default: True).        

    Returns:
        str: Formatted search results with rankings, relevance scores, and sources.

    Raises:
        ValueError: If query is invalid or both sources fail.

    Example:
        >>> result = hybrid_search(
        ...     query="quantum computing breakthroughs 2024",
        ...     search_mode="web_first",
        ...     max_results=10,
        ...     summary_length="detailed",
        ...     recency_weight=0.8
        ... )
    """
    
    # Input validation
    _validate_input(query, max_results, timeout_seconds, recency_weight)
    
    query_clean = query.strip()
    
    # Check cache first
    if allow_cache:
        cached = _get_cached_results(query_clean, search_mode)
        if cached:
            console.print(f"✅ Using cached results for: '[cyan]{query_clean}[/cyan]'", style="success")
            return cached
    
    # Stream progress if runtime available
    #writer = runtime.stream_writer if runtime else None
    writer =  None
    
    _stream("🔍 Web hybrid search starting...", writer)
    _stream(f"   Query: '{query_clean}'", writer)
    _stream(f"   Mode: {search_mode} | Max results: {max_results}", writer)
    
    console.print(
        f"🔍 Web hybrid search: '[cyan]{query_clean}[/cyan]' | Mode: {search_mode}",
        style="info"
    )
    
    try:
        all_results = []
        
        # Determine search strategy
        search_wikipedia = search_mode in ["hybrid", "wikipedia_first", "wikipedia_only"]
        search_web = search_mode in ["hybrid", "web_first", "web_only"]
        
        # Execute searches based on mode
        if search_wikipedia:
            _stream(f"   📖 Searching Wikipedia...", writer)
            wiki_results = _search_wikipedia(query_clean, timeout_seconds)
            all_results.extend(wiki_results)
            _stream(f"      Found {len(wiki_results)} Wikipedia articles", writer)
        
        if search_web:
            _stream(f"   🌐 Searching DuckDuckGo...", writer)
            web_results = _search_duckduckgo(query_clean, timeout_seconds)
            all_results.extend(web_results)
            _stream(f"      Found {len(web_results)} web results", writer)
        
        if not all_results:
            return f"❌ No results found for: '{query_clean}'\n\nTry:\n  - Simplifying your query\n  - Using different keywords\n  - Checking spelling"
        
        # Rank and filter results
        _stream(f"   ⭐ Ranking {len(all_results)} results by relevance...", writer)
        ranked_results = _rank_results(
            all_results,
            query_clean,
            search_mode,
            recency_weight
        )
        
        # Deduplicate similar results
        deduped = _deduplicate_results(ranked_results)
        _stream(f"      Deduped to {len(deduped)} unique results", writer)
        
        # Limit to max_results
        final_results = deduped[:max_results]
        
        # Format output
        _stream(f"   📝 Formatting output...", writer)
        formatted = _format_results(
            final_results,
            query_clean,
            summary_length,
            include_sources
        )
        
        # Cache results
        if allow_cache:
            _cache_results(query_clean, search_mode, formatted)
        
        _stream(f"✅ Search complete! Found {len(final_results)} results", writer)
        console.print(f"✅ Search complete! {len(final_results)} results", style="success")
        
        return formatted
        
    except httpx.TimeoutException:
        raise ValueError(f"Search timed out after {timeout_seconds}s. Try a shorter query or increase timeout.")
    except httpx.RequestError as e:
        raise ValueError(f"Network error during search: {str(e)}")
    except Exception as e:
        raise ValueError(f"Search failed: {str(e)}")


# ============================================================================
# WIKIPEDIA SEARCH
# ============================================================================

def _search_wikipedia(query: str, timeout_seconds: int) -> list[SearchResult]:
    """Search Wikipedia with advanced filtering."""
    
    search_url = "https://en.wikipedia.org/w/api.php"
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srwhat": "text",
        "srlimit": 10,  # Get more to rank better
        "format": "json",
    }
    
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(search_url, params=search_params)
            response.raise_for_status()
            search_data = response.json()
    except Exception as e:
        console.print(f"⚠️  Wikipedia search failed: {str(e)}", style="warning")
        return []
    
    search_results = search_data.get("query", {}).get("search", [])
    if not search_results:
        return []
    
    page_titles = [r["title"] for r in search_results[:10]]
    
    # Get full content
    content_url = "https://en.wikipedia.org/w/api.php"
    content_params = {
        "action": "query",
        "titles": "|".join(page_titles),
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "format": "json",
    }
    
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(content_url, params=content_params)
            response.raise_for_status()
            content_data = response.json()
    except Exception as e:
        console.print(f"⚠️  Wikipedia content fetch failed: {str(e)}", style="warning")
        return []
    
    results = []
    pages = content_data.get("query", {}).get("pages", {})
    
    for page_id, page_data in pages.items():
        if "missing" in page_data:
            continue
        
        title = page_data.get("title", "")
        extract = page_data.get("extract", "")
        
        if not extract:
            continue
        
        # Truncate to first 200 chars for snippet
        snippet = extract[:200] + "..." if len(extract) > 200 else extract
        
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        
        results.append(SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            source=SearchSourceType.WIKIPEDIA,
            relevance_score=0.85,  # Will be adjusted by ranker
            relevance_level=ResultRelevanceLevel.HIGH,
            timestamp=datetime.now(),
            result_type="article"
        ))
    
    return results


# ============================================================================
# DUCKDUCKGO SEARCH
# ============================================================================

def _search_duckduckgo(query: str, timeout_seconds: int) -> list[SearchResult]:
    """Search DuckDuckGo with instant answers and web results."""
    
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "t": "langchain",
        "no_redirect": 1,
    }
    
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        console.print(f"⚠️  DuckDuckGo search failed: {str(e)}", style="warning")
        return []
    
    results = []
    
    # Instant answer (highest priority)
    if data.get("AbstractText") and data.get("AbstractURL"):
        results.append(SearchResult(
            title=data.get("Heading", "Instant Answer"),
            url=data.get("AbstractURL", ""),
            snippet=data.get("AbstractText", "")[:200],
            source=SearchSourceType.DUCKDUCKGO,
            relevance_score=0.95,
            relevance_level=ResultRelevanceLevel.EXACT,
            timestamp=datetime.now(),
            result_type="instant_answer"
        ))
    
    # Related topics (web results)
    for topic in data.get("RelatedTopics", [])[:15]:
        if "FirstURL" not in topic:
            continue
        
        results.append(SearchResult(
            title=topic.get("Text", "").split(" - ")[0][:80],
            url=topic.get("FirstURL", ""),
            snippet=topic.get("Text", "")[:200],
            source=SearchSourceType.DUCKDUCKGO,
            relevance_score=0.75,
            relevance_level=ResultRelevanceLevel.MEDIUM,
            timestamp=datetime.now(),
            result_type="article"
        ))
    
    return results


# ============================================================================
# RANKING & DEDUPLICATION
# ============================================================================

def _rank_results(
    results: list[SearchResult],
    query: str,
    search_mode: str,
    recency_weight: float
) -> list[SearchResult]:
    """Rank results by relevance, freshness, and source."""
    
    query_terms = set(query.lower().split())
    
    for result in results:
        score = 0.0
        title_lower = result.title.lower()
        snippet_lower = result.snippet.lower()
        
        # Exact match bonus
        if query.lower() in title_lower:
            score += 0.3
        
        # Term coverage in title
        title_matches = sum(1 for term in query_terms if term in title_lower)
        score += min(0.25, title_matches * 0.08)
        
        # Term coverage in snippet
        snippet_matches = sum(1 for term in query_terms if term in snippet_lower)
        score += min(0.2, snippet_matches * 0.05)
        
        # Source weighting
        if search_mode == "wikipedia_first":
            score += 0.2 if result.source == SearchSourceType.WIKIPEDIA else 0.0
        elif search_mode == "web_first":
            score += 0.2 if result.source == SearchSourceType.DUCKDUCKGO else 0.0
        
        # Recency weighting
        age_hours = (datetime.now() - result.timestamp).total_seconds() / 3600
        recency_score = max(0, 1.0 - (age_hours / 168))  # 7 days = 0
        score += recency_score * recency_weight * 0.15
        
        # Result type bonus
        if result.result_type == "instant_answer":
            score += 0.15
        
        # Cap at 1.0
        result.relevance_score = min(1.0, score + 0.1)  # Base confidence
        
        # Classify relevance level
        if result.relevance_score >= 0.9:
            result.relevance_level = ResultRelevanceLevel.EXACT
        elif result.relevance_score >= 0.7:
            result.relevance_level = ResultRelevanceLevel.HIGH
        elif result.relevance_score >= 0.5:
            result.relevance_level = ResultRelevanceLevel.MEDIUM
        else:
            result.relevance_level = ResultRelevanceLevel.LOW
    
    # Sort by relevance score
    return sorted(results, key=lambda r: r.relevance_score, reverse=True)


def _deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove duplicate/similar results."""
    
    seen_titles = set()
    deduped = []
    
    for result in results:
        # Simple dedup by title similarity
        title_hash = hashlib.md5(result.title.lower().split()[0].encode()).hexdigest()[:8]
        
        if title_hash not in seen_titles:
            seen_titles.add(title_hash)
            deduped.append(result)
    
    return deduped


# ============================================================================
# FORMATTING & OUTPUT
# ============================================================================

def _format_results(
    results: list[SearchResult],
    query: str,
    summary_length: str,
    include_sources: bool
) -> str:
    """Format results with advanced styling."""
    
    # Determine snippet length
    summary_chars = {
        "brief": 100,
        "normal": 180,
        "detailed": 300
    }.get(summary_length, 180)
    
    output = f"\n{'='*80}\n"
    output += f"🔍 HYBRID SEARCH RESULTS: '{query}'\n"
    output += f"{'='*80}\n\n"
    
    for idx, result in enumerate(results, 1):
        # Relevance indicator
        relevance_emoji = {
            ResultRelevanceLevel.EXACT: "🎯",
            ResultRelevanceLevel.HIGH: "⭐",
            ResultRelevanceLevel.MEDIUM: "👍",
            ResultRelevanceLevel.LOW: "📌"
        }[result.relevance_level]
        
        score_bar = "█" * int(result.relevance_score * 10) + "░" * (10 - int(result.relevance_score * 10))
        
        output += f"{idx}. {relevance_emoji} {result.title}\n"
        output += f"   [{score_bar}] {result.relevance_score:.0%} • {result.source.value.upper()}\n"
        
        # Snippet
        snippet = result.snippet[:summary_chars]
        if len(result.snippet) > summary_chars:
            snippet += "..."
        output += f"   {snippet}\n"
        
        # Sources
        if include_sources:
            output += f"   🔗 {result.url}\n"
        
        output += "\n"
    
    output += f"{'='*80}\n"
    output += f"💡 Tip: Adjust search_mode for better results (wikipedia_first for facts, web_first for current info)\n"
    
    return output


# ============================================================================
# CACHING
# ============================================================================

_result_cache = {}

def _get_cached_results(query: str, mode: str) -> Optional[str]:
    """Get results from cache if fresh (< 1 hour old)."""
    
    key = f"{query}:{mode}"
    if key in _result_cache:
        timestamp, results = _result_cache[key]
        age_minutes = (datetime.now() - timestamp).total_seconds() / 60
        
        if age_minutes < 60:
            return results
    
    return None

def _cache_results(query: str, mode: str, results: str) -> None:
    """Cache results with timestamp."""
    
    key = f"{query}:{mode}"
    _result_cache[key] = (datetime.now(), results)
    
    # Simple cleanup: remove old entries if cache gets large
    if len(_result_cache) > 100:
        oldest_key = min(_result_cache.keys(), key=lambda k: _result_cache[k][0])
        del _result_cache[oldest_key]


# ============================================================================
# UTILITIES
# ============================================================================

def _validate_input(query: str, max_results: int, timeout: int, recency: float) -> None:
    """Validate all input parameters."""
    
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")
    
    if len(query.strip()) < 2:
        raise ValueError("Query must be at least 2 characters")
    
    if not (1 <= max_results <= 15):
        raise ValueError("max_results must be 1-15")
    
    if not (5 <= timeout <= 30):
        raise ValueError("timeout_seconds must be 5-30")
    
    if not (0.0 <= recency <= 1.0):
        raise ValueError("recency_weight must be 0.0-1.0")


def _stream(message: str, writer: Optional[object]) -> None:
    """Stream progress message if writer available."""
    
    if writer:
        try:
            writer(message)
        except:
            pass  # Silently fail if streaming unavailable


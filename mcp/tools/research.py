from pinecone import Pinecone
from openai import OpenAI
from config import settings


# Native clients — no LangChain. The OpenAI Agents SDK requires openai>=2, which
# is incompatible with langchain-openai/langchain-pinecone, so RAG retrieval uses
# the OpenAI and Pinecone SDKs directly.
_openai = OpenAI(api_key=settings.OPENAI_API_KEY)
_pc = Pinecone(api_key=settings.PINECONE_API_KEY)
_index = _pc.Index(settings.PINECONE_INDEX_NAME)

# Key under which document text is stored in vector metadata. LangChain's
# PineconeVectorStore used "text" by default; we try a few common keys so this
# keeps working regardless of how the index was populated.
_TEXT_KEYS = ("text", "page_content", "content")


def _embed(text: str) -> list[float]:
    """Embed a query string with the configured OpenAI embedding model."""
    response = _openai.embeddings.create(model=settings.EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def _extract_content(metadata) -> tuple[str, dict]:
    """Pull the document text out of vector metadata, returning (content, remaining_metadata)."""
    md = dict(metadata or {})
    for key in _TEXT_KEYS:
        if key in md:
            return (md.pop(key) or ""), md
    return "", md


def search_financial_knowledge(query: str, top_k: int = None) -> dict:
    """
    Searches the Pinecone vector database for relevant financial content.
    This includes crowdsourced articles, financial news, and market analysis.

    Args:
        query: The search query (e.g., "Apple earnings outlook", "tech sector analysis")
        top_k: Number of results to return (default from settings)

    Returns:
        Dictionary containing relevant documents and metadata
    """
    try:
        if top_k is None:
            top_k = settings.RAG_TOP_K

        response = _index.query(
            vector=_embed(query),
            top_k=top_k,
            include_metadata=True,
        )

        # Pinecone QueryResponse exposes `.matches`; fall back to dict access.
        matches = getattr(response, "matches", None)
        if matches is None and isinstance(response, dict):
            matches = response.get("matches", [])
        matches = matches or []

        if not matches:
            return {
                "success": True,
                "data": {
                    "query": query,
                    "results": [],
                    "total_found": 0,
                    "message": "No relevant documents found for this query"
                }
            }

        # Format results
        documents = []
        for match in matches:
            score = getattr(match, "score", None)
            metadata = getattr(match, "metadata", None)
            if score is None and isinstance(match, dict):
                score = match.get("score")
                metadata = match.get("metadata")

            content, remaining = _extract_content(metadata)
            documents.append({
                "content": content,
                "relevance_score": round(float(score), 4) if score is not None else 0.0,
                "metadata": remaining
            })

        return {
            "success": True,
            "data": {
                "query": query,
                "results": documents,
                "total_found": len(documents),
                "top_k": top_k
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }


def search_by_ticker(ticker: str, top_k: int = None) -> dict:
    """
    Searches for financial content related to a specific stock ticker.

    Args:
        ticker: Stock symbol (e.g., "AAPL", "TSLA")
        top_k: Number of results to return

    Returns:
        Dictionary containing relevant documents about the ticker
    """
    # Enhance query with common variations
    query = f"{ticker} stock analysis news earnings"

    return search_financial_knowledge(query, top_k)


def search_market_sentiment(topic: str, top_k: int = None) -> dict:
    """
    Searches for market sentiment and analysis on a specific topic.

    Args:
        topic: Topic to analyze (e.g., "tech sector", "interest rates", "AI stocks")
        top_k: Number of results to return

    Returns:
        Dictionary containing sentiment-related documents
    """
    query = f"{topic} market sentiment analysis outlook"

    return search_financial_knowledge(query, top_k)


def get_context_for_query(query: str, user_symbols: list[str] = None) -> dict:
    """
    Builds comprehensive context for the AI by combining:
    1. Direct query search
    2. User's portfolio-related content (if symbols provided)

    Args:
        query: User's question
        user_symbols: List of stock symbols the user owns

    Returns:
        Combined context from multiple searches
    """
    try:
        results = {
            "query_results": [],
            "portfolio_context": [],
            "total_sources": 0
        }

        # 1. Search for direct query
        direct_search = search_financial_knowledge(query, top_k=3)
        if direct_search["success"] and direct_search["data"]["results"]:
            results["query_results"] = direct_search["data"]["results"]
            results["total_sources"] += len(direct_search["data"]["results"])

        # 2. If user has portfolio, search for their stocks mentioned in query
        if user_symbols:
            # Check if any user symbols are mentioned in the query
            query_lower = query.lower()
            relevant_symbols = [
                s for s in user_symbols
                if s.lower() in query_lower
            ]

            # If specific stocks mentioned, get context for them
            if relevant_symbols:
                for symbol in relevant_symbols[:2]:  # Limit to 2 symbols
                    ticker_search = search_by_ticker(symbol, top_k=2)
                    if ticker_search["success"] and ticker_search["data"]["results"]:
                        results["portfolio_context"].extend(ticker_search["data"]["results"])
                        results["total_sources"] += len(ticker_search["data"]["results"])

        return {
            "success": True,
            "data": results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }


def format_sources_for_response(search_results: list[dict]) -> list[str]:
    """
    Formats search results into source strings for the API response.

    Args:
        search_results: List of search result documents

    Returns:
        List of formatted source strings
    """
    sources = []

    for i, result in enumerate(search_results, 1):
        content = result.get("content", "")
        score = result.get("relevance_score", 0)

        # Truncate content for display
        truncated = content[:200] + "..." if len(content) > 200 else content
        sources.append(f"[Source {i}] (relevance: {score}): {truncated}")

    return sources

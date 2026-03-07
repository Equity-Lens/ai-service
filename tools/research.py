from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from typing import Optional
from config import settings


# Initialize Pinecone client
pc = Pinecone(api_key=settings.PINECONE_API_KEY)

# Initialize embeddings model
embeddings = OpenAIEmbeddings(
    model=settings.EMBEDDING_MODEL,
    openai_api_key=settings.OPENAI_API_KEY
)


def get_vector_store() -> PineconeVectorStore:
    """
    Returns initialized Pinecone vector store.
    """
    return PineconeVectorStore(
        index_name=settings.PINECONE_INDEX_NAME,
        embedding=embeddings
    )


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
        
        vector_store = get_vector_store()
        
        # Perform similarity search
        results = vector_store.similarity_search_with_score(
            query=query,
            k=top_k
        )
        
        if not results:
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
        for doc, score in results:
            documents.append({
                "content": doc.page_content,
                "relevance_score": round(float(score), 4),
                "metadata": doc.metadata if doc.metadata else {}
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
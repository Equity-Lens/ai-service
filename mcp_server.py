from fastmcp import FastMCP
from typing import Optional
import asyncio

from tools.portfolio import (
    get_user_holdings,
    get_user_alerts,
    get_portfolio_summary
)
from tools.market import (
    get_live_market_data,
    get_multiple_quotes,
    get_price_history,
    calculate_portfolio_value
)
from tools.research import (
    search_financial_knowledge,
    search_by_ticker,
    search_market_sentiment,
    get_context_for_query
)
from config import settings


# Initialize FastMCP server
mcp = FastMCP(
    name="MarketAxis Trading Intelligence",
    description="AI-powered tools for portfolio analysis, market data, and financial research"
)

# Portfolio Tools
@mcp.tool()
async def fetch_user_holdings(user_id: int) -> dict:
    """
    Fetches all stock holdings for a user across all their portfolios.
    Use this when the user asks about their portfolio, positions, or holdings.
    
    Args:
        user_id: The authenticated user's ID
        
    Returns:
        User's portfolios with all stock holdings, quantities, and average prices
    """
    return await get_user_holdings(user_id)


@mcp.tool()
async def fetch_user_alerts(user_id: int) -> dict:
    """
    Fetches all price alerts set by a user.
    Use this when the user asks about their alerts or notifications.
    
    Args:
        user_id: The authenticated user's ID
        
    Returns:
        User's price alerts with target prices and status
    """
    return await get_user_alerts(user_id)


@mcp.tool()
async def fetch_portfolio_summary(user_id: int) -> dict:
    """
    Gets a comprehensive summary of user's portfolio and alerts.
    Use this for personalized advice or when user asks about overall portfolio status.
    
    Args:
        user_id: The authenticated user's ID
        
    Returns:
        Summary with symbols owned, total invested, and active alerts
    """
    return await get_portfolio_summary(user_id)

# Market Data Tools
@mcp.tool()
def fetch_stock_price(ticker: str) -> dict:
    """
    Fetches real-time market data for a stock ticker.
    Use this when user asks about current price, P/E ratio, or stock metrics.
    
    Args:
        ticker: Stock symbol (e.g., "AAPL", "MSFT", "AMD")
        
    Returns:
        Current price, day change, volume, P/E ratio, 52-week range, and more
    """
    return get_live_market_data(ticker)


@mcp.tool()
def fetch_multiple_stocks(tickers: list[str]) -> dict:
    """
    Fetches market data for multiple stock tickers at once.
    Use this when comparing stocks or getting prices for a portfolio.
    
    Args:
        tickers: List of stock symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
        
    Returns:
        Market data for each requested ticker
    """
    return get_multiple_quotes(tickers)


@mcp.tool()
def fetch_price_history(ticker: str, period: str = "1mo") -> dict:
    """
    Fetches historical price data for a stock.
    Use this when user asks about past performance or price trends.
    
    Args:
        ticker: Stock symbol (e.g., "AAPL")
        period: Time period - 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max
        
    Returns:
        Historical OHLCV data with period performance
    """
    return get_price_history(ticker, period)


@mcp.tool()
def calculate_holdings_value(holdings: list[dict]) -> dict:
    """
    Calculates current value and P&L for a list of holdings using live prices.
    Use this to show user their profit/loss on specific positions.
    
    Args:
        holdings: List of holdings with symbol, quantity, and avg_buy_price
        
    Returns:
        Current value, P&L amount, and P&L percentage for each holding
    """
    return calculate_portfolio_value(holdings)

# Research Tools
@mcp.tool()
def search_financial_articles(query: str, top_k: int = 5) -> dict:
    """
    Searches the knowledge base for relevant financial articles and news.
    Use this to find expert opinions, analysis, and news about stocks or market topics.
    
    Args:
        query: Search query (e.g., "Apple earnings outlook", "tech sector analysis")
        top_k: Number of results to return (default 5)
        
    Returns:
        Relevant financial articles and their content
    """
    return search_financial_knowledge(query, top_k)


@mcp.tool()
def search_stock_news(ticker: str, top_k: int = 5) -> dict:
    """
    Searches for news and analysis about a specific stock.
    Use this when user asks about news or sentiment for a particular company.
    
    Args:
        ticker: Stock symbol (e.g., "AAPL", "TSLA")
        top_k: Number of results to return
        
    Returns:
        News and analysis related to the stock
    """
    return search_by_ticker(ticker, top_k)


@mcp.tool()
def search_sentiment(topic: str, top_k: int = 5) -> dict:
    """
    Searches for market sentiment and analysis on a topic.
    Use this when user asks about market outlook or sentiment on sectors/themes.
    
    Args:
        topic: Topic to analyze (e.g., "tech sector", "interest rates", "AI stocks")
        top_k: Number of results to return
        
    Returns:
        Sentiment and analysis documents
    """
    return search_market_sentiment(topic, top_k)


@mcp.tool()
def get_research_context(query: str, user_symbols: list[str] = None) -> dict:
    """
    Builds comprehensive research context combining query search and portfolio context.
    Use this for complex questions that need both general research and personalized context.
    
    Args:
        query: User's question
        user_symbols: List of stock symbols the user owns (for personalized context)
        
    Returns:
        Combined context from multiple research sources
    """
    return get_context_for_query(query, user_symbols)

# MCP Server runner
if __name__ == "__main__":
    print(" Starting MarketAxis MCP Server...")
    print(f" Host: {settings.MCP_SERVER_HOST}")
    print(f" Port: {settings.MCP_SERVER_PORT}")
    print("\n Available Tools:")
    print("  • fetch_user_holdings - Get user's portfolio holdings")
    print("  • fetch_user_alerts - Get user's price alerts")
    print("  • fetch_portfolio_summary - Get portfolio overview")
    print("  • fetch_stock_price - Get real-time stock data")
    print("  • fetch_multiple_stocks - Get data for multiple stocks")
    print("  • fetch_price_history - Get historical prices")
    print("  • calculate_holdings_value - Calculate P&L")
    print("  • search_financial_articles - Search knowledge base")
    print("  • search_stock_news - Search news for a ticker")
    print("  • search_sentiment - Search market sentiment")
    print("  • get_research_context - Build comprehensive context")
    print("\n MCP Server ready!")
    
    # Run the MCP server
    mcp.run(
        host=settings.MCP_SERVER_HOST,
        port=settings.MCP_SERVER_PORT
    )
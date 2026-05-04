from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
from jose import JWTError, jwt

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.tools import StructuredTool

from tools.portfolio import get_user_holdings, get_user_alerts, get_portfolio_summary
from tools.market import (
    get_live_market_data,
    get_multiple_quotes,
    get_price_history,
    calculate_portfolio_value,
    get_earnings_calendar,
    get_financial_statements,
    fetch_quarterly_earnings as market_fetch_quarterly_earnings,
)
from tools.research import (
    search_financial_knowledge,
    search_by_ticker,
    search_market_sentiment,
    get_context_for_query,
    format_sources_for_response
)
from config import settings
from routes.chat_history import router as chat_history_router
from database.mongodb import connect_to_mongodb, close_mongodb_connection


# FastAPI app initialization
app = FastAPI(
    title="Equity Lens Trading Intelligence",
    description="AI-powered financial assistant for portfolio analysis and market research",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:3001"],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await connect_to_mongodb()

@app.on_event("shutdown")
async def shutdown():
    await close_mongodb_connection()

app.include_router(chat_history_router)

# chat request and response model
class ChatRequest(BaseModel):
    query: str
    conversation_history: Optional[list[dict]] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    tools_used: list[str]

# JWT authentication
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        if settings.DEBUG:
            return {"userId": 3, "email": "test@example.com"}
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id = payload.get("userId") or payload.get("user_id") or payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        return {"userId": int(user_id), "email": payload.get("email")}
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

# Longchain tools setup
class EmptyInput(BaseModel):
    pass

class TickerInput(BaseModel):
    ticker: str = Field(description="Stock ticker symbol (e.g., AAPL, MSFT, SNPS)")

class MultipleTickers(BaseModel):
    tickers: str = Field(description="Comma-separated ticker symbols (e.g., AAPL,MSFT,GOOGL)")

class TickerPeriod(BaseModel):
    ticker: str = Field(description="Stock ticker symbol")
    period: str = Field(default="1mo", description="Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max")

class SearchQuery(BaseModel):
    query: str = Field(description="Search query text")

class HistoricalEarningsInput(BaseModel):
    ticker: str = Field(description="Stock ticker symbol (e.g., AMD, AAPL)")
    year: int = Field(description="Fiscal year (e.g., 2023, 2024, 2025)")
    quarter: str = Field(description="Quarter (Q1, Q2, Q3, or Q4)")

def create_tools(user_id: int) -> list:
    
# Portfolio tools   
    def fetch_my_holdings() -> str:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(get_user_holdings(user_id))
            return str(result)
        finally:
            loop.close()
    
    def fetch_my_alerts() -> str:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(get_user_alerts(user_id))
            return str(result)
        finally:
            loop.close()
    
    def fetch_my_portfolio_summary() -> str:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(get_portfolio_summary(user_id))
            return str(result)
        finally:
            loop.close()
    
# Live market data tools
    def fetch_stock_data(ticker: str) -> str:
        result = get_live_market_data(ticker.strip().upper())
        return str(result)
    
    def fetch_multiple_stock_data(tickers: str) -> str:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        result = get_multiple_quotes(ticker_list)
        return str(result)
    
    def fetch_stock_history(ticker: str, period: str = "1mo") -> str:
        result = get_price_history(ticker.strip().upper(), period)
        return str(result)
    
    def fetch_earnings_calendar(ticker: str) -> str:
        result = get_earnings_calendar(ticker.strip().upper())
        return str(result)
    
    def fetch_financial_statements(ticker: str) -> str:
        result = get_financial_statements(ticker.strip().upper())
        return str(result)
    
    def fetch_quarterly_earnings(ticker: str, year: int, quarter: str) -> str:
        """Fetches quarterly earnings from Yahoo Finance (FREE)."""
        result = market_fetch_quarterly_earnings(ticker.strip().upper(), year, quarter.upper())
        return str(result)
    
# Research Tools    
    def search_articles(query: str) -> str:
        result = search_financial_knowledge(query, top_k=5)
        return str(result)
    
    def search_ticker_news(ticker: str) -> str:
        result = search_by_ticker(ticker.strip().upper(), top_k=5)
        return str(result)
    
    def search_market_trends(query: str) -> str:
        result = search_market_sentiment(query, top_k=5)
        return str(result)
    
# Structured Tools Creation
    tools = [
        StructuredTool.from_function(
            func=fetch_my_holdings,
            name="get_my_holdings",
            description="Get the current user's stock holdings across all portfolios. No input required.",
            args_schema=EmptyInput
        ),
        StructuredTool.from_function(
            func=fetch_my_alerts,
            name="get_my_alerts",
            description="Get the current user's price alerts. No input required.",
            args_schema=EmptyInput
        ),
        StructuredTool.from_function(
            func=fetch_my_portfolio_summary,
            name="get_my_portfolio_summary",
            description="Get comprehensive overview of user's portfolio including holdings and alerts. No input required.",
            args_schema=EmptyInput
        ),
        StructuredTool.from_function(
            func=fetch_stock_data,
            name="get_stock_price",
            description="Get real-time stock data including price, P/E ratio, 52-week range, volume. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=fetch_multiple_stock_data,
            name="get_multiple_stock_prices",
            description="Get prices for multiple stocks. Input: comma-separated tickers (e.g., 'AAPL,MSFT,GOOGL').",
            args_schema=MultipleTickers
        ),
        StructuredTool.from_function(
            func=fetch_stock_history,
            name="get_stock_history",
            description="Get historical price data. Input: ticker and period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max).",
            args_schema=TickerPeriod
        ),
        StructuredTool.from_function(
            func=fetch_earnings_calendar,
            name="get_earnings_calendar",
            description="Get earnings dates (past and upcoming) and EPS data for a stock. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=fetch_financial_statements,
            name="get_financial_statements",
            description="Get ACTUAL financial data from SEC filings: revenue, profit, margins, EPS. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=fetch_quarterly_earnings,
            name="get_quarterly_earnings",
            description="""Get quarterly earnings for a specific quarter. Uses Yahoo Finance (FREE).
            Returns: revenue, gross profit, operating income, net income, margins.
            Input: ticker, year (e.g., 2024), quarter (Q1/Q2/Q3/Q4).
            Note: Very recent quarters may have 1-2 week delay.""",
            args_schema=HistoricalEarningsInput
        ),
        StructuredTool.from_function(
            func=search_articles,
            name="search_financial_news",
            description="Search knowledge base for articles and news. Input: search query.",
            args_schema=SearchQuery
        ),
        StructuredTool.from_function(
            func=search_ticker_news,
            name="search_stock_news",
            description="Find news about a specific stock. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=search_market_trends,
            name="search_market_sentiment",
            description="Find market sentiment on topics or sectors. Input: topic query.",
            args_schema=SearchQuery
        ),
    ]
    
    return tools

# Guest user tools
def create_guest_tools() -> list:
    """Create tools for guest users - public market data only, no portfolio access."""
    
# Market Data Tools
    def fetch_stock_data(ticker: str) -> str:
        result = get_live_market_data(ticker.strip().upper())
        return str(result)
    
    def fetch_multiple_stock_data(tickers: str) -> str:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        result = get_multiple_quotes(ticker_list)
        return str(result)
    
    def fetch_stock_history(ticker: str, period: str = "1mo") -> str:
        result = get_price_history(ticker.strip().upper(), period)
        return str(result)
    
    def fetch_earnings_calendar(ticker: str) -> str:
        result = get_earnings_calendar(ticker.strip().upper())
        return str(result)
    
    def fetch_financial_statements(ticker: str) -> str:
        result = get_financial_statements(ticker.strip().upper())
        return str(result)
    
    def fetch_quarterly_earnings(ticker: str, year: int, quarter: str) -> str:
        result = market_fetch_quarterly_earnings(ticker.strip().upper(), year, quarter.upper())
        return str(result)
    
# Research Tools
    def search_articles(query: str) -> str:
        result = search_financial_knowledge(query, top_k=5)
        return str(result)
    
    def search_ticker_news(ticker: str) -> str:
        result = search_by_ticker(ticker.strip().upper(), top_k=5)
        return str(result)
    
    def search_market_trends(query: str) -> str:
        result = search_market_sentiment(query, top_k=5)
        return str(result)
    
# Structured Tools Creation
    tools = [
        StructuredTool.from_function(
            func=fetch_stock_data,
            name="get_stock_price",
            description="Get real-time stock data including price, P/E ratio, 52-week range, volume. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=fetch_multiple_stock_data,
            name="get_multiple_stock_prices",
            description="Get prices for multiple stocks. Input: comma-separated tickers (e.g., 'AAPL,MSFT,GOOGL').",
            args_schema=MultipleTickers
        ),
        StructuredTool.from_function(
            func=fetch_stock_history,
            name="get_stock_history",
            description="Get historical price data. Input: ticker and period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max).",
            args_schema=TickerPeriod
        ),
        StructuredTool.from_function(
            func=fetch_earnings_calendar,
            name="get_earnings_calendar",
            description="Get earnings dates (past and upcoming) and EPS data for a stock. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=fetch_financial_statements,
            name="get_financial_statements",
            description="Get ACTUAL financial data from SEC filings: revenue, profit, margins, EPS. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=fetch_quarterly_earnings,
            name="get_quarterly_earnings",
            description="""Get quarterly earnings for a specific quarter. Uses Yahoo Finance (FREE).
            Returns: revenue, gross profit, operating income, net income, margins.
            Input: ticker, year (e.g., 2024), quarter (Q1/Q2/Q3/Q4).
            Note: Very recent quarters may have 1-2 week delay.""",
            args_schema=HistoricalEarningsInput
        ),
        StructuredTool.from_function(
            func=search_articles,
            name="search_financial_news",
            description="Search knowledge base for articles and news. Input: search query.",
            args_schema=SearchQuery
        ),
        StructuredTool.from_function(
            func=search_ticker_news,
            name="search_stock_news",
            description="Find news about a specific stock. Input: ticker symbol.",
            args_schema=TickerInput
        ),
        StructuredTool.from_function(
            func=search_market_trends,
            name="search_market_sentiment",
            description="Find market sentiment on topics or sectors. Input: topic query.",
            args_schema=SearchQuery
        ),
    ]
    
    return tools

# LangChain Agent Setup
SYSTEM_PROMPT = """You are MarketAxis Trading Intelligence, an expert AI financial assistant.

You help users with:
1. Portfolio Analysis - Analyze holdings, calculate P&L, provide insights
2. Market Data - Fetch real-time prices, metrics, historical data
3. Earnings Information - Get earnings dates, EPS, quarterly results
4. Financial Research - Search articles, news, sentiment
5. Personalized Advice - Combine portfolio data with market research

GUIDELINES:
- Fetch user's portfolio first when they ask about "my stocks" or "my portfolio"
- Use real-time data for current prices - never make up numbers
- Use get_quarterly_earnings for specific quarter results (e.g., "AMD Q3 2024")
- Use get_financial_statements for latest overall financials
- Format currency as $1,234.56 and percentages as +2.34%
- If data isn't available, say so clearly
- Be concise but informative

When providing analysis:
- Start with the key insight
- Support with data from tools
- End with actionable recommendations"""


GUEST_SYSTEM_PROMPT = """You are MarketAxis Trading Intelligence, an expert AI financial assistant.

You help users with:
1. Market Data - Fetch real-time prices, metrics, historical data
2. Earnings Information - Get earnings dates, EPS, quarterly results
3. Financial Research - Search articles, news, sentiment

GUIDELINES:
- Use real-time data for current prices - never make up numbers
- Use get_quarterly_earnings for specific quarter results (e.g., "AMD Q3 2024")
- Use get_financial_statements for latest overall financials
- Format currency as $1,234.56 and percentages as +2.34%
- If data isn't available, say so clearly
- Be concise but informative

IMPORTANT: You do NOT have access to portfolio data for guest users.
If a user asks about "my portfolio", "my stocks", or "my holdings", politely explain that 
portfolio features require signing in, and offer to help with general market data instead.

When providing analysis:
- Start with the key insight
- Support with data from tools
- End with actionable recommendations"""


def create_agent(user_id: int):
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    tools = create_tools(user_id)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.DEBUG,
        handle_parsing_errors=True,
        max_iterations=10,
        return_intermediate_steps=True
    )
    
    return agent_executor


def create_guest_agent():
    """Create an agent for guest users with limited tools (no portfolio access)."""
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    tools = create_guest_tools()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", GUEST_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.DEBUG,
        handle_parsing_errors=True,
        max_iterations=10,
        return_intermediate_steps=True
    )
    
    return agent_executor

# API Endpoints
@app.get("/")
async def root():
    return {
        "service": "MarketAxis Trading Intelligence",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "llm_model": settings.LLM_MODEL,
        "pinecone_index": settings.PINECONE_INDEX_NAME,
        "debug_mode": settings.DEBUG
    }


@app.post("/v1/ai/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["userId"]
        agent_executor = create_agent(user_id)
        
        chat_history = []
        if request.conversation_history:
            for msg in request.conversation_history[-10:]:
                if msg.get("role") == "user":
                    chat_history.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    chat_history.append(AIMessage(content=msg.get("content", "")))
        
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: agent_executor.invoke({
                "input": request.query,
                "chat_history": chat_history
            })
        )
        
        answer = result.get("output", "I apologize, but I couldn't generate a response.")
        
        tools_used = []
        sources = []
        
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if len(step) >= 2:
                    action = step[0]
                    tool_output = step[1]
                    
                    if hasattr(action, "tool"):
                        tools_used.append(action.tool)
                    
                    if "search" in str(action.tool).lower():
                        try:
                            if "'results':" in tool_output:
                                import ast
                                output_dict = ast.literal_eval(tool_output)
                                if output_dict.get("success") and output_dict.get("data", {}).get("results"):
                                    for doc in output_dict["data"]["results"][:3]:
                                        content = doc.get("content", "")[:150]
                                        if content:
                                            sources.append(content + "...")
                        except:
                            pass
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            tools_used=list(set(tools_used))
        )
        
    except Exception as e:
        if settings.DEBUG:
            raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request."
        )


@app.post("/v1/ai/simple-chat")
async def simple_chat(request: ChatRequest):
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Debug mode only")
    
    test_user = {"userId": 3}
    return await chat(request, test_user)

# Server runner
if __name__ == "__main__":
    import uvicorn
    
    print("Starting MarketAxis Trading Intelligence Server...")
    print(f"Host: {settings.HOST}")
    print(f"Port: {settings.PORT}")
    print(f"LLM Model: {settings.LLM_MODEL}")
    print(f"Pinecone Index: {settings.PINECONE_INDEX_NAME}")
    print(f"Debug Mode: {settings.DEBUG}")
    print("\n Endpoints:")
    print("  • GET  / - Health check")
    print("  • GET  /health - Detailed health")
    print("  • POST /v1/ai/chat - Main chat (requires auth)")
    print("  • POST /v1/ai/simple-chat - Test chat (debug only)")
    print("  • POST /v1/ai/sessions/chat/guest - Guest chat (no auth)")
    print("\n Available Tools:")
    print("  • get_my_holdings - Portfolio holdings (auth only)")
    print("  • get_my_alerts - Price alerts (auth only)")
    print("  • get_my_portfolio_summary - Portfolio overview (auth only)")
    print("  • get_stock_price - Real-time stock data")
    print("  • get_multiple_stock_prices - Multiple stocks")
    print("  • get_stock_history - Historical prices")
    print("  • get_earnings_calendar - Earnings dates & EPS")
    print("  • get_financial_statements - SEC filing data")
    print("  • get_quarterly_earnings - Specific quarter earnings")
    print("  • search_financial_news - Knowledge base search")
    print("  • search_stock_news - Stock-specific news")
    print("  • search_market_sentiment - Market sentiment")
    print("\n Server ready!")
    
    uvicorn.run(
        "server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

# uvicorn server:app --reload --port 8000
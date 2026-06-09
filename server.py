from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import json

from jose import JWTError, jwt

from agents import Agent, Runner, ModelSettings
from agents.mcp import MCPServerStreamableHttp
from agents.mcp.util import create_static_tool_filter
from agents.items import ToolCallItem, ToolCallOutputItem

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


# Safety net: ensure ANY unhandled exception returns a JSON response. Exception
# handlers run inside ExceptionMiddleware (below CORSMiddleware), so their
# response flows back through CORS and keeps the Access-Control-* headers.
# Without this, an unhandled error is caught by Starlette's outermost
# ServerErrorMiddleware, which bypasses CORS and makes the browser report the
# failure as a CORS error ("Response headers (0)").
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    detail = str(exc) if settings.DEBUG else "Internal server error."
    return JSONResponse(status_code=500, content={"success": False, "detail": detail})


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


# ============================================
# AGENT SYSTEM PROMPTS
# ============================================
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
- Use fetch_financial_statements for latest overall financials
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
- Use fetch_financial_statements for latest overall financials
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


# ============================================
# MCP AGENT
# ============================================
# The agent runs over the MCP server (mcp_server.py), which exposes all the
# tools/* functions over streamable HTTP. We connect a fresh MCP session per
# request so the authenticated user id can be passed as a header (X-User-Id);
# the MCP portfolio tools resolve the user from that header, never from the LLM.

# URL of the MCP tool server (the separate ai-mcp-service). In production set the
# MCP_URL env var to the private host (e.g. https://ai-mcp-service.internal/mcp);
# locally it is built from MCP_SERVER_HOST/PORT.
# Note: FastMCP serves the endpoint at /mcp (no trailing slash); the slashed form
# 307-redirects, which the MCP client will not follow.
MCP_URL = settings.MCP_URL or f"http://{settings.MCP_SERVER_HOST}:{settings.MCP_SERVER_PORT}/mcp"

# Portfolio tools are blocked for guests (they require an authenticated user).
PORTFOLIO_TOOLS = ["fetch_user_holdings", "fetch_user_alerts", "fetch_portfolio_summary"]

_MODEL_SETTINGS = ModelSettings(
    temperature=settings.LLM_TEMPERATURE,
    max_tokens=settings.LLM_MAX_TOKENS,
)


def _coerce_output(output) -> Optional[dict]:
    """
    Best-effort parse of an MCP tool output into the tool's {"success", "data"} dict.

    MCP results arrive wrapped as a content block {"type": "text", "text": "<json>"}
    (or a list of such blocks), so unwrap that before parsing.
    """
    if isinstance(output, list):
        for block in output:
            parsed = _coerce_output(block)
            if parsed is not None:
                return parsed
        return None
    if isinstance(output, dict):
        if output.get("type") == "text" and isinstance(output.get("text"), str):
            return _coerce_output(output["text"])
        return output
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except (ValueError, TypeError):
            return None
        return _coerce_output(parsed) if isinstance(parsed, (dict, list)) else None
    return None


def _extract_sources(output) -> list[str]:
    """Pull short source snippets out of a search tool's structured output."""
    data = _coerce_output(output)
    if not data or not data.get("success"):
        return []
    results = (data.get("data") or {}).get("results") or []
    snippets = []
    for doc in results[:3]:
        content = (doc.get("content") or "")[:150]
        if content:
            snippets.append(content + "...")
    return snippets


def _normalize(result) -> dict:
    """Turn an Agents SDK RunResult into our {answer, tools_used, sources} contract."""
    answer = result.final_output or "I apologize, but I couldn't generate a response."

    tools_used: list[str] = []
    sources: list[str] = []
    call_names: dict[str, str] = {}

    for item in result.new_items:
        if isinstance(item, ToolCallItem):
            raw = item.raw_item
            name = getattr(raw, "name", None)
            if name:
                tools_used.append(name)
                call_id = getattr(raw, "call_id", None)
                if call_id:
                    call_names[call_id] = name
        elif isinstance(item, ToolCallOutputItem):
            raw = item.raw_item
            call_id = raw.get("call_id") if isinstance(raw, dict) else getattr(raw, "call_id", None)
            name = call_names.get(call_id, "")
            if "search" in name.lower():
                sources.extend(_extract_sources(item.output))

    # de-duplicate while preserving order
    return {
        "answer": answer,
        "tools_used": list(dict.fromkeys(tools_used)),
        "sources": sources,
    }


async def run_agent(
    query: str,
    chat_history: Optional[list[dict]] = None,
    user_id: Optional[int] = None,
    guest: bool = False,
) -> dict:
    """
    Run the MarketAxis agent for a single turn against the MCP tool server.

    Args:
        query: the user's message
        chat_history: prior turns as [{"role": "user"|"assistant", "content": str}]
        user_id: authenticated user id (passed to MCP as X-User-Id for portfolio tools)
        guest: when True, use the guest prompt and block portfolio tools

    Returns:
        {"answer": str, "tools_used": list[str], "sources": list[str]}
    """
    headers = {} if guest or user_id is None else {"X-User-Id": str(user_id)}
    tool_filter = (
        create_static_tool_filter(blocked_tool_names=PORTFOLIO_TOOLS) if guest else None
    )

    async with MCPServerStreamableHttp(
        name="MarketAxis",
        params={"url": MCP_URL, "headers": headers},
        cache_tools_list=True,
        client_session_timeout_seconds=30,
        tool_filter=tool_filter,
    ) as mcp_server:
        agent = Agent(
            name="MarketAxis Trading Intelligence",
            instructions=GUEST_SYSTEM_PROMPT if guest else SYSTEM_PROMPT,
            model=settings.LLM_MODEL,
            model_settings=_MODEL_SETTINGS,
            mcp_servers=[mcp_server],
        )

        input_items: list[dict] = []
        for msg in (chat_history or [])[-10:]:
            role = msg.get("role")
            if role in ("user", "assistant"):
                input_items.append({"role": role, "content": msg.get("content", "")})
        input_items.append({"role": "user", "content": query})

        result = await Runner.run(agent, input=input_items, max_turns=10)

    return _normalize(result)


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
        "mcp_url": MCP_URL,
        "debug_mode": settings.DEBUG
    }


@app.post("/v1/ai/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await run_agent(
            query=request.query,
            chat_history=request.conversation_history,
            user_id=current_user["userId"],
        )
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            tools_used=result["tools_used"],
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
    print(f"MCP Server: {MCP_URL}")
    print(f"Pinecone Index: {settings.PINECONE_INDEX_NAME}")
    print(f"Debug Mode: {settings.DEBUG}")
    print("\n NOTE: start the MCP tool server too:  python mcp_server.py")
    print("\n Endpoints:")
    print("  • GET  / - Health check")
    print("  • GET  /health - Detailed health")
    print("  • POST /v1/ai/chat - Main chat (requires auth)")
    print("  • POST /v1/ai/simple-chat - Test chat (debug only)")
    print("  • POST /v1/ai/sessions/chat/guest - Guest chat (no auth)")
    print("\n Server ready!")

    uvicorn.run(
        "server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

# uvicorn server:app --reload --port 8000

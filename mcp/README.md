# ai-mcp-service

MCP tool server for the MarketAxis trading platform. Exposes portfolio, market-data,
and financial-research tools over the **Model Context Protocol** (streamable HTTP).

It is consumed by the `ai-service` FastAPI app (the OpenAI Agents SDK agent connects to
this server and calls these tools). This service holds no chat/agent logic — only tools.

## Tools

- **Portfolio** (auth via `X-User-Id` header): `fetch_user_holdings`, `fetch_user_alerts`, `fetch_portfolio_summary`
- **Market data**: `fetch_stock_price`, `fetch_multiple_stocks`, `fetch_price_history`, `calculate_holdings_value`, `fetch_earnings_calendar`, `fetch_financial_statements`, `get_quarterly_earnings`
- **Research (RAG)**: `search_financial_articles`, `search_stock_news`, `search_sentiment`, `get_research_context`

All tools return `{"success": bool, "data": {...}, "error": str}`.

## Run locally

```bash
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source venv/bin/activate && pip install -r requirements.txt  # macOS/Linux

cp .env.example .env   # then fill in the keys
./venv/Scripts/python.exe mcp_server.py
```

Serves the MCP endpoint at `POST http://<host>:<port>/mcp` (note: `/mcp/` 307-redirects).

## Deploy

Start command: `python mcp_server.py`. Set `MCP_SERVER_HOST=0.0.0.0` so it binds the
platform port (`MCP_SERVER_PORT` falls back to `$PORT`).

> **Security:** this server has **no authentication**. Anyone who can reach it can call any
> tool — including portfolio data (via a forged `X-User-Id` header) and the Postgres DB.
> It MUST be deployed on a **private network** (e.g. a private service, not a public URL),
> reachable only by `ai-service`.

## Environment variables

See `.env.example`: `OPENAI_API_KEY`, `EMBEDDING_MODEL`, `PINECONE_API_KEY`,
`PINECONE_INDEX_NAME`, `RAG_TOP_K`, `DATABASE_URL`, `MCP_SERVER_HOST`, `MCP_SERVER_PORT`.

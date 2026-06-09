#!/usr/bin/env bash
# Single-service launcher: run the vendored MCP tool server alongside the FastAPI
# AI service in the same deployment. The MCP server listens on a fixed internal
# port (127.0.0.1:8001) and is never exposed publicly; the FastAPI app binds the
# platform's $PORT. The AI service reaches the MCP over loopback, so MCP traffic
# never crosses the public edge (no Cloudflare rate-limit / 429).
set -euo pipefail

MCP_PORT="${MCP_SERVER_PORT:-8001}"

# Start the MCP server. We unset PORT for this child so its config does NOT grab
# the platform's public $PORT (its config reads PORT first); it falls back to
# MCP_SERVER_PORT (8001). It runs from the ./mcp dir so its `from config`/`tools`
# imports and .env resolve correctly.
(
  cd mcp
  env -u PORT MCP_SERVER_HOST=127.0.0.1 MCP_SERVER_PORT="$MCP_PORT" python mcp_server.py
) &
MCP_PID=$!

# If the MCP process dies, take the whole container down so the platform restarts it.
trap 'kill "$MCP_PID" 2>/dev/null || true' EXIT

# Wait for the MCP server to accept connections before starting the API.
echo "Waiting for MCP server on 127.0.0.1:${MCP_PORT} ..."
for i in $(seq 1 30); do
  if python -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', ${MCP_PORT}))==0 else 1)"; then
    echo "MCP server is up."
    break
  fi
  if ! kill -0 "$MCP_PID" 2>/dev/null; then
    echo "MCP server exited during startup." >&2
    exit 1
  fi
  sleep 1
done

# Start the public API in the foreground (becomes the container's main process).
exec uvicorn server:app --host 0.0.0.0 --port "${PORT:-8000}"

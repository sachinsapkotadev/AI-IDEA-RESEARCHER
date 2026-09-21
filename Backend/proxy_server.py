"""
OpenRouter API Key Rotation Proxy
Round-robins requests across multiple API keys from .env.
Proxies to https://openrouter.ai/api/v1

Usage:
    python proxy_server.py                    # starts on port 3457
    OPENROUTER_PROXY_PORT=8080 python proxy_server.py

Config: .env (OPENROUTER_API_KEY_01 .. _50)
"""

import os
import sys
import asyncio
from itertools import cycle
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import uvicorn

# ── Load .env from Backend root ─────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

# ── Collect API keys ────────────────────────────────────────────────────
def get_api_keys() -> list[str]:
    keys = []
    for i in range(1, 51):
        num = str(i).zfill(2)
        key = os.getenv(f"OPENROUTER_API_KEY_{num}", "")
        if key and "YOUR_KEY_HERE" not in key and "xxxxxxxx" not in key:
            keys.append(key)
    # Fallback: single key
    if not keys:
        single = os.getenv("OPENROUTER_API_KEY", "")
        if single:
            keys.append(single)
    return keys


API_KEYS = get_api_keys()
UPSTREAM = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MAX_RETRIES = int(os.getenv("OPENROUTER_MAX_RETRIES", "3"))
PROXY_PORT = int(os.getenv("OPENROUTER_PROXY_PORT", "3457"))
PROXY_HOST = os.getenv("OPENROUTER_PROXY_HOST", "127.0.0.1")

# ── Key rotation ────────────────────────────────────────────────────────
key_cycle = cycle(API_KEYS) if API_KEYS else None
lock = asyncio.Lock()


async def next_key() -> str | None:
    async with lock:
        if key_cycle is None:
            return None
        return next(key_cycle)


# ── FastAPI app ─────────────────────────────────────────────────────────
app = FastAPI(title="OpenRouter Key Rotation Proxy", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "keys_loaded": len(API_KEYS),
        "strategy": "round-robin",
        "upstream": UPSTREAM,
        "port": PROXY_PORT,
    }


@app.get("/")
async def root():
    return await health()


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    if not API_KEYS:
        return JSONResponse(
            status_code=500,
            content={"error": "No valid API keys. Add them to Backend/.env"},
        )

    api_key = await next_key()
    key_idx = (list(next_key.__code__.co_freevars).index("key_cycle") if False else 0)
    # Log
    key_num = API_KEYS.index(api_key) + 1 if api_key in API_KEYS else 0
    print(f"[proxy] {request.method} /{path}  key #{key_num}/{len(API_KEYS)}")

    # Build upstream URL
    upstream_url = f"{UPSTREAM}/{path}"
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    # Read request body
    body = await request.body()

    # Forward headers (drop hop-by-hop)
    headers = {}
    skip = {"host", "connection", "keep-alive", "transfer-encoding", "content-length"}
    for k, v in request.headers.items():
        if k.lower() not in skip:
            headers[k] = v
    headers["authorization"] = f"Bearer {api_key}"

    if body and "content-type" not in headers:
        headers["content-type"] = "application/json"

    # Proxy with retry on 429
    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.request(
                    method=request.method,
                    url=upstream_url,
                    headers=headers,
                    content=body if body else None,
                )

                # 429 = rate limited, rotate key and retry
                if resp.status_code == 429 and attempt < MAX_RETRIES - 1:
                    print(f"[proxy] 429 on key #{key_num}, rotating...")
                    api_key = await next_key()
                    key_num = API_KEYS.index(api_key) + 1 if api_key in API_KEYS else 0
                    headers["authorization"] = f"Bearer {api_key}"
                    await asyncio.sleep(0.2)
                    continue

                # Return response
                resp_headers = dict(resp.headers)
                resp_headers["x-proxy-key"] = str(key_num)
                resp_headers["x-proxy-attempt"] = str(attempt + 1)
                # Remove problematic headers
                for h in ["transfer-encoding", "content-encoding", "content-length"]:
                    resp_headers.pop(h, None)

                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers=resp_headers,
                )

            except httpx.RequestError as e:
                print(f"[proxy] Upstream error: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.2)
                    continue
                return JSONResponse(
                    status_code=502,
                    content={"error": "Upstream request failed", "details": str(e)},
                )

    return JSONResponse(status_code=500, content={"error": "Unexpected error"})


# ── Main ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n  OpenRouter Key Rotation Proxy")
    print(f"  ─────────────────────────────")
    print(f"  Listening:  http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"  Upstream:   {UPSTREAM}")
    print(f"  API Keys:   {len(API_KEYS)} loaded")
    print(f"  Strategy:   round-robin + 429 retry (max {MAX_RETRIES})")
    print(f"  Health:     http://{PROXY_HOST}:{PROXY_PORT}/health")
    print()
    if not API_KEYS:
        print("  WARNING: No keys found! Edit Backend/.env and add your OpenRouter keys.\n")
    uvicorn.run(app, host=PROXY_HOST, port=PROXY_PORT, log_level="warning")

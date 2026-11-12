"""A tiny web server for the chatbot page.

Run:   .venv/Scripts/python -m chat_app.app        then open http://localhost:8000
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from chat_app.agent import MODEL, OrderAgent

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")          # reads ANTHROPIC_API_KEY from .env (never committed)
os.environ.setdefault("DATABASE_URL", "postgresql://agent_ro:agent_ro_pw@localhost:5433/orders")

agent = OrderAgent()
conversations: dict[str, list] = {}  # chat history per browser tab (in memory, demo only)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await agent.connect()            # start the MCP server once, when the web app starts
    print(f"MCP server connected. Tools: {[t['name'] for t in agent.tools]}")
    yield
    await agent.close()


app = FastAPI(title="Order Exception Agent", lifespan=lifespan)


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/")
def page():
    return FileResponse(ROOT / "chat_app" / "static" / "index.html")


@app.get("/api/status")
def status():
    return {"model": MODEL, "tools": [t["name"] for t in agent.tools],
            "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/api/chat")
async def chat(body: ChatIn):
    sid = body.session_id or str(uuid.uuid4())
    history = conversations.setdefault(sid, [])
    checkpoint = len(history)
    try:
        result = await agent.run(history, body.message.strip()[:4000])
    except anthropic.AuthenticationError:
        del history[checkpoint:]
        return {"session_id": sid, "steps": [], "error": True,
                "reply": "The Anthropic API key is missing or invalid. Add it to the .env file and restart."}
    except anthropic.APIConnectionError:
        del history[checkpoint:]
        return {"session_id": sid, "steps": [], "error": True,
                "reply": "Could not reach the Anthropic API. Check your internet connection."}
    except anthropic.APIStatusError as exc:
        del history[checkpoint:]
        return {"session_id": sid, "steps": [], "error": True,
                "reply": f"The Anthropic API returned an error ({exc.status_code}): {exc.message}"}
    except TypeError as exc:   # raised by the SDK before any request when no key is configured
        del history[checkpoint:]
        if "authentication" not in str(exc):
            raise
        return {"session_id": sid, "steps": [], "error": True,
                "reply": "No Anthropic API key found. Copy .env.example to .env, paste your key "
                         "after ANTHROPIC_API_KEY=, then restart the chatbot."}
    except Exception as exc:   # anything else: keep the page working and log the details
        del history[checkpoint:]
        print(f"chat error: {exc!r}")
        return {"session_id": sid, "steps": [], "error": True,
                "reply": f"Something went wrong: {type(exc).__name__}. Check the server window for details."}
    return {"session_id": sid, **result}


@app.post("/api/reset")
def reset(body: ChatIn):
    conversations.pop(body.session_id or "", None)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

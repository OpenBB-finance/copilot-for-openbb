import os
import re
import json
import httpx
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
from sse_starlette.sse import EventSourceResponse

from dotenv import load_dotenv
from liquid_copilot.models import (
    AgentQueryRequest
)
from liquid_copilot.prompts import SYSTEM_PROMPT


load_dotenv(".env")
app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:1420",
    "http://localhost:5050",
    "https://pro.openbb.dev",
    "https://pro.openbb.co",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def sanitize_message(message: str) -> str:
    """Sanitize a message by escaping forbidden characters."""
    cleaned_message = re.sub(r"(?<!\{)\{(?!{)", "{{", message)
    cleaned_message = re.sub(r"(?<!\})\}(?!})", "}}", cleaned_message)
    return cleaned_message


async def create_message_stream(
    content: AsyncGenerator[str, None],
) -> AsyncGenerator[dict, None]:
    async for chunk in content:
        yield {"event": "copilotMessageChunk", "data": json.dumps({"delta": chunk})}


@app.get("/copilots.json")
def get_copilot_description():
    """Widgets configuration file for the OpenBB Terminal Pro"""
    return JSONResponse(
        content=json.load(open((Path(__file__).parent.resolve() / "copilots.json")))
    )

@app.post("/v1/query")
async def query(request: AgentQueryRequest) -> EventSourceResponse:
    """Query the Copilot."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in request.messages:
        role = message.role.lower()
        if role not in ['system', 'user', 'assistant']:
            role = 'user'  # Default to 'user' if an invalid role is provided
        messages.append({
            "role": role,
            "content": sanitize_message(message.content)
        })

    async def generate() -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization":
                        f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "HTTP-Referer": "pro.openbb.co",
                    "X-Title": "OpenBB",
                },
                json={
                    "model": "liquid/lfm-40b:free",
                    "messages": messages,
                    "stream": True
                },
                timeout=None
            )
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    line = line.removeprefix("data: ").strip()
                    if line == "[DONE]":
                        break
                    if line:  # Only try to parse non-empty lines
                        try:
                            data = json.loads(line)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e}")
                            print(f"Problematic line: {line}")
                            continue

    return EventSourceResponse(
        content=create_message_stream(generate()),
        media_type="text/event-stream",
    )
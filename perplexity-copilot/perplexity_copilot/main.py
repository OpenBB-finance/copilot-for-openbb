import re
import json
import os
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
from sse_starlette.sse import EventSourceResponse

from dotenv import load_dotenv
from .models import AgentQueryRequest
from .prompts import SYSTEM_PROMPT


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

client = OpenAI(
    api_key=os.getenv("PERPLEXITY_API_KEY"),
    base_url="https://api.perplexity.ai"
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
        yield {"event": "copilotMessageChunk", "data": {"delta": chunk}}


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

    async def generate():
        response_stream = client.chat.completions.create(
            model="llama-3-sonar-large-32k-online",
            messages=messages,
            stream=True,
        )
        for response in response_stream:
            if response.choices[0].delta.content is not None:
                yield response.choices[0].delta.content

    return EventSourceResponse(
        content=create_message_stream(generate()),
        media_type="text/event-stream",
    )
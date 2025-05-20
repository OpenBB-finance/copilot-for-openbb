import re
import json
from pathlib import Path
from typing import AsyncGenerator
from openbb_agents.agent import openbb_agent
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from magentic import (
    UserMessage,
    AssistantMessage,
)

from dotenv import load_dotenv
from sse_starlette import EventSourceResponse
from .models import AgentQueryRequest

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
    content: str,
) -> AsyncGenerator[dict, None]:
    yield {"event": "copilotMessageChunk", "data": {"delta": content}}


@app.get("/copilots.json")
def get_copilot_description():
    """Widgets configuration file for the OpenBB Terminal Pro"""
    return JSONResponse(
        content=json.load(open((Path(__file__).parent.resolve() / "copilots.json")))
    )


@app.post("/v1/query")
async def query(request: AgentQueryRequest) -> EventSourceResponse:
    """Query the Copilot."""

    chat_messages: list[AssistantMessage | UserMessage] = []
    for message in request.messages:
        if message.role == "ai":
            chat_messages.append(
                AssistantMessage(content=sanitize_message(message.content))
            )
        elif message.role == "human":
            chat_messages.append(UserMessage(content=sanitize_message(message.content)))

    try:
        result = openbb_agent(
            str(chat_messages), verbose=True, openbb_pat=os.getenv("OPENBB_PAT")
        )
        return EventSourceResponse(
            create_message_stream(result), media_type="text/event-stream"
        )

    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))

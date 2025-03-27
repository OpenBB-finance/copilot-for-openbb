import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from magentic import (
    AsyncStreamedStr,
    Chat,
    FunctionCall,
)
from sse_starlette.sse import EventSourceResponse

from dotenv import load_dotenv
from common import agent
from common.models import (
    AgentQueryRequest,
)
from .prompts import SYSTEM_PROMPT
from .functions import get_random_palettes


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


@app.get("/copilots.json")
def get_copilot_description():
    """Widgets configuration file for the OpenBB Terminal Pro"""
    return JSONResponse(
        content=json.load(open((Path(__file__).parent.resolve() / "copilots.json")))
    )


@app.post("/v1/query")
async def query(request: AgentQueryRequest) -> EventSourceResponse:
    """Query the Copilot."""

    chat = Chat(
        messages=agent.prepare_messages(SYSTEM_PROMPT, request.messages),
        output_types=[AsyncStreamedStr, FunctionCall],
        functions=[get_random_palettes],  # Add the function to the LLM.
    )

    # This is the main execution loop for the Copilot.
    async def execution_loop(chat: Chat):
        async for event in agent.run_agent(chat):
            yield event

    # Stream the SSEs back to the client.
    return EventSourceResponse(
        content=execution_loop(chat),
        media_type="text/event-stream",
    )

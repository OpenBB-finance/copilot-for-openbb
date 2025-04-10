import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .prompts import SYSTEM_PROMPT

from dotenv import load_dotenv
from common import agent
from common.models import (
    AgentQueryRequest,
)


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

    # This is the main execution loop for the Copilot.
    async def execution_loop():
        async for event in agent.run_openrouter_agent(
            messages=await agent.process_messages(
                system_prompt=SYSTEM_PROMPT,
                messages=request.messages,
                kind="openai",
            ),
            model="deepseek/deepseek-r1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        ):
            yield event

    # Stream the SSEs back to the client.
    return EventSourceResponse(
        content=execution_loop(),
        media_type="text/event-stream",
    )

import logging
import os
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse


from dotenv import load_dotenv
from common import agent
from common.models import (
    QueryRequest,
)
from .functions import get_widget_data
from .prompts import render_system_prompt

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


@app.get("/agents.json")
def get_copilot_description():
    """Widgets configuration file for the OpenBB Terminal Pro"""
    return JSONResponse(
        content={
            "gemini_experimental": {
                "name": "Gemini Experimental",
                "description": "A copilot that uses Gemini as its LLM.",
                "image": "https://github.com/OpenBB-finance/copilot-for-terminal-pro/assets/14093308/7da2a512-93b9-478d-90bc-b8c3dd0cabcf",
                "endpoints": {"query": "http://localhost:7777/v1/query"},
                "features": {
                    "widget-dashboard-select": True,
                    "widget-dashboard-search": False,
                },
            }
        }
    )


async def start_music(energetic: bool, loud: bool) -> AsyncGenerator[str, None]:
    yield f"Playing {energetic} and {loud} music."


@app.post("/v1/query")
async def query(request: QueryRequest) -> EventSourceResponse:
    """Query the Copilot."""

    openbb_agent = agent.OpenBBAgent(
        query_request=request,
        system_prompt=render_system_prompt(widget_collection=request.widgets),
        functions=[get_widget_data],
        chat_class=agent.GeminiChat,
        model="gemini-2.0-flash-001",
        # If using Google AI Studio instead of Vertex AI, comment out the lines
        # below and make sure the GEMINI_API_KEY environment variable is set
        vertex_ai=True,
        project=os.environ["GCP_PROJECT_ID"],
        location="us-central1",
    )

    # Stream the SSEs back to the client.
    return EventSourceResponse(
        content=openbb_agent.run(),
        media_type="text/event-stream",
    )

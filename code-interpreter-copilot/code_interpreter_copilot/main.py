from multiprocessing import Process, Queue
import re
import json
from pathlib import Path
from typing import Any, AsyncGenerator
import uuid
import logging

from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from magentic import (
    FunctionCall,
    FunctionResultMessage,
    chatprompt,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    AsyncStreamedStr,
)
import pandas as pd
from sse_starlette.sse import EventSourceResponse

from dotenv import load_dotenv
from common.models import (
    AgentQueryRequest,
    ChartParameters,
    ClientArtifact,
    RawContext,
    StatusUpdateSSE,
    StatusUpdateSSEData,
)
from .prompts import SYSTEM_PROMPT
from .code_interpreter import repl_worker

logger = logging.getLogger("uvicorn.error")

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
    content: AsyncStreamedStr,
) -> AsyncGenerator[dict, None]:
    async for chunk in content:
        yield {"event": "copilotMessageChunk", "data": json.dumps({"delta": chunk})}


@app.get("/copilots.json")
def get_copilot_description():
    """Widgets configuration file for the OpenBB Terminal Pro"""
    return JSONResponse(
        content=json.load(open((Path(__file__).parent.resolve() / "copilots.json")))
    )


def handle_function_call(result: FunctionCall) -> ClientArtifact:
    logger.info(f"Running function call: {result}")
    output = result()
    if "```json" in output:
        output = json.loads(output.split("```json")[1].split("```")[0])
        if output["type"] == "table":
            return ClientArtifact(
                type="table",
                name=f"table_artifact_{uuid.uuid4()}",
                description=result.arguments["code"],
                content=json.loads(output["content"]),
            )
        elif output["type"] == "chart":
            return ClientArtifact(
                type="chart",
                name=f"chart_artifact_{uuid.uuid4()}",
                description=result.arguments["code"],
                content=json.loads(output["content"]),
                chart_params=ChartParameters(
                    chartType=output["chart_params"]["chartType"],
                    xKey=output["chart_params"]["xKey"],
                    yKey=[output["chart_params"]["yKey"]],
                ),
            )

    return ClientArtifact(
        type="text",
        name=f"text_artifact_{uuid.uuid4()}",
        description=result.arguments["code"],
        content=output,
    )


class HandledContext(BaseModel):
    context_prompt_str: str
    loaded_context: dict[str, Any]


def handle_context(context: str | list[RawContext]) -> HandledContext:
    loaded_context = {}
    context_prompt_str = ""
    if isinstance(context, list):
        for context_item in context:
            df = pd.DataFrame(json.loads(context_item.data.content))
            clean_name = "df_" + context_item.name.replace(" ", "_").replace(
                "-", "_"
            ).replace(".", "_")
            clean_name += (
                f"_{context_item.metadata.get('symbol')}"
                if context_item.metadata and context_item.metadata.get("symbol")
                else ""
            )
            clean_name = clean_name.lower()
            loaded_context[clean_name] = df

            context_prompt_str += f"## {context_item.name}\n"
            context_prompt_str += f"Available as a pandas dataframe via the variable `{clean_name}` in the code interpreter.\n"
            context_prompt_str += f"Description: {context_item.description}\n"
            context_prompt_str += f"Metadata: {context_item.metadata}\n"
            context_prompt_str += f"Preview:\n{df.head().to_json(orient='records', lines=True, date_format='iso')}\n"
            context_prompt_str += "---"
            context_prompt_str += "\n\n"

    return HandledContext(
        context_prompt_str=context_prompt_str, loaded_context=loaded_context
    )


@app.post("/v1/query")
async def query(request: AgentQueryRequest) -> EventSourceResponse:
    """Query the Copilot."""

    chat_messages = []
    for message in request.messages:
        if message.role == "ai":
            chat_messages.append(
                AssistantMessage(content=sanitize_message(message.content))
            )
        elif message.role == "human":
            chat_messages.append(UserMessage(content=sanitize_message(message.content)))

    if request.context:
        handled_context = handle_context(request.context)

    def llm_run_code(code: str) -> str:
        """Use this tool to run Python code and get the output.

        To return structured data (eg. a numpy array or dataframe) as a table for
        the user, return it by calling the function `return_structured(<data>)`.

        Never pass in unevaluated expressions like `range(10)` into return_structured.
        """
        input_queue = Queue()
        output_queue = Queue()
        worker_process = Process(
            target=repl_worker,
            args=(input_queue, output_queue, handled_context.loaded_context),
        )
        worker_process.start()
        input_queue.put(code)
        result = output_queue.get()
        input_queue.put(None)  # Signal to shut down
        worker_process.join()
        return result

    async def execution_loop() -> AsyncGenerator[Any, None]:
        count = 0
        MAX_CALLS = 10
        while count < MAX_CALLS:
            count += 1

            @chatprompt(
                SystemMessage(SYSTEM_PROMPT), *chat_messages, functions=[llm_run_code]
            )
            async def _llm(context: str) -> AsyncStreamedStr | FunctionCall: ...

            # Run the LLM
            logger.info("Running LLM...")
            result = await _llm(context=handled_context.context_prompt_str)

            # Handle the response
            if isinstance(result, FunctionCall):
                yield StatusUpdateSSE(
                    data=StatusUpdateSSEData(
                        eventType="INFO",
                        message="Running code",
                        details=[{"code": result.arguments["code"]}],
                        artifacts=None,
                    )
                ).model_dump()
                artifact = handle_function_call(result)
                yield StatusUpdateSSE(
                    data=StatusUpdateSSEData(
                        eventType="INFO",
                        message="Completed code execution",
                        artifacts=[artifact],
                    )
                ).model_dump()

                # Add the function call to the chat messages
                chat_messages.append(AssistantMessage(result))
                # Add the function result to the chat messages
                chat_messages.append(
                    FunctionResultMessage(
                        content=artifact.content,
                        function_call=result,
                    )
                )
            elif isinstance(result, AsyncStreamedStr):
                async for event in create_message_stream(result):
                    yield event
                break

    return EventSourceResponse(execution_loop())
import json
from common.models import (
    LlmClientFunctionCallResult,
    LlmClientMessage,
    StatusUpdateSSE,
    StatusUpdateSSEData,
)
from magentic import (
    AssistantMessage,
    AsyncStreamedStr,
    Chat,
    FunctionCall,
    FunctionResultMessage,
    AnyMessage,
    SystemMessage,
    UserMessage,
)
from typing import Any, AsyncGenerator, Literal
import re


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


def reasoning_step(
    event_type: Literal["INFO", "WARNING", "ERROR"],
    message: str,
    details: dict[str, Any] | None = None,
) -> StatusUpdateSSE:
    return StatusUpdateSSE(
        data=StatusUpdateSSEData(
            eventType=event_type,
            message=message,
            details=[details] if details else [],
        )
    )


def prepare_messages(
    system_prompt: str,
    messages: list[LlmClientFunctionCallResult | LlmClientMessage],
) -> list[AnyMessage]:
    chat_messages: list[AnyMessage] = [SystemMessage(system_prompt)]
    for message in messages:
        match message:
            case LlmClientMessage(role="human"):
                chat_messages.append(UserMessage(content=message.content))
            case LlmClientMessage(role="ai"):
                chat_messages.append(AssistantMessage(content=message.content))
            case _:
                raise ValueError(f"Unsupported message type: {message}")
    return chat_messages


async def run_agent(
    chat: Chat, max_completions: int = 10
) -> AsyncGenerator[dict, None]:
    completion_count = 0
    # We set a limit to avoid infinite loops.
    while completion_count < max_completions:
        completion_count += 1
        chat = await chat.asubmit()
        # Handle a streamed text response.
        if isinstance(chat.last_message.content, AsyncStreamedStr):
            async for event in create_message_stream(chat.last_message.content):
                yield event
            return
        # Handle a function call.
        elif isinstance(chat.last_message.content, FunctionCall):
            function_call_result: str = ""
            async for event in chat.last_message.content():
                # Yield reasoning steps.
                if isinstance(event, StatusUpdateSSE):
                    yield event.model_dump()
                # Otherwise, append to the function call result.
                else:
                    function_call_result += str(event)
            chat = chat.add_message(
                FunctionResultMessage(
                    content=function_call_result,
                    function_call=chat.last_message.content,
                )
            )

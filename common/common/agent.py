import inspect
import json
from common.models import (
    DataContent,
    DataSourceRequest,
    FunctionCallSSE,
    FunctionCallSSEData,
    LlmClientFunctionCallResult,
    LlmFunctionCall,
    LlmClientMessage,
    StatusUpdateSSE,
    StatusUpdateSSEData,
    Widget,
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
from typing import Any, AsyncGenerator, Awaitable, Callable, Literal, cast
import re
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionAssistantMessageParam,
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


def remote_function_call(
    function: Literal["get_widget_data"],
    output_formatter: Callable[..., Awaitable[str]] | None = None,
    callbacks: list[Callable[..., Awaitable[Any]]] | None = None,
) -> Callable:
    if function not in ["get_widget_data"]:
        raise ValueError(
            f"Unsupported function: {function}. Must be 'get_widget_data'."
        )

    def outer_wrapper(func: Callable):
        class InnerWrapper:
            def __init__(self):
                self.__name__ = func.__name__
                self.__signature__ = inspect.signature(func)
                self.__doc__ = func.__doc__
                self.func = func
                self.function = function
                self.post_process_function = output_formatter
                self.callbacks = callbacks

            async def execute_callbacks(self, data: list[DataContent]) -> None:
                if self.callbacks:
                    for callback in self.callbacks:
                        await callback(data)

            async def execute_post_processing(self, data: list[DataContent]) -> str:
                if self.post_process_function:
                    return await self.post_process_function(data)
                return str(data)

            async def __call__(
                self, *args, **kwargs
            ) -> AsyncGenerator[FunctionCallSSE | StatusUpdateSSE, None]:
                signature = inspect.signature(self.func)
                bound_args = signature.bind(*args, **kwargs).arguments

                async for event in func(*args, **kwargs):
                    if isinstance(event, StatusUpdateSSE):
                        yield event
                    elif isinstance(event, DataSourceRequest):
                        yield FunctionCallSSE(
                            data=FunctionCallSSEData(
                                function=self.function,
                                input_arguments={
                                    "data_sources": [
                                        DataSourceRequest(
                                            widget_uuid=event.widget_uuid,
                                            origin=event.origin,
                                            id=event.id,
                                            input_args=event.input_args,
                                        )
                                    ]
                                },
                                extra_state={
                                    "copilot_function_call_arguments": {
                                        **bound_args,
                                    },
                                    "_locally_bound_function": func.__name__,
                                },
                            )
                        )
                        return
                    else:
                        yield event

        return InnerWrapper()

    return outer_wrapper


def get_remote_data(
    widget: Widget,
    input_arguments: dict[str, Any],
) -> DataSourceRequest:
    return DataSourceRequest(
        widget_uuid=str(widget.uuid),
        origin=widget.origin,
        id=widget.widget_id,
        input_args=input_arguments,
    )


async def process_messages(
    system_prompt: str,
    messages: list[LlmClientFunctionCallResult | LlmClientMessage],
    functions: list[Any] | None = None,
    kind: Literal["magentic", "openai"] = "magentic",
) -> list[AnyMessage] | list[ChatCompletionMessageParam]:
    if kind == "magentic":
        return await _process_messages_magentic(system_prompt, messages, functions)
    elif kind == "openai":
        return await _process_messages_openai(system_prompt, messages)

    raise ValueError(f"Unsupported kind: {kind}")


async def _process_messages_magentic(
    system_prompt: str,
    messages: list[LlmClientFunctionCallResult | LlmClientMessage],
    functions: list[Any] | None = None,
) -> list[AnyMessage]:
    chat_messages: list[AnyMessage] = [SystemMessage(system_prompt)]
    for message in messages:
        match message:
            case LlmClientMessage(role="human"):
                chat_messages.append(UserMessage(content=message.content))
            case LlmClientMessage(role="ai") if isinstance(message.content, str):
                chat_messages.append(AssistantMessage(content=message.content))
            case LlmClientMessage(role="ai") if isinstance(
                message.content, LlmFunctionCall
            ):
                # Everything is handle in the function call result message.
                pass
            case LlmClientFunctionCallResult(role="tool"):
                if not functions:
                    continue
                matching_local_functions = list(
                    filter(
                        lambda x: x.__name__
                        == message.extra_state.get("_locally_bound_function"),
                        functions,
                    )
                )
                wrapped_function = (
                    matching_local_functions[0] if matching_local_functions else None
                )
                if not wrapped_function:
                    raise ValueError(
                        f"Local function not found: {message.extra_state.get('_locally_bound_function')}"
                    )

                function_call = FunctionCall(
                    function=wrapped_function.func,
                    **message.extra_state.get("copilot_function_call_arguments", {}),
                )
                chat_messages.append(AssistantMessage(function_call))

                await wrapped_function.execute_callbacks(message.data)
                chat_messages.append(
                    FunctionResultMessage(
                        content=await wrapped_function.execute_post_processing(
                            message.data
                        ),
                        function_call=function_call,
                    )
                )
            case _:
                raise ValueError(f"Unsupported message type: {message}")
    return chat_messages


async def _process_messages_openai(
    system_prompt: str,
    messages: list[LlmClientFunctionCallResult | LlmClientMessage],
) -> list[ChatCompletionMessageParam]:
    chat_messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system_prompt)
    ]
    for message in messages:
        match message:
            case LlmClientMessage(role="human"):
                chat_messages.append(
                    ChatCompletionUserMessageParam(
                        role="user", content=cast(str, message.content)
                    )
                )
            case LlmClientMessage(role="ai") if isinstance(message.content, str):
                chat_messages.append(
                    ChatCompletionAssistantMessageParam(
                        role="assistant", content=message.content
                    )
                )
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
                if isinstance(event, FunctionCallSSE):
                    yield event.model_dump()
                    return
                # Otherwise, append to the function call result.
                else:
                    function_call_result += str(event)
            chat = chat.add_message(
                FunctionResultMessage(
                    content=function_call_result,
                    function_call=chat.last_message.content,
                )
            )


async def run_openrouter_agent(
    messages: list[ChatCompletionMessageParam],
    model: str,
    api_key: str,
) -> AsyncGenerator[dict | StatusUpdateSSE, None]:
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    stream = await client.chat.completions.create(
        model=model, messages=messages, stream=True
    )

    reasoning = ""
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            if reasoning:
                yield reasoning_step(
                    event_type="INFO",
                    message="Reasoning complete",
                    details={"Reasoning": reasoning},
                ).model_dump()
                reasoning = ""
            yield {
                "event": "copilotMessageChunk",
                "data": json.dumps({"delta": chunk.choices[0].delta.content}),
            }
        elif (
            hasattr(chunk.choices[0].delta, "reasoning")
            and chunk.choices[0].delta.reasoning
        ):
            if not reasoning:
                yield reasoning_step(
                    event_type="INFO",
                    message="Reasoning...",
                ).model_dump()
            reasoning += chunk.choices[0].delta.reasoning  # type: ignore
    return

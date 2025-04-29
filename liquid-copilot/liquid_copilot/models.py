from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class RoleEnum(str, Enum):
    ai = "ai"
    human = "human"


class LlmMessage(BaseModel):
    role: RoleEnum = Field(
        description="The role of the entity that is creating the message"
    )
    content: str = Field(description="The content of the message")


class BaseContext(BaseModel):
    uuid: UUID = Field(description="The UUID of the widget.")
    name: str = Field(description="The name of the widget.")
    description: str = Field(
        description="A description of the data contained in the widget"
    )
    content: Any = Field(description="The data content of the widget")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional widget metadata (eg. the selected ticker, etc)",
    )


class AgentQueryRequest(BaseModel):
    messages: list[LlmMessage] = Field(
        description="A list of messages to submit to the copilot."
    )
    context: list[BaseContext] | None = Field(
        default=None,
        description="Additional context.",
    )
    use_docs: bool = Field(
        default=None, description="Set True to use uploaded docs when answering query."
    )

    @field_validator("messages")
    def check_messages_not_empty(cls, value):
        if not value:
            raise ValueError("messages list cannot be empty.")
        return value

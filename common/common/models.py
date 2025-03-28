from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)
from enum import Enum
import json
import uuid


class RoleEnum(str, Enum):
    ai = "ai"
    human = "human"
    tool = "tool"


class ChartParameters(BaseModel):
    chartType: Literal["line", "bar", "scatter"]
    xKey: str
    yKey: list[str]


class RawObjectDataFormat(BaseModel):
    data_type: Literal["object"] = "object"
    parse_as: Literal["text", "table", "chart"] = "table"
    chart_params: ChartParameters | None = None

    @model_validator(mode="after")
    def validate_chart_params(cls, values):
        if values.parse_as == "chart" and not values.chart_params:
            raise ValueError("chart_params is required when parse_as is 'chart'")
        if values.parse_as != "chart" and values.chart_params:
            raise ValueError("chart_params is only allowed when parse_as is 'chart'")
        return values


class PdfDataFormat(BaseModel):
    data_type: Literal["pdf"]
    filename: str


class ImageDataFormat(BaseModel):
    data_type: Literal["jpg", "jpeg", "png"]
    filename: str


# Discriminated union of data formats
DataFormat = Annotated[
    RawObjectDataFormat | PdfDataFormat | ImageDataFormat,
    Field(discriminator="data_type", default_factory=RawObjectDataFormat),
]


class DataContent(BaseModel):
    content: str = Field(
        description="The data content, either as a raw string, JSON string, or as a base64 encoded string."  # noqa: E501
    )
    data_format: DataFormat = Field(
        default_factory=RawObjectDataFormat,
        description="How the data should be parsed and handled.",
    )


class DataFileReference(BaseModel):
    file_reference: UUID | HttpUrl = Field(
        description="The file reference to the data file. Either a OpenBB Hub file UUID, or a URL to a file."  # noqa: E501
    )
    data_format: DataFormat = Field(
        description="Optional. How the data should be parsed. If not provided, a best-effort attempt will be made to automatically determine the data format.",  # noqa: E501
    )


class LlmClientFunctionCallResult(BaseModel):
    """Contains the result of a function call made against a client."""

    role: RoleEnum = RoleEnum.tool
    function: str = Field(description="The name of the called function.")
    input_arguments: dict[str, Any] | None = Field(
        default=None, description="The input arguments passed to the function"
    )
    data: list[DataContent | DataFileReference] = Field(
        description="The content of the function call."
    )
    extra_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra state to be passed between the client and this service.",
    )


class LlmFunctionCall(BaseModel):
    function: str
    input_arguments: dict[str, Any]


class RawContext(BaseModel):
    uuid: UUID = Field(description="The UUID of the widget.")
    name: str = Field(description="The name of the widget.")
    description: str = Field(
        description="A description of the data contained in the widget"
    )
    data: DataContent = Field(description="The data content of the widget")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional widget metadata (eg. the selected ticker, etc)",
    )


class Undefined:
    pass


class WidgetParam(BaseModel):
    name: str = Field(description="Name of the parameter.")
    type: str = Field(description="Type of the parameter.")
    description: str = Field(description="Description of the parameter.")
    default_value: Any | None = Field(
        default=None, description="Default value of the parameter."
    )
    current_value: Any | None = Field(
        default=None,
        description="Current value of the parameter. Must not be set for 'extra' widgets.",  # noqa: E501
    )
    options: list[Any] | None = Field(
        default=None, description="Optional list of values for enumerations."
    )

    @model_validator(mode="before")
    @classmethod
    def validate_default_value(cls, data: dict):
        # We want to distinguish between a missing default value and an
        # explicitly set default value of None.  There is a difference between
        # my_function(param=None) and my_function(param).
        if "default_value" not in data:
            data["default_value"] = Undefined
        return data


class Widget(BaseModel):
    uuid: UUID = Field(
        description="UUID of the widget. Used by Copilot to identify widgets. Only used internally.",  # noqa: E501
        default_factory=uuid.uuid4,
    )
    origin: str = Field(description="Origin of the widget.")
    widget_id: str = Field(description="Endpoint ID of the widget.")
    name: str = Field(description="Name of the widget.")
    description: str = Field(description="Description of the widget.")
    params: list[WidgetParam] = Field(description="List of parameters for the widget.")
    metadata: dict[str, Any] = Field(
        description="Metadata for the widget, must not overlap with current_params."
    )


class LlmClientMessage(BaseModel):
    role: RoleEnum = Field(
        description="The role of the entity that is creating the message"
    )
    content: str | LlmFunctionCall = Field(
        description="The content of the message or the result of a function call."
    )

    @field_validator("content", mode="before", check_fields=False)
    def parse_content(cls, v):
        if isinstance(v, str):
            try:
                parsed_content = json.loads(v)
                if isinstance(parsed_content, str):
                    # Sometimes we need a second decode if the content is
                    # escaped and string-encoded
                    parsed_content = json.loads(parsed_content)
                return LlmFunctionCall(**parsed_content)
            except (json.JSONDecodeError, TypeError, ValueError):
                return v
        return v


class WidgetCollection(BaseModel):
    primary: list[Widget] = Field(
        default_factory=list, description="Explicitly-added widgets with top priority."
    )
    secondary: list[Widget] = Field(
        default_factory=list,
        description="Dashboard widgets with second-highest priority.",
    )
    extra: list[Widget] = Field(
        default_factory=list, description="Extra data sources or custom backends."
    )


class AgentQueryRequest(BaseModel):
    messages: list[LlmClientFunctionCallResult | LlmClientMessage] = Field(
        description="A list of messages to submit to the copilot."
    )
    context: list[RawContext] | None = Field(
        default=None, description="Additional context."
    )
    widgets: WidgetCollection | None = Field(
        default=None,
        description="A dictionary containing primary, secondary, and extra widgets.",
    )

    @field_validator("messages")
    @classmethod
    def check_messages_not_empty(cls, value):
        if not value:
            raise ValueError("messages list cannot be empty.")
        return value


class DataSourceRequest(BaseModel):
    widget_uuid: str
    origin: str
    id: str
    input_args: dict[str, Any]


class FunctionCallResponse(BaseModel):
    function: str = Field(description="The name of the function to call.")
    input_arguments: dict | None = Field(
        default=None, description="The input arguments to the function."
    )
    extra_state: dict | None = Field(
        default=None,
        description="Extra state to be passed between the client and this service.",
    )


class BaseSSE(BaseModel):
    event: Any
    data: Any

    def model_dump(self, *args, **kwargs) -> dict:
        return {
            "event": self.event,
            "data": self.data.model_dump_json(exclude_none=True),
        }


class FunctionCallSSEData(BaseModel):
    function: Literal["get_widget_data"]
    input_arguments: dict
    extra_state: dict | None = None


class FunctionCallSSE(BaseSSE):
    event: Literal["copilotFunctionCall"] = "copilotFunctionCall"
    data: FunctionCallSSEData


class ClientArtifact(BaseModel):
    """A piece of output data that is returned to the client."""

    type: Literal["text", "table", "chart"]
    name: str
    description: str
    uuid: UUID = Field(default_factory=uuid.uuid4)
    content: str | list[dict]
    chart_params: ChartParameters | None = None

    @model_validator(mode="after")
    def check_chart_params(cls, values):
        if values.type == "chart" and not values.chart_params:
            raise ValueError("chart_params is required for type 'chart'")
        if values.type != "chart" and values.chart_params:
            raise ValueError("chart_params is only allowed for type 'chart'")
        return values


class StatusUpdateSSEData(BaseModel):
    eventType: Literal["INFO", "WARNING", "ERROR"]
    message: str
    group: Literal["reasoning"] = "reasoning"
    details: list[dict[str, Any]] | None = None
    artifacts: list[ClientArtifact] | None = None

    @model_validator(mode="before")
    @classmethod
    def exclude_fields(cls, values):
        # Exclude these fields from being in the "details" field.  (since this
        # pollutes the JSON output)
        _exclude_fields = []

        if details := values.get("details"):
            for detail in details:
                for key in list(detail.keys()):
                    if key.lower() in _exclude_fields:
                        detail.pop(key, None)
        return values


class StatusUpdateSSE(BaseSSE):
    event: Literal["copilotStatusUpdate"] = "copilotStatusUpdate"
    data: StatusUpdateSSEData

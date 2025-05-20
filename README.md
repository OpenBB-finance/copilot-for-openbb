**Note: This is a work-in-progress. API definitions, models, specifications, etc. are still in active development and may change without notice.**

# Bring your own Agent to the OpenBB Workspace

Welcome to the example repository for integrating custom agents into the OpenBB Workspace.

This repository provides everything you need to build and add your own custom
agents that are compatible with the OpenBB Workspace.

## Features
- [Streaming conversations](#basic-conversational-agent)
- [Function calling](#local-function-calling)
- [Retrieve data from widgets in OpenBB Workspace](#remote-function-calling-retrieving-widget-data-from-openbb-workspace)
- [Reasoning Steps / Status Updates](#reasoning-steps--status-updates)
- [Citations](#citations)
- [Support for multiple LLM providers](#llm-configuration)

For a quick start, run one of the included example agents and add it as a custom copilot to OpenBB Workspace (instructions included with each example). Cloning and modifying an existing example is the fastest way to build your own custom agent.

## Introduction

There are a few common reasons why you might want to build your own agent:
- You have a unique data source that you don't want to add as a custom integration to OpenBB.
- You want to use a specific LLM.
- You want to use a local LLM.
- You want a agent that is self-hosted on your infrastructure.
- You are running on-premise in a locked-down environment that doesn't allow data to leave your VPC.


## Examples
If you prefer diving straight into code, we have a growing list of examples of
custom agents in this repository, varying in complexity and features:

- [A basic conversational agent](./01-simple-copilot)
- [A simple agent with local function calling](./02-simple-copilot-local-function-calling)
- [A simple agent that yields reasoning steps to OpenBB Workspace](./03-simple-copilot-reasoning-steps)
- [A simple agent that uses remote function calling to retrieve data from OpenBB Workspace](./04-simple-copilot-openbb-function-calling)
- [A simple agent that can retrieve data from OpenBB Workspace and produce citations](./05-simple-copilot-openbb-citations)
- [A simple agent that can retrieve data from OpenBB Workspace and handle PDF files](./06-simple-copilot-pdf-handling)
- [A simple agent using DeepSeek v3](./20-simple-copilot-deepseek-v3)
- [A reasoning agent using DeepSeek R1](./21-reasoning-copilot-deepseek-r1)
- [An experiment Google Gemini agent](./90-gemini-experimental)

These examples are a good starting point for building your own custom agent if
you are interested in a specific feature or use case.

## Usage

To integrate a custom agent that you can interact with from the OpenBB Workspace,
you'll need to create a backend API that the OpenBB Workspace can make requests to. 

A custom agent consists of an API with two endpoints:

- `/agents.json` -- Describes your custom agent to the OpenBB Workspace
- `/query` -- Receives requests from the OpenBB Workspace and responds with SSEs

Your custom agent API must respond with Server-Sent Events
([SSEs](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)). 

We highly recommend using FastAPI to build your custom agent API. All examples
and documentation will use FastAPI. If you are new to FastAPI, we recommend
checking out the [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/).

### The simplest possible agent

The most basic custom agent is capable only of chatting with the user.

First, let's set our OPENAI_API_KEY:

```bash
export OPENAI_API_KEY=<your-openai-api-key>
```

Now, let's create a basic FastAPI app that uses the `OpenBBAgent` class to chat
with the user:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from dotenv import load_dotenv
from common import agent
from common.models import (
    QueryRequest,
)

load_dotenv(".env")
app = FastAPI()

origins = [
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
    return JSONResponse(
        content={
            "simple_copilot": {
                "name": "Simple Copilot",
                "description": "A simple copilot that can answer questions.",
                "image": "https://github.com/OpenBB-finance/copilot-for-terminal-pro/assets/14093308/7da2a512-93b9-478d-90bc-b8c3dd0cabcf",
                "endpoints": {"query": "http://localhost:7777/query"},
            }
        }
    )


@app.post("/v1/query")
async def query(request: QueryRequest) -> EventSourceResponse:
    openbb_agent = agent.OpenBBAgent(
        query_request=request,
        system_prompt="You are a helpful assistant that can answer questions.",
    )

    return EventSourceResponse(
        content=openbb_agent.run(),
        media_type="text/event-stream",
    )

```

And that's it! All you need to do now is run the FastAPI app:

```bash
uvicorn main:app --reload --port 7777
```

And add it to the OpenBB Workspace as a custom agent:

https://github.com/user-attachments/assets/bd8daae2-6ef4-473e-abbc-cbb92fdec098

You can now chat with your custom agent in the OpenBB Workspace.

The `agent.OpenBBAgent` object is responsible for handling the request from the
OpenBB Workspace, and for streaming the response back to the OpenBB Workspace
via SSEs. All function calling execution, state management, request parsing, etc. is handled automatically for you by the `OpenBBAgent` object.

To stream back messages to the OpenBB Workspace, you must return an
`EventSourceResponse` object from your `/query` endpoint, where the `content` is
the result of calling `OpenBBAgent.run()`.

### Function calling

There are two types of function calling supported by a custom agent:

1. Local function calling
2. Remote function calling

**Local function calling** allows the LLM to execute functions directly within your agent's backend process (typically running locally on your machine).

**Remote function calling** allows the OpenBB Workspace web app to execute functions on the front end to fetch widget data and send it to your custom agent.

OpenBB Workspace functions as both a front-end and a data gateway for all
widgets. This architecture enables your local custom agent to connect with
widgets in the OpenBB Workspace, regardless of whether they're being served locally
on localhost or on a remote web server.

### Local function calling

```python
import random
from typing import AsyncGenerator
from pydantic import BaseModel
import httpx


class Rating(BaseModel):
    average: float
    reviews: int


class Beer(BaseModel):
    id: int
    price: str
    name: str
    rating: Rating
    image: str


async def get_random_stout_beers(n: int = 1) -> AsyncGenerator[str, None]:
    """Get a random stout beer from the Beer API.

    It is recommended to display the image url in the UI
    for the user so that they can see the beer.

    Parameters:
        n: int = 1
            The number of beers to return.
            Maximum is 10.


    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.sampleapis.com/beers/stouts",
            headers={"User-Agent": "OpenBB Example Copilot"},
        )
        if response.status_code != 200:
            yield "Failed to fetch beers."
            return

        data = response.json()
        random_sample = random.sample(data, n)
        beers = [Beer(**beer) for beer in random_sample]

        response_str = "-- Beers --\n"
        for beer in beers:
            response_str += f"name: {beer.name}\n"
            response_str += f"price: {beer.price}\n"
            response_str += f"rating: {beer.rating.average}\n"
            response_str += f"reviews: {beer.rating.reviews}\n"
            response_str += (
                f"image (use this to display the beer image): {beer.image}\n"
            )
            response_str += "-----------------------------------\n"
        yield response_str
        return


@app.post("/v1/query")
async def query(request: QueryRequest) -> EventSourceResponse:
    openbb_agent = agent.OpenBBAgent(
        query_request=request,
        system_prompt="You are a helpful assistant that can answer questions and retrieve stout beers.",
        functions=[get_random_stout_beers],  # 👈 add the function to the `functions` argument
    )

    return EventSourceResponse(
        content=openbb_agent.run(),
        media_type="text/event-stream",
    )

```

<img width="726" src="https://openbb-assets.s3.us-east-1.amazonaws.com/docs/custom_copilot/local_function_calling_example.png" alt="Local Function Calling Example">

To add a local function call to your custom agent, you must define a function
that can be called by the LLM powering your custom agent, and then add that
function to the `functions` argument of the `OpenBBAgent` object.

In the example above, we add a function that returns a list of random stout beers.

A few important things to note:
- The function must be an `async` function.
- The function must be type-hinted.
- The function must yield a string as its output.

It is also recommended to:
- Use a descriptive function name (this is passed to the LLM).
- Use a docstring to describe the function and its parameters (this is passed to the LLM).

When you query the agent, it will be able to call the `get_random_stout_beers` function.

### Remote function calling (retrieving widget data from OpenBB Workspace)

```python
from typing import AsyncGenerator
from common import agent
from common.models import (
    QueryRequest,
    DataContent,
    FunctionCallSSE,
    StatusUpdateSSE,
    Widget,
    WidgetCollection,
)

SYSTEM_PROMPT_TEMPLATE = """\n
You are a helpful financial assistant.

You can use the following functions to help you answer the user's query:
- get_widget_data(widget_uuid: str) -> str: Get the data for a widget. You can use this function multiple times to get the data for multiple widgets.

{widgets_prompt}
"""


def _render_widget(widget: Widget) -> str:
    """Format a widget's information into a LLM-friendly string representation."""
    widget_str = ""
    widget_str += (
        f"uuid: {widget.uuid} <-- use this to retrieve the data for the widget\n"
    )
    widget_str += f"name: {widget.name}\n"
    widget_str += f"description: {widget.description}\n"
    widget_str += "parameters:\n"
    for param in widget.params:
        widget_str += f"  {param.name}={param.current_value}\n"
    widget_str += "-------\n"
    return widget_str


def render_system_prompt(widget_collection: WidgetCollection | None = None) -> str:
    """Render the system prompt for the custom agent, which includes a list of available widgets."""
    widgets_prompt = "# Available Widgets\n\n"
    widgets_prompt += "## Primary Widgets (prioritize using these widgets when answering the user's query):\n\n"
    for widget in widget_collection.primary if widget_collection else []:
        widgets_prompt += _render_widget(widget)
    
    return SYSTEM_PROMPT_TEMPLATE.format(widgets_prompt=widgets_prompt)


async def handle_widget_data(data: list[DataContent]) -> str:
    """Format the data retrieved from a widget into a LLM-friendly string representation."""
    result_str = "--- Data ---\n"
    for content in data:
        result_str += f"{content.content}\n"
        result_str += "------\n"
    return result_str

@agent.remote_function_call(
    function="get_widget_data",
    output_formatter=handle_widget_data,
)
async def get_widget_data(
    widget_uuid: str,
    request: QueryRequest,  # Must be included as an argument
) -> AsyncGenerator[FunctionCallSSE | StatusUpdateSSE, None]:
    """Retrieve data for a widget by specifying the widget UUID."""

    widgets = (
        request.widgets.primary if request.widgets else []
    )

    matching_widgets = list(
        filter(lambda widget: str(widget.uuid) == widget_uuid, widgets)
    )
    widget = matching_widgets[0] if matching_widgets else None

    if not widget:
        yield f"Unable to retrieve data for widget with UUID: {widget_uuid} (is it added as a priority widget in the context?)"  # noqa: E501
        return

    yield agent.remote_data_request(
        widget=widget,
        input_arguments={param.name: param.current_value for param in widget.params},
    )
    return

@app.get("/agents.json")
def get_copilot_description():
    return JSONResponse(
        content={
            "simple_copilot": {
                "name": "Simple Copilot with OpenBB Function Calling",
                "description": "A simple copilot that can answer questions, execute OpenBB function calls, and return reasoning steps.",
                "image": "https://github.com/OpenBB-finance/copilot-for-terminal-pro/assets/14093308/7da2a512-93b9-478d-90bc-b8c3dd0cabcf",
                "endpoints": {
                    "query": "http://localhost:7777/v1/query"
                },
                "features": {
                    "widget-dashboard-select": True,  # 👈 We need to enable remote function calling for the custom agent
                    "widget-dashboard-search": True,  # 👈 We need to enable remote function calling for the custom agent
                },
            }
        }
    )

@app.post("/v1/query")
async def query(request: QueryRequest) -> EventSourceResponse:
    openbb_agent = agent.OpenBBAgent(
        query_request=request,
        system_prompt="You are a helpful assistant that can answer questions and retrieve stout beers.",
        functions=[get_widget_data],  # 👈 add the function to the `functions` argument
    )

    return EventSourceResponse(
        content=openbb_agent.run(),
        media_type="text/event-stream",
    )

```

To allow our custom agent to retrieve data from widgets on a dashboard on OpenBB
Workspace, we must use remote function calling.

To do this, we must:

- Define a function with the `@remote_function_call` decorator
- Update system prompt to include available widgets
- Enable remote function calling in `agents.json` endpoint

In the example above, we use the widget's current parameter values, but in more advanced cases, we could modify these based on the user query.

The function must:
- Be `async`
- Include the `request` parameter
- Use the `@remote_function_call` decorator
- Yield the result of `get_remote_data`, specifying both `widget` and `input_arguments`


#### `@remote_function_call`
The `@remote_function_call` decorator marks a function for retrieving data from OpenBB Workspace widgets.

It requires a `function` parameter (currently only `"get_widget_data"` is supported).

By default, widget data is returned to the LLM as a raw string. You can provide an optional `output_formatter` function that accepts a list of `DataContent` objects and returns a formatted string.

Example of a `DataContent` object with a single item:

```python
from common.models import DataContent, SingleDataContent, RawObjectDataFormat

data_content_example = DataContent(
    items=[
        SingleDataContent(
            content="<content of the widget data>",
            data_format=RawObjectDataFormat(  # Could also be PdfDataFormat or ImageDataFormat
                data_type="object",
                parse_as="table",  # or "chart" or "text"
                chart_params=None
            ),
            citable=True
        )
    ],
    extra_citations=[]
)
```

The `data_format` object provides hints for handling widget data, with `parse_as` indicating whether to treat data as a table, chart, or text. For all available formats, see the `DataFormat` model in [common/models.py](https://github.com/OpenBB-finance/copilot-for-terminal-pro/blob/main/common/common/models.py).

#### `remote_data_request`

The decorated remote function must yield the result of the `agent.remote_data_request`
function, which must specify the `Widget` and `input_arguments` to retrieve data
for. 

To learn more about how widgets work, see the [Widget Priority](#widget-priority) section of this README.

#### `request` 

The `request` argument is the `QueryRequest` object passed to the `query` endpoint, containing conversation messages, added context, and information about dashboard widgets.

It's useful for finding widgets specified by the LLM or accessing other request data. In the `get_widget_data` function above, we use it to filter widgets by UUID.

View the full schema in the `QueryRequest` model in [common/models.py](https://github.com/OpenBB-finance/copilot-for-terminal-pro/blob/main/common/common/models.py) or through the Swagger UI at `<your-custom-agent-url>/docs` (e.g., `http://localhost:7777/docs`).


### Reasoning steps / status updates

```python
from common import agent

async def get_random_stout_beers(n: int = 1) -> AsyncGenerator[str, None]:
    """Get a random stout beer from the Beer API.

    It is recommended to display the image url in the UI
    for the user so that they can see the beer.

    Parameters:
        n: int = 1
            The number of beers to return.
            Maximum is 10.


    """

    yield agent.reasoning_step( # 👈 Yield a reasoning step
        event_type="INFO",
        message="Fetching random stout beers...",
        details={"number of beers": n},
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.sampleapis.com/beers/stouts",
            headers={"User-Agent": "OpenBB Example Copilot"},
        )
        if response.status_code != 200:
            yield agent.reasoning_step( # 👈 Yield a reasoning step
                event_type="ERROR",
                message="Failed to fetch beers.",
                details={"error": "Failed to fetch beers."},
            )
            yield "Failed to fetch beers."
            return

        yield agent.reasoning_step( # 👈 Yield a reasoning step
            event_type="INFO",
            message="Beers fetched successfully.",
        )

        data = response.json()
        random_sample = random.sample(data, n)
        beers = [Beer(**beer) for beer in random_sample]

        response_str = "-- Beers --\n"
        for beer in beers:
            response_str += f"name: {beer.name}\n"
            response_str += f"price: {beer.price}\n"
            response_str += f"rating: {beer.rating.average}\n"
            response_str += f"reviews: {beer.rating.reviews}\n"
            response_str += (
                f"image (use this to display the beer image): {beer.image}\n"
            )
            response_str += "-----------------------------------\n"
        yield response_str
        return
```

This results in the following reasoning step being displayed in the OpenBB Workspace:

<img width="726" alt="reasoning steps example" src="https://github.com/user-attachments/assets/fd0494ad-ea80-41ff-8d30-b90c139cdeb2" />

Reasoning steps (or status updates) provide real-time feedback to users in the OpenBB Workspace during task execution. To implement them, `yield` from the `agent.reasoning_step` function within your custom agent's functions:

- Use `event_type` of `INFO`, `WARNING`, or `ERROR` to indicate severity
- Include a `message` that will display to the user
- Optionally add a `details` dictionary for additional information (displays as an expandable table)

Reasoning steps work with both local and remote functions, as shown in the `get_random_stout_beers` example above.

### Citations
```python
from common import agent

@agent.remote_function_call(
    function="get_widget_data",
    output_formatter=handle_widget_data,
    callbacks=[
        agent.cite_widget,  # 👈 Yield citations for retrieved widgets
    ],
)
async def get_widget_data(
    widget_uuid: str,
    request: QueryRequest,  # Must be included as an argument
) -> AsyncGenerator[FunctionCallSSE | StatusUpdateSSE, None]:
    """Retrieve data for a widget by specifying the widget UUID."""

    widgets = (
        request.widgets.primary if request.widgets else []
    )

    matching_widgets = list(
        filter(lambda widget: str(widget.uuid) == widget_uuid, widgets)
    )
    widget = matching_widgets[0] if matching_widgets else None

    if not widget:
        yield f"Unable to retrieve data for widget with UUID: {widget_uuid} (is it added as a priority widget in the context?)"  # noqa: E501
        return

    yield agent.remote_data_request(
        widget=widget,
        input_arguments={param.name: param.current_value for param in widget.params},
    )
    return
```

To cite widgets whose data is retrieved using remote function calling, you can
use the `agent.cite_widget` callback that is included as part of the `agent`
library. If instead you'd like to have custom control over your citations, you
can implement your own callback function (see the [Custom citations](#custom-citations)
section of this README for an example).

#### Custom citations

Coming soon.

## LLM Configuration

### OpenAI
By default, custom agents use the OpenAI API, and `gpt-4o` as the default model.
This requires an OpenAI API key to be set in the `OPENAI_API_KEY` environment variable.

To use a different model, set the `model` parameter in the `OpenBBAgent` constructor.

```python
openbb_agent = agent.OpenBBAgent(
    ...
    model="gpt-4o-mini",
)
```

### Google Gemini

Custom agents support both Google AI Studio and Vertex AI.

**Google AI Studio**

To use Google AI Studio, set the `GEMINI_API_KEY` environment variable, and specify the `chat_class` parameter in the `OpenBBAgent` constructor as `agent.GeminiChat`:

```python
from common import agent 

...
openbb_agent = agent.OpenBBAgent(
    ...
    chat_class=agent.GeminiChat,
    model="gemini-2.0-flash-001",  # 👈 Specify the model to use (this is the default model)
)
```

**Vertex AI**

To use Vertex AI you must have the `gcloud CLI` installed and [authorized for Vertex AI](https://cloud.google.com/vertex-ai/docs/authentication#client-libs). Then, set the `vertex_ai` parameter in the `OpenBBAgent` constructor to `True` and specify the `project` and `location` parameters:

```python
from common import agent 

...
openbb_agent = agent.OpenBBAgent(
    ...
    chat_class=agent.GeminiChat,
    model="gemini-2.0-flash-001", 
    vertex_ai=True,  # 👈 Enable Vertex AI
    project="your-project-id",  # 👈 Specify your GCP project ID
    location="your-location",  # 👈 Specify your GCP location
)
```

### Widget Priority
Custom agents receive three widget types via the `QueryRequest.widgets` field:

- **Primary widgets**: Explicitly added by the user to the context
- **Secondary widgets**: Present on the active dashboard but not explicitly added
- **Extra widgets**: Any widgets added to OpenBB Workspace (visible or not)

Currently, only primary and secondary widgets are accessible to custom agents, with extra widget support coming soon.

The dashboard below shows a Management Team widget (primary/priority) and a Historical Stock Price widget (secondary):

<img width="1526" alt="example dashboard" src="https://github.com/user-attachments/assets/9f579a2a-7240-41f5-8aa3-5ffd8a6ed7ba" />

If we inspect the `request.widgets` attribute of the `QueryRequest` object, we
can see the following was sent through to the custom agent:

```python
>>> request.widgets
WidgetCollection(
    primary=[
        Widget(
            uuid=UUID('68ab6973-ed1a-45aa-ab20-efd3e016dd48'),
            origin='OpenBB API',
            widget_id='management_team',
            name='Management Team',
            description='Details about the management team of a company, including name, title, and compensation.',
            params=[
                WidgetParam(
                    name='symbol',
                    type='ticker',
                    description='The symbol of the asset, e.g. AAPL,GOOGL,MSFT',
                    default_value=None,
                    current_value='AAPL',
                    options=[]
                )
            ],
            metadata={
                'source': 'Financial Modelling Prep',
                'lastUpdated': 1746177646279
            }
        )
    ],
    secondary=[
        Widget(
            uuid=UUID('bfa0aaaf-0b63-49b9-bb48-b13ef9db514b'),
            origin='OpenBB API',
            widget_id='eod_price',
            name='Historical Stock Price',
            description='Historical stock price data, including open, high, low, close, volume, etc.',
            params=[
                WidgetParam(
                    name='symbol',
                    type='ticker',
                    description='The symbol of the asset, e.g. AAPL,GOOGL,MSFT',
                    default_value=None,
                    current_value='AAPL',
                    options=[]
                ),
                WidgetParam(
                    name='start_date',
                    type='date',
                    description='The start date of the historical data',
                    default_value='2023-05-02',
                    current_value='2023-05-02',
                    options=[]
                )
            ],
            metadata={
                'source': 'Financial Modelling Prep',
                'lastUpdated': 1746177655947
            }
        )
    ],
    extra=[]
)
```

You can also see the parameter information of each widget in the `params` field
of the `Widget` object.

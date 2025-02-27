# Bring your own Copilot to the OpenBB Workspace

Welcome to the example repository for integrating custom copilots into the OpenBB Workspace.

This repository provides everything you need to build and add your own custom
copilots that are compatible with the OpenBB Workspace.

Here are a few common reasons why you might want to build your own copilot:
- You have a unique data source that you don't want to add as a custom integration to OpenBB.
- You want to use a specific LLM.
- You want to use a local LLM.
- You want a Copilot that is self-hosted on your infrastructure.
- You are running on-premise in a locked-down environment that doesn't allow data to leave your VPC.


## Overview

To integrate a custom Copilot that you can interact with from the OpenBB Workspace,
you'll need to create a backend API that the OpenBB Workspace can make requests to.  


Your custom copilot API will respond with Server-Sent Events
([SSEs](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)).

**Note: If you're looking to get started
quickly, we suggest running one of the example copilots included as part of
this repository, and adding it as a custom copilot to the OpenBB Workspace (each example copilot includes instructions on how to run them). Cloning and modifying an example copilot is a great way to build a custom copilot.**

## Migration guide

- **2025-01-16**: The custom copilot protocol has changed. To migrate your custom copilot to the new protocol, see the [migration guide](./docs/migration-guide.md).

## The Copilot protocol is stateless

The most important concept to understand is that the copilot protocol is
_stateless_.  This means that every request from the OpenBB Workspace to your copilot
will include all previous messages (such as AI completions, human messages,
function calls, and function call results) in the request payload.

This means it is not necessary for your custom copilot to maintain any state
between requests. It should simply use the request payload to generate a response.

The OpenBB Workspace is solely responsible for maintaining the conversation state, and will
append the responses to the `messages` array in the request payload. 

## Handling requests from the OpenBB Workspace

The OpenBB Workspace will make POST requests to the `query` endpoint defined in your
`copilots.json` file (more on this later). The payload of this request will
contain data such as the current conversation's messages, any explicitly-added
context, information about widgets on the currently-active dashboard, URLs to
retrieve, and so on.

### API Request Schema

The core of the query request schema you must implement is as follows:

```python
{
  "messages": [  # <-- the chat messages between the user and the copilot (including function calls and results)
    {
      "role": "human",  # <-- each message has a role: "human", "ai", or "tool"
      "content": "Hi there."  # <-- the content of the message
    },
    ...
  ],
  "widgets": {  # <-- an object with primary, secondary, and optional extra lists
    "primary": [  # <-- explicitly added widgets (highest priority)
      {
        "origin": "<origin>", # <-- the origin of the widget (OpenBB API, custom backend name, etc.)
        "widget_id": "<widget_id>", # <-- the ID of the widget  (eg. "stock_price_quote")
        "name": "<widget name>", # <-- the name of the widget (eg. "Stock Price Quote")
        "description": "<widget description>", # <-- the description of the widget
        "params": [  # <-- parameters for the widget
          {
            "name": "<parameter_name>", # <-- parameter name
            "type": "<parameter_type>", # <-- parameter type (string, number, etc.)
            "description": "<parameter description>",  # <-- parameter description
            "current_value": "<current value>", # <-- currently set value of the parameter on the widget
            "default_value": "<default value>" # <-- default value of the parameter on the widget if it's not set
          },
          ...
        ],
        "metadata": {
          "<metadata key>": "<metadata value>",
          ...
        }
      },
      ...
    ],
    "secondary": [  # <-- dashboard widgets (second priority)
      {
        "origin": "<origin>",
        "widget_id": "<widget_id>",
        "name": "<widget name>",
        "description": "<widget description>",
        "params": [],  # <-- same schema as primary params  
        "metadata": {} # <-- same schema as primary params  
      },
      ...
    ],
    "extra": [  # <-- optional list of all other available widgets (only present of the global data toggle is enabled)
      {
        "origin": "<origin>",
        "widget_id": "<widget_id>",
        "name": "<widget name>",
        "description": "<widget description>",
        "params": [  # <-- `extra` widgets don't have current values, since the widgets are not currently visible on the dashboard
          {
            "name": "<parameter_name>",
            "type": "<parameter_type>", 
            "description": "<parameter description>",
            "default_value": "<default value>"
          },
          ...
        ],
        "metadata": {}
      },
      ...
    ]
  },
  "context": [  # <-- reserved for artifacts returned by the custom copilot (optional)
    {
      "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  # <-- the UUID of the context
      "name": "<context name>",  # <-- the name of the context
      "description": "<context description>",  # <-- the description of the context
      "data": {
        "content": "<data>"  # <-- the data of the context
      },
      "metadata": {
        "<metadata key>": "<metadata value>",  # <-- the metadata of the context
        ...
      }
    },
    ...
  ]
}
```

We'll go over each of these fields in more detail below.

#### `messages`
This is the list of messages between the user and the copilot. This includes the
user's messages, the copilot's messages, function calls, and function call
results. Each message has a `role` and `content`.

The simplest example is when no function calling is involved, which simply
consists of an array of `human` and `ai` messages.

The OpenBB Workspace automatically appends all return `ai` messages (from your Copilot)
to the `messages` array of any follow-up request.

```python
# Only one human message
{
  "messages": [
    {
      "role": "human", 
      "content": "Hi there."
    }
  ],
  ...
}
```

```python
# Multiple messages
{
  "messages": [
    {
      "role": "human", 
      "content": "Hi there."
    },
    {
      "role": "ai", 
      "content": "Hi there, I'm a copilot. How are you?"
    },
    {
      "role": "human", 
      "content": "I'm fine, thank you. What is the weather in Tokyo?"
    }
  ],
  ...
}
```

Function calls to the OpenBB Workspace (such as when retrieving widget data), as well as the results of those function calls (containing the widget data), are also included in the `messages` array. For information on function calling, see the "Function Calling" section below.

#### `widgets`

This is an object containing a collection of widgets that added explicitly by the user as context (`primary`),
widgets in the currently-active dashboard (`secondary`), or widgets that are globally available if "global data" toggle is enabled (`extra`).

```python
{
  ...
  "widgets": {
    "primary": [
      {
        "origin": "OpenBB API",
        "widget_id": "stock_price_quote",
        "name": "Stock Price Quote Widget",
        "description": "Contains the current stock price of a ticker",
        "params": [
          {
            "name": "ticker",
            "type": "string",
            "description": "Stock ticker symbol",
            "current_value": "TSLA",
            "default_value": "AAPL"
          }
        ],
        "metadata": {
          "ticker": "TSLA"
        }
      }
    ],
    "secondary": [
      {
        "origin": "OpenBB API",
        "widget_id": "financial_ratios",
        "name": "Financial Ratios Widget",
        "description": "Displays key financial ratios for a company",
        "params": [
          {
            "name": "ticker",
            "type": "string",
            "description": "Stock ticker symbol",
            "current_value": "AAPL",
            "default_value": "AAPL"
          },
          {
            "name": "period",
            "type": "string",
            "description": "Time period for ratios",
            "current_value": "TTM",
            "default_value": "TTM"
          }
        ],
        "metadata": {
          "lastUpdated": 1737111708292,  
          "source": "Financial Modelling Prep"  
        }
      }
    ],
    "extra": []
  },
  ...
}
```

#### `context`

This is an optional array of artifact data that will be sent by the OpenBB Workspace
when artifacts have been returned by your custom copilot. 

The `context` field works as follows:

```python
{
  ...
  "context": [
    {
      "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  # <-- each context has a UUID
      "name": "chart_artifact_123a5",
      "description": "A chart showing the stock price of AAPL over the last 30 days",
      "data": {
        "content": "<data>"  # <-- the data of the context could either be a JSON string or plaintext (you must choose how to handle this in your copilot)
      },
      "metadata": {  # <-- additional metadata about the context
          "lastUpdated": 1737111708292,  
          "source": "Financial Modelling Prep"  
      }
    },
    {
      "uuid": "8b2e5f79-3a1d-4c9e-b6f8-1e7d2a9c0b3d",  # <-- there can be multiple contexts
      "name": "table_artifact_4534as",  
      "description": "A table showing the management team of AAPL",
      "data": {
        "content": "<data>"  # <-- the data of the context
      },
      "metadata": {
        ...
      }
    },
    ...
  ],
  ...
}
```

## Responding to the OpenBB Workspace

Your custom copilot must respond to the OpenBB Workspace's request using a variety of Server-Sent Events (SSEs).

The OpenBB Workspace can process the following SSEs:

- `copilotMessageChunk`: Used to return streamed copilot tokens (partial
responses) back to the OpenBB Workspace These responses can be streamed as they are
generated.
- `copilotMessageArtifact`: Used to return an artifact to the OpenBB Workspace as part
of the Copilot's response. This allows your copilot to return tables, charts,
and long-form text excerpts that will be rendered by the OpenBB Workspace Often
interleaved the `copilotMessageChunk` SSEs.
- `copilotCitationCollection`: Used to return a collection of citations back to the OpenBB Workspace This is useful for returning structured data, such as a list of news articles, research reports, or other sources that were used to generate the Copilot's response. This should be returned after the `copilotMessageChunk` SSEs have finished streaming.
- `copilotFunctionCall`: Used to request data (e.g., widget data) or perform a
specific function. This instructs the OpenBB Workspace to take further action on the
client's side. This is only necessary if you're planning on implementing
function calling in your custom copilot.
- `copilotStatusUpdate`: Used to send status updates or "reasoning steps" back to
the OpenBB Workspace These are user-friendly "updates" that are displayed in the
copilot window of the OpenBB Workspace, and are useful for informing the user about what your custom copilot is doing under-the-hood.

#### `copilotMessageChunk`
The message chunk SSE has the following format:

```
event: copilotMessageChunk
data: {"delta":"H"}  # <-- the `data` field must be a JSON object.
```
The `delta` must be a string, but can be of any length. We suggest streaming
back each chunk you receive from your LLM as soon as it's generated as a `delta`.

For example, if you wanted to stream back the message "Hi!", you would send the
following SSEs:

```
event: copilotMessageChunk
data: {"delta":"H"}

event: copilotMessageChunk
data: {"delta":"i"}

event: copilotMessageChunk
data: {"delta":"!"}
```

#### `copilotMessageArtifact`
The message artifact SSE has the following format:

```
event: copilotMessageArtifact
data: {"type": "<type>", "uuid": "<uuid>", "content": "<content>", "chart_params": <chart_params>}
```

An artifact can be a table, chart, or long-form text excerpt.
Let's go over each of these with examples:

A text artifact:

```
{
    "type": "text",
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "content": "This is a sample text content",
}
```

#### `copilotFunctionCall` (required for retrieving widget data -- see below)
The function call SSE has the following format:

```
event: copilotFunctionCall
data: {"function":"get_widget_data","input_arguments":{"data_sources":[{"origin":"OpenBB API","id":"company_news","input_args":{"symbol":"AAPL","channels":"All","start_date":"2021-01-16","end_date":"2025-01-16","topics":"","limit":50}}]},"copilot_function_call_arguments":{"data_sources":[{"origin":"OpenBB API","widget_id":"company_news"}]}}
```

Again, the `data` field must be a JSON object. The `function` field is the name
of the function to be called (currently only `get_widget_data` is supported),
and the `input_arguments` field is a dictionary of arguments to be passed to the
function. For the `get_widget_data` function, the only required argument is
`data_sources`, which is a list of objects specifying the origin, widget ID, and input arguments for each widget to retrieve data for.


## Function Calling

Function calling makes it possible for your copilot to request data from widgets. 

A list of all available widgets is sent to your copilot in the `widgets` field
of the request payload. They are categorized according to explicitly-added widgets (`primary`), widgets in the user's currently-active dashboard (`secondary`), and widgets that are globally available if the "global data" toggle is enabled (`extra`).

To retrieve the data from a widget, your copilot should respond with a
`copilotFunctionCall` event, specifying the widget origin, widget ID, and input arguments:

```
event: copilotFunctionCall
data: {"function":"get_widget_data","input_arguments":{"data_sources":[{"origin":"OpenBB API","id":"company_news","input_args":{"symbol":"AAPL","channels":"All","start_date":"2021-01-16","end_date":"2025-01-16","topics":"","limit":50}}]},"copilot_function_call_arguments":{"data_sources":[{"origin":"OpenBB API","widget_id":"company_news"}]}}
```


After emitting a `copilotFunctionCall` event, you must close the connection and wait for a new query request from the OpenBB Workspace

When a `copilotFunctionCall` event is received, the OpenBB Workspace will retrieve
the data, and initiate a **new** query request. This new query request will
include the original function call, as well as the function call result in the
`messages` array.

```python
{
  ...
  "messages": [
    ...
    {
      "role": "ai",
      "content": "{\"function\":\"get_widget_data\",\"input_arguments\":{\"data_sources\":[{\"origin\":\"OpenBB API\",\"id\":\"company_news\",\"input_args\":{\"symbol\":\"AAPL\",\"channels\":\"All\",\"start_date\":\"2021-01-16\",\"end_date\":\"2025-01-16\",\"topics\":\"\",\"limit\":50}}]},\"copilot_function_call_arguments\":{\"data_sources\":[{\"origin\":\"OpenBB API\",\"widget_id\":\"company_news\"}]}}"
    },
    {
      "role": "tool", 
      "function": "get_widget_data",
      "input_arguments": {
        "data_sources": [
          {
            "origin": "OpenBB API",
            "id": "company_news",
            "input_args": {
              "symbol": "AAPL",
              "channels": "All", 
              "start_date": "2021-01-16",
              "end_date": "2025-01-16",
              "topics": "",
              "limit": 50
            }
          }
        ]
      },
      "copilot_function_call_arguments": {
        "data_sources": [
          {
            "origin": "OpenBB API",
            "widget_id": "company_news"
          }
        ]
      },
      "data": [  # <-- the data field is a list of objects, each containing the data for a widget (in order) that was requested in the `data_sources` field of the `copilotFunctionCall` event.
        {
          "content": "<data>"
        },
        ...
      ]
    }
  ]
}
```

Notice that:
- Both the function call and the function call result are included in the `messages` array. 
- The `content` field of the function call `ai` message is a verbatim string-encoded JSON object of the `data` field of the `copilotFunctionCall` event (this is a very useful mechanism for smuggling additional metadata related to the function call, if your copilot needs it).

Currently, the only function call supported by the OpenBB Workspace is `get_widget_data`, which retrieves data from a specific widget.

### Function call example

Your custom copilot receives the following request from the OpenBB Workspace:

```json
{
  "messages": [
    {
      "role": "human",
      "content": "What is the current stock price of AAPL?"
    }
  ],
  "widgets": {
    "primary": [
      {
        "origin": "openbb_api",
        "widget_id": "historical_stock_price",
        "name": "Historical Stock Price",
        "description": "Historical Stock Price",
        "params": [
          {
            "name": "symbol",
            "type": "string",
            "description": "Stock ticker symbol",
            "current_value": "AAPL",
            "default_value": "AAPL"
          }
        ],
        "metadata": {
          "symbol": "AAPL",
          "source": "Financial Modelling Prep",
          "lastUpdated": 1728994470324
        }
      }
    ],
    "secondary": [],
    "extra": []
  }
}
```

You then parse the response, format the messages to your LLM (including information on which widgets are available).  Let's assume
that your copilot determines that the user's query can be answered using the widget available, and generates a function call to retrieve the data.

Your copilot then responds with the following SSE and close the connection:

```
event: copilotFunctionCall
data: {"function":"get_widget_data","input_arguments":{"data_sources":[{"origin":"openbb_api","id":"historical_stock_price","input_args":{"symbol":"AAPL"}}]},"copilot_function_call_arguments":{"data_sources":[{"origin":"openbb_api","widget_id":"historical_stock_price"}]}}
```

The OpenBB Workspace will then execute the specified function, and make a new query request to your custom copilot:

```python
{
  "messages": [
    {
      "role": "human",
      "content": "What is the current stock price of AAPL?"
    },
    {
      "role": "ai",
      "content": "{\"function\":\"get_widget_data\",\"input_arguments\":{\"data_sources\":[{\"origin\":\"openbb_api\",\"id\":\"historical_stock_price\",\"input_args\":{\"symbol\":\"AAPL\"}}]},\"copilot_function_call_arguments\":{\"data_sources\":[{\"origin\":\"openbb_api\",\"widget_id\":\"historical_stock_price\"}]}}"
    },
    {
      "role": "tool",
      "function": "get_widget_data",
      "input_arguments": {
        "data_sources": [
          {
            "origin": "openbb_api",
            "id": "historical_stock_price",
            "input_args": {
              "symbol": "AAPL"
            }
          }
        ]
      },
      "copilot_function_call_arguments": {
        "data_sources": [
          {
            "origin": "openbb_api",
            "widget_id": "historical_stock_price"
          }
        ]
      },
      "data": [
        {
          "content": "[{\"date\":\"2024-10-15T00:00:00-04:00\",\"open\":233.61,\"high\":237.49,\"low\":232.37,\"close\":233.85,\"volume\":61901688,\"vwap\":234.33,\"adj_close\":233.85,\"change\":0.24,\"change_percent\":0.0010274},{\"date\":\"2024-10-14T00:00:00-04:00\",\"open\":228.7,\"high\":231.73,\"low\":228.6,\"close\":231.3,\"volume\":39882100,\"vwap\":230.0825,\"adj_close\":231.3,\"change\":2.6,\"change_percent\":0.0114},{\"date\":\"2024-10-11T00:00:00-04:00\",\"open\":229.3,\"high\":233.2,\"low\":228.9,\"close\":231.0,\"volume\":32581944,\"vwap\":231.0333,\"adj_close\":231.0,\"change\":1.7,\"change_percent\":0.0074}, ... ]"
        }
      ]
    }
  ],
  "widgets": {
    "primary": [
      {
        "origin": "OpenBB API",
        "widget_id": "historical_stock_price",
        "name": "Historical Stock Price",
        "description": "Historical Stock Price",
        "params": [
          {
            "name": "symbol",
            "type": "string", 
            "description": "Stock ticker symbol",
            "current_value": "AAPL",
            "default_value": "AAPL"
          }
        ],
        "metadata": {
          "lastUpdated": 1728994470324,
          "source": "Financial Modelling Prep"
        }
      }
    ],
    "secondary": [],
    "extra": []
  }
}
```


You then parse the response, process the data, and format the messages to your LLM. Let's assume that the LLM then generates a string of tokens to answer the user's query. These are then streamed back to the user using the `copilotMessageChunk` SSE:

```
event: copilotMessageChunk
data: {"delta":"The"}

event: copilotMessageChunk
data: {"delta":" current"}

event: copilotMessageChunk
data: {"delta":" stock"}

event: copilotMessageChunk
data: {"delta":" price"}

event: copilotMessageChunk
data: {"delta":" of"}

event: copilotMessageChunk
data: {"delta":" Apple"}

event: copilotMessageChunk
data: {"delta":" Inc."}

event: copilotMessageChunk
data: {"delta":" (AAPL)"}

event: copilotMessageChunk
data: {"delta":" is"}

event: copilotMessageChunk
data: {"delta":" $150.75."}
```


## Configuring your custom copilot for the OpenBB Workspace (`copilots.json`)

To integrate your custom copilot with the OpenBB Workspace, you need to configure and
serve a `copilots.json` file. This file defines how your custom copilot connects
with the frontend, including which features are supported by your custom
copilot, and where requests  should be sent.  

Here is an example copilots.json configuration:

```json
{
  "example_copilot": { // <-- the ID of your copilot
    "name": "Mistral Example Co. Copilot", // <-- the display name of your copilot
    "description": "AI-powered financial copilot that uses Mistral Large as its LLM.", // <-- a short description of your copilot
    "image": "<url>", // <-- a URL to an image icon for your copilot
    "endpoints": {
      "query": "<url>" # <-- the URL that the OpenBB Workspace will send requests to. For example, "http://localhost:7777/v1/query"
    },
    "hasStreaming": true,  // Deprecated: use features.streaming instead
    "hasDocuments": false,  // Deprecated: not applicable anymore
    "hasFunctionCalling": false,  // Deprecated: use features.widget-dashboard-select, widget-dashboard-search or widget-global-search instead
    "features": {
        "streaming": true, // <-- whether your copilot supports streaming responses via SSEs. This must always be true.
        "file-upload": false,  // <-- whether the copilot supports uploading files
        "widget-dashboard-select": false,  // <-- specifies if the copilot supports manually selected widgets. These will be sent in `widgets.primary` in the payload.
        "widget-dashboard-search": false,  // <-- specifies if the copilot supports sending dashboard widgets. These will be sent in `widgets.secondary` in the payload.
        "widget-global-search": false  // <-- specifies if the copilot supports searching through all available widgets These will be sent in `widgets.extra` in the payload.
    }    
  }
}
```

Your `copilots.json` file must be served at `<your-host>/copilots.json`, for example, `http://localhost:7777/copilots.json`.

# Simple Copilot with Local Function Calling

This is a simple copilot, powered by OpenAI, that can perform question answering
and internal function calling (i.e. function calling that is executed within the backend of
the custom copilot itself).

It does not support retrieving data from the OpenBB Workspace.

For this particular local function calling example, we will implement a local function that fetches random
stout beers from the [Sample Beer API](https://sampleapis.com/api-list/beers).

## Architecture

```sh
┌─────────────────────┐                ┌───────────────────────────────────────────────────┐              ┌───────────────┐
│                     │                │                                                   │              │               │
│                     │                │               Simple Copilot                      │              │               │
│                     │                │                 (Backend)                         │              │               │
│                     │                │                                                   │              │               │
│   OpenBB Workspace  │ ───────────>   │  ┌─────────────┐        ┌─────────────────┐       │              │  External API │
│      (Frontend)     │     HTTP       │  │             │        │                 │       │              │  (Beer API)   │
│                     │    Request     │  │  LLM        │ ─────> │ Internal        │ ──────────────────>  │               │
│                     │                │  │  Processing │        │ Function Call   │       │              │               │
│                     │                │  │             │ <───── │ Execution       │ <─────────────────   │               │
│                     │   <───────────-│  │             │        │                 │       │              │               │
│                     │      SSE       │  └─────────────┘        └─────────────────┘       │              │               │
│                     │                │                                                   │              │               │
└─────────────────────┘                └───────────────────────────────────────────────────┘              └───────────────┘
```

The architecture consists of two main components:

1. **OpenBB Workspace (Frontend)**: The user interface where queries are entered
2. **Simple Copilot (Backend)**: Powered by OpenAI, handles the processing of queries, executing internal function calls, and returns answers

The frontend communicates with the backend via HTTP requests to the `/query`
endpoint as defined in the copilot.json schema.

## Overview

This implementation utilizes a FastAPI application to serve as the backend for
the copilot. The core functionality is powered by `magentic`, a robust, minimal
framework for working with Large Language Models (LLMs).

You're not limited to our setup! If you have preferences for different APIs or
LLM frameworks, feel free to adapt this implementation. The key is to adhere to
the schema defined by the `/query` endpoint and the specifications in
`copilot.json`.

## Getting started

Here's how to get your copilot up and running:

### Prerequisites

Ensure you have poetry, a tool for dependency management and packaging in
Python, as well as your OpenAI API key.

### Installation and Running

1. Clone this repository to your local machine.

2. Set the OpenAI API key as an environment variable in your .bashrc or .zshrc file:

    ``` sh
    # in .zshrc or .bashrc
    export OPENAI_API_KEY=<your-api-key>
    ```

3. Install the necessary dependencies:

``` sh
poetry install --no-root
```

4.Start the API server:

``` sh
cd 02-simple-copilot-local-function-calling
poetry run uvicorn simple_copilot_fc.main:app --port 7777 --reload
```

This command runs the FastAPI application, making it accessible on your network.

### Testing the Copilot

The example copilot has a small, basic test suite to ensure it's
working correctly. As you develop your copilot, you are highly encouraged to
expand these tests.

You can run the tests with:

```sh
pytest tests
```

### Accessing the Documentation

Once the API server is running, you can view the documentation and interact with
the API by visiting: http://localhost:7777/docs

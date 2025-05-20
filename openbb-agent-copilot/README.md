# OpenBB Agent Copilot

This example provides a copilot that leverages the OpenBB Platform to retrieve financial data.

## Overview

This implementation utilizes a FastAPI application to serve as the backend for
the copilot.

## Getting started

Here's how to get your copilot up and running:

### Prerequisites

Ensure you have poetry, a tool for dependency management and packaging in
Python, installed as well as your OpenAI API key.

### Installation and Running

1. Clone this repository to your local machine.
2. Set the OpenAI API key as an environment variable in your .bashrc or .zshrc file:

``` sh
# in .zshrc or .bashrc
export OPENAI_API_KEY=<your-api-key>
export OPENBB_PAT=<your-openbb-pat>
```

The latter can be found here: https://my.openbb.co/app/platform/pat

3. Install the necessary dependencies:

``` sh
poetry install --no-root
```

4.Start the API server:

``` sh
poetry run uvicorn openbb_agent_copilot.main:app --port 7777 --reload
```

This command runs the FastAPI application, making it accessible on your network.

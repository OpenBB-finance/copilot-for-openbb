# Perplexity AI Copilot

This example provides a basic copilot that utilizes the Perplexity AI API for natural language processing and generation.

## Overview

This implementation uses a FastAPI application as the backend for the copilot. The core functionality is powered by the Perplexity AI API, which offers advanced language models and various capabilities.

You can adapt this implementation to suit your needs or preferences. The key is to adhere to the schema defined by the `/query` endpoint and the specifications in `copilot.json`.

This repository serves as a starting point for you to experiment, modify, and extend. You can build copilots with various capabilities, leveraging Perplexity AI's features such as different model options, chat completions, and more.

## Getting Started

Follow these steps to set up and run your Perplexity AI-powered copilot:

### Prerequisites

- Python 3.7 or higher
- Poetry (for dependency management)
- A Perplexity AI API key (sign up at https://www.perplexity.ai/ if you don't have one)


### Installation and Running

1. Clone this repository to your local machine.
2. Set the Perplexity API key as an environment variable in your .bashrc or .zshrc file:

``` sh
# in .zshrc or .bashrc
export PERPLEXITY_API_KEY=pplx=<your-api-key>
```

3. Install the necessary dependencies:

``` sh
poetry install --no-root
```

4.Start the API server:

``` sh
poetry run uvicorn perplexity_copilot.main:app --port 7777 --reload
```

This command runs the FastAPI application, making it accessible on your network.

### Testing the Copilot

The example copilot has a small, basic test suite to ensure it's
working correctly. As you develop your copilot, you are highly encouraged to
expand these tests.

You can run the tests with:

``` sh
pytest tests
```

### Accessing the Documentation

Once the API server is running, you can view the documentation and interact with the API by visiting: http://localhost:7777/docs
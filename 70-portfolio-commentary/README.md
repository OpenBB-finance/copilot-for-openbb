# Portfolio Commentary Copilot

This is a FastAPI-based copilot service that provides portfolio commentary and analysis capabilities. The service utilizes DeepSeek for reasoning and Perplexity for web search based on user requests. It is designed to work with OpenBB Workspace and can be deployed using Docker or run locally.

## Architecture

```sh
┌─────────────────────┐                ┌─────────────────────┐
│                     │                │                     │
│   OpenBB Workspace  │ ───────────>   │   Portfolio         │
│      (Frontend)     │     HTTP       │   Commentary        │
│                     │    Request     │   Copilot           │
│                     │                │   (Backend)         │
│                     │   <───────────-│                     │
│                     │      SSE       │                     │
└─────────────────────┘                └─────────────────────┘
```

The architecture consists of two main components:

1. **OpenBB Workspace (Frontend)**: The user interface where queries are entered
2. **Portfolio Commentary Copilot (Backend)**: A FastAPI service that processes queries and returns analysis

## Project Structure

```
portfolio-commentary/
├── portfolio_commentary/
│   ├── main.py          # Main FastAPI application
│   ├── functions.py     # Core functionality
│   ├── prompts.py       # LLM prompts
│   └── agents.json      # Agent configuration
├── common/              # Shared utilities
├── pyproject.toml       # Project dependencies
├── Dockerfile           # Docker configuration
└── fly.toml             # Fly.io deployment config
```

## Getting Started

Here's how to get your copilot up and running:

### Prerequisites

- Python 3.10 or higher
- Poetry for dependency management
- Docker (optional, for containerized deployment)
- Your OpenRouter API key

### Installation and Running

1. Clone this repository to your local machine.

2. Create and activate a virtual environment:
```sh
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies using Poetry:
```sh
poetry install --no-root
```

4. Set up environment variables:
Create a `.env` file in the root directory with the following content:
```
OPENROUTER_API_KEY=<your-api-key>
```

5. Run the development server:
```sh
cd 70-portfolio-commentary
poetry run uvicorn portfolio_commentary.main:app --reload --port 7777
```

### Docker Deployment

Bring the /common folder to the root, for the docker image.

1. Build the Docker image:
```sh
docker build -t portfolio-commentary .
```

2. Run the container:
```sh
docker run -p 7777:7777 --env-file .env portfolio-commentary
```

### Fly.io Deployment

The project includes a `fly.toml` configuration for deployment to Fly.io. To deploy:

0. Go into agents.json and change `"query": "https://portfolio-commentary.fly.dev/v1/query"` to `"query": "https://<YOUR-FLY-IO-APP-NAME>.fly.dev/v1/query"`. This will make sure that OpenBB workspace utilizes this endpoint.
1. Install the Fly CLI
2. Run `fly launch` to create a new app
3. Set your environment variables using `fly secrets set OPENROUTER_API_KEY="your-api-key"`
4. Deploy with `fly deploy`

### Accessing the Documentation

Once the API server is running, you can view the documentation and interact with
the API by visiting: http://localhost:7777/docs

## License

This project is licensed under the MIT License - see the LICENSE file for details.

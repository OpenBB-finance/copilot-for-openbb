# Build stage for the common package
FROM python:3.10-slim as common-builder
WORKDIR /build
COPY ./common /build/common/

# Final stage
FROM python:3.10-slim
WORKDIR /app

# Install required packages and poetry
RUN pip install --no-cache-dir fastapi uvicorn[standard] python-dotenv httpx sse-starlette pdfplumber "magentic[litellm]" poetry

# Copy the portfolio commentary application first
COPY ./portfolio_commentary /app/portfolio_commentary
COPY ../pyproject.toml ./poetry.lock* /app/
COPY .env /app/.env

# Copy the common package - place it where Poetry expects it
COPY --from=common-builder /build/common /common

# Install dependencies using poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Expose the port the app will run on
EXPOSE 7777

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

# Command to run the application
CMD ["uvicorn", "portfolio_commentary.main:app", "--host", "0.0.0.0", "--port", "7777", "--reload"]
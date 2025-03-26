import re
import json
from ast import literal_eval
from pathlib import Path
from fastapi.testclient import TestClient
from perplexity_copilot.main import app
import pytest
from unittest.mock import patch, MagicMock

test_client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_sse_starlette_appstatus_event():
    """
    Fixture that resets the appstatus event in the sse_starlette app.
    Should be used on any test that uses sse_starlette to stream events.
    """
    # See https://github.com/sysid/sse-starlette/issues/59
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None


def _capture_stream_response(event_stream: str):
    captured_stream = ""
    lines = event_stream.split("\n")
    event_type = ""
    for line in lines:
        if line.startswith("event:"):
            event_type = line.split("event:")[1].strip()
        elif event_type == "copilotMessageChunk" and line.startswith("data:"):
            data_payload = line.split("data:")[1].strip()
            data_dict_ = literal_eval(data_payload)
            captured_stream += data_dict_["delta"]
    return captured_stream


@patch('perplexity_copilot.main.client.chat.completions.create')
def test_query(mock_create):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(delta=MagicMock(content="The answer is 2."))]
    mock_create.return_value = [mock_response]

    test_payload = {"messages": [{"role": "human", "content": "what is 1 + 1?"}]}
    response = test_client.post("/v1/query", json=test_payload)
    captured_stream = _capture_stream_response(response.text)
    assert response.status_code == 200
    assert "2" in captured_stream


@patch('perplexity_copilot.main.client.chat.completions.create')
def test_query_conversation(mock_create):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(delta=MagicMock(content="The answer is 4."))]
    mock_create.return_value = [mock_response]

    test_payload = {
        "messages": [
            {"role": "human", "content": "what is 1 + 1?"},
            {"role": "ai", "content": "2"},
            {"role": "human", "content": "what is 2 + 2?"},
        ]
    }
    response = test_client.post("/v1/query", json=test_payload)
    captured_stream = _capture_stream_response(response.text)
    assert response.status_code == 200
    assert "4" in captured_stream


@patch('perplexity_copilot.main.client.chat.completions.create')
def test_query_with_context(mock_create):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(delta=MagicMock(content="Your favorite food is pizza."))]
    mock_create.return_value = [mock_response]

    test_payload = {
        "messages": [
            {"role": "human", "content": "What is my favourite food?"},
        ],
        "context": [
            {
                "uuid": "ff6368ec-a397-4baf-9f5a-fecd9fd797a3",
                "name": "favourite_food",
                "description": "The user's favourite food",
                "content": "pizza",
            }
        ],
    }
    response = test_client.post("/v1/query", json=test_payload)
    captured_stream = _capture_stream_response(response.text)
    assert response.status_code == 200
    assert "pizza" in captured_stream.lower()


def test_query_no_messages():
    test_payload = {
        "messages": [],
    }
    response = test_client.post("/v1/query", json=test_payload)
    assert response.status_code == 422  # Unprocessable Entity
    assert "messages" in response.text
    assert "empty" in response.text.lower()


def test_get_copilot_description():
    response = test_client.get("/copilots.json")
    assert response.status_code == 200
    content = json.loads(response.content)
    assert "llama_copilot" in content
    assert "name" in content["llama_copilot"]
    assert "description" in content["llama_copilot"]
    assert "endpoints" in content["llama_copilot"]
    assert "query" in content["llama_copilot"]["endpoints"]

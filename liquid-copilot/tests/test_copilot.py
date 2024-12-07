import re
import json
from ast import literal_eval
from pathlib import Path
from fastapi.testclient import TestClient
from liquid_copilot.main import app
import pytest
from unittest.mock import patch, AsyncMock

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
            data_dict_ = json.loads(data_payload)
            captured_stream += data_dict_["delta"]
    return captured_stream


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_query(mock_post):
    mock_response = AsyncMock()
    mock_response.aiter_lines.return_value = [
        'data: {"choices":[{"delta":{"content":"The answer is 2."}}]}',
        'data: [DONE]'
    ]
    mock_post.return_value = mock_response

    test_payload = {"messages": [{"role": "user", "content": "what is 1 + 1?"}]}
    response = await test_client.post("/v1/query", json=test_payload)
    captured_stream = _capture_stream_response(response.text)
    assert response.status_code == 200
    assert "The answer is 2." in captured_stream


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_query_conversation(mock_post):
    mock_response = AsyncMock()
    mock_response.aiter_lines.return_value = [
        'data: {"choices":[{"delta":{"content":"The answer is 4."}}]}',
        'data: [DONE]'
    ]
    mock_post.return_value = mock_response

    test_payload = {
        "messages": [
            {"role": "user", "content": "what is 1 + 1?"},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "what is 2 + 2?"},
        ]
    }
    response = await test_client.post("/v1/query", json=test_payload)
    captured_stream = _capture_stream_response(response.text)
    assert response.status_code == 200
    assert "The answer is 4." in captured_stream


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_query_with_context(mock_post):
    mock_response = AsyncMock()
    mock_response.aiter_lines.return_value = [
        'data: {"choices":[{"delta":{"content":"Your favorite food is pizza."}}]}',
        'data: [DONE]'
    ]
    mock_post.return_value = mock_response

    test_payload = {
        "messages": [
            {"role": "user", "content": "What is my favourite food?"},
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
    response = await test_client.post("/v1/query", json=test_payload)
    captured_stream = _capture_stream_response(response.text)
    assert response.status_code == 200
    assert "Your favorite food is pizza." in captured_stream


@pytest.mark.asyncio
async def test_query_no_messages():
    test_payload = {
        "messages": [],
    }
    response = await test_client.post("/v1/query", json=test_payload)
    assert response.status_code == 422  # Unprocessable Entity
    assert "messages" in response.text
    assert "empty" in response.text.lower()


def test_get_copilot_description():
    response = test_client.get("/copilots.json")
    assert response.status_code == 200
    content = json.loads(response.content)
    assert "liquid_copilot" in content
    assert "name" in content["liquid_copilot"]
    assert "description" in content["liquid_copilot"]
    assert "endpoints" in content["liquid_copilot"]
    assert "query" in content["liquid_copilot"]["endpoints"]

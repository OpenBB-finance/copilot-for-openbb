import json
from fastapi.testclient import TestClient
from simple_copilot_rs.main import app
import pytest
from pathlib import Path
from common.testing import CopilotResponse, capture_stream_response
from unittest.mock import MagicMock, patch

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


def test_query():
    test_payload_path = (
        Path(__file__).parent.parent.parent / "test_payloads" / "single_message.json"
    )
    test_payload = json.load(open(test_payload_path))

    response = test_client.post("/v1/query", json=test_payload)
    event_name, captured_stream = capture_stream_response(response.text)
    assert response.status_code == 200
    assert event_name == "copilotMessageChunk"
    assert "2" in captured_stream


def test_query_conversation():
    test_payload_path = (
        Path(__file__).parent.parent.parent / "test_payloads" / "multiple_messages.json"
    )
    test_payload = json.load(open(test_payload_path))

    response = test_client.post("/v1/query", json=test_payload)
    event_name, captured_stream = capture_stream_response(response.text)
    assert response.status_code == 200
    assert event_name == "copilotMessageChunk"
    assert "4" in captured_stream


def test_query_no_messages():
    test_payload = {
        "messages": [],
    }
    response = test_client.post("/v1/query", json=test_payload)
    "messages list cannot be empty" in response.text


def test_query_local_function_call():
    test_payload = {
        "messages": [
            {
                "role": "human",
                "content": "Fetch and describe a random colour palette.",
            }
        ]
    }

    mock_json_response = [
        {
            "id": 12345,
            "title": "Mock Palette",
            "colors": ["FF0000", "00FF00", "0000FF"],  # RGB colors without #
            "url": "https://www.colourlovers.com/palette/12345/Mock_Palette",
            "imageUrl": "https://www.colourlovers.com/paletteImg/12345/Mock_Palette.png",
        }
    ]

    mock_response = MagicMock(name="mock_response")
    mock_response.status_code = 200
    mock_response.json.return_value = mock_json_response

    with patch("simple_copilot_rs.functions.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )
        response = test_client.post("/v1/query", json=test_payload)
        assert response.status_code == 200

        copilot_response = CopilotResponse(response.text)
        (
            copilot_response.starts("copilotStatusUpdate")
            .with_("Fetching palettes...")
            .then("copilotStatusUpdate")
            .with_("Palettes fetched successfully.")
            .then("copilotMessage")
            .with_("Mock")
            .with_("FF0000")
            .with_("00FF00")
            .with_("0000FF")
            .with_("colourlovers.com")
        )

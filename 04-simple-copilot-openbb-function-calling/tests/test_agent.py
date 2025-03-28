import json
from fastapi.testclient import TestClient
from simple_copilot_rfc.main import app
import pytest
from pathlib import Path
from common.testing import CopilotResponse, capture_stream_response

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


def test_query_returns_remote_function_call():
    test_payload_path = (
        Path(__file__).parent.parent.parent
        / "test_payloads"
        / "message_with_primary_widget.json"
    )
    test_payload = json.load(open(test_payload_path))

    response = test_client.post("/v1/query", json=test_payload)
    assert response.status_code == 200

    (
        CopilotResponse(response.text)
        .starts("copilotStatusUpdate")
        .with_("Retrieving data for widget: Company News...")
        .then("copilotFunctionCall")
        .with_({"function": "get_widget_data"})
        .with_(
            {
                "input_arguments": {
                    "data_sources": [
                        {
                            "widget_uuid": "123e4567-e89b-12d3-a456-426614174000",
                            "origin": "openbb",
                            "id": "company_news",
                            "input_args": {"ticker": "AAPL"},
                        }
                    ]
                }
            }
        )
        .with_(
            {
                "extra_state": {
                    "copilot_function_call_arguments": {
                        "widget_uuid": "123e4567-e89b-12d3-a456-426614174000"
                    },
                    "_locally_bound_function": "_get_widget_data",
                }
            }
        )
    )


def test_query_completes_remote_function_call():
    test_payload_path = (
        Path(__file__).parent.parent.parent
        / "test_payloads"
        / "message_with_primary_widget_and_tool_call.json"
    )
    test_payload = json.load(open(test_payload_path))

    response = test_client.post("/v1/query", json=test_payload)
    assert response.status_code == 200
    copilot_response = CopilotResponse(response.text)
    (
        copilot_response.starts("copilotMessage")
        .with_("Positive")
        .with_("Negative")
        .with_("Neutral")
        .with_("Apple")
    )

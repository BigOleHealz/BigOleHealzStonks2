# Standard imports
import pytest
from typing import Any, Dict, Generator
from pytest_mock import MockerFixture

# Third-party imports
from fastapi import Request
from fastapi.testclient import TestClient
import requests
from requests import Response

# Local imports
from main import app
from services.jira.jira_manager import add_comment_to_jira, extract_issue_details
from config import (
    GITHUB_TEST_REPO_OWNER,
    GITHUB_TEST_REPO_NAME,
    JIRA_BASE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN
)

# Use FastAPI's TestClient to test endpoints
client = TestClient(app)

# Test data
test_project_key: str = "SCRUM"
test_jira_issue_summary: str = "Test Issue"
test_jira_issue_description: str = "This is a test issue description."
test_github_issue_link: str = f"https://github.com/{GITHUB_TEST_REPO_OWNER}/{GITHUB_TEST_REPO_NAME}/issues/1"

@pytest.fixture(scope="module")
def test_create_jira_issue() -> Generator[Dict[str, Any], None, None]:
    """Fixture to create a JIRA issue, provide its details, and delete it after tests."""
    # Create the JIRA issue
    url = f"{JIRA_BASE_URL}/rest/api/2/issue"
    payload = {
        "fields": {
            "project": {"key": test_project_key},
            "summary": test_jira_issue_summary,
            "description": test_jira_issue_description,
            "issuetype": {"name": "Task"}
        }
    }

    response: Response = requests.post(
        url,
        json=payload,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 201, f"Failed to create JIRA issue: {response.text}"
    print("JIRA issue created successfully")

    response_json = response.json()
    jira_issue = {
        "id": int(response_json["id"]),
        "key": response_json["key"],
        "link": response_json["self"]
    }

    # Yield the created issue to the tests
    yield jira_issue

    # Teardown logic: Delete the JIRA issue after all tests are done
    delete_url = f"{JIRA_BASE_URL}/rest/api/2/issue/{jira_issue['key']}"
    delete_response = requests.delete(
        delete_url,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
    )

    if delete_response.status_code == 204:
        print(f"JIRA issue {jira_issue['key']} deleted successfully.")
    else:
        print(f"Failed to delete JIRA issue {jira_issue['key']}: {delete_response.text}")

@pytest.fixture
def mock_jira_payload(test_create_jira_issue: Dict[str, Any]) -> Dict[str, Any]:
    """Fixture to provide a mock JIRA webhook payload."""
    return {
        "issue": {
            "key": test_create_jira_issue["key"],
            "fields": {
                "summary": test_jira_issue_summary,
                "description": test_jira_issue_description,
            }
        }
    }

@pytest.mark.asyncio
async def test_extract_issue_details_with_dict(
    mock_jira_payload: Dict[str, Any]
) -> None:
    """Test the extract_issue_details function with a dictionary input."""
    issue_details = extract_issue_details(payload=mock_jira_payload)
    assert issue_details["key"] == mock_jira_payload["issue"]["key"]
    assert issue_details["title"] == test_jira_issue_summary
    assert issue_details["description"] == test_jira_issue_description

@pytest.mark.asyncio
async def test_extract_issue_details_with_request(
    mock_jira_payload: Dict[str, Any]
) -> None:
    """Test the extract_issue_details function with a FastAPI Request object."""

    def mock_json() -> Dict[str, Any]:
        return mock_jira_payload

    mock_request = Request(scope={"type": "http"})
    mock_request.json = mock_json  # Mock the json method

    issue_details = extract_issue_details(payload=mock_request)
    assert issue_details["key"] == mock_jira_payload["issue"]["key"]
    assert issue_details["title"] == test_jira_issue_summary
    assert issue_details["description"] == test_jira_issue_description

def test_jira_webhook_endpoint(mock_jira_payload: Dict[str, Any], mocker: MockerFixture) -> None:
    """Test the /jira-webhook endpoint."""
    response = client.post("/jira-webhook", json=mock_jira_payload)
    assert response.status_code == 200
    assert response.json() == {"message": "Jira webhook processed successfully"}


def test_add_comment_to_jira_success(
    test_create_jira_issue: Dict[str, Any],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test successful comment addition to JIRA."""
    # Use mocker to patch requests.post
    mock_requests_post = mocker.patch("services.jira.jira_manager.requests.post")

    # Configure the mock response
    mock_response = mocker.Mock()
    mock_response.status_code = 201
    mock_requests_post.return_value = mock_response

    # Call the function
    add_comment_to_jira(test_create_jira_issue["key"], test_github_issue_link)

    # Verify that requests.post was called with the correct parameters
    mock_requests_post.assert_called_once_with(
        f"{JIRA_BASE_URL}/rest/api/2/issue/{test_create_jira_issue['key']}/comment",
        json={"body": f"GitHub issue created: [View on GitHub|{test_github_issue_link}]"},
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Content-Type": "application/json"}
    )

    # Capture and verify the output
    captured = capsys.readouterr()
    assert f"Comment added to JIRA issue {test_create_jira_issue['key']}" in captured.out

def test_add_comment_to_jira_failure(
    test_create_jira_issue: Dict[str, Any],
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test failed comment addition to JIRA."""
    # Use mocker to patch requests.post
    mock_requests_post = mocker.patch("services.jira.jira_manager.requests.post")

    # Configure the mock response to simulate a failure
    mock_response = mocker.Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_requests_post.return_value = mock_response

    # Call the function
    add_comment_to_jira(test_create_jira_issue["key"], test_github_issue_link)

    # Capture and verify the output
    captured = capsys.readouterr()
    assert "Failed to add comment to JIRA: Bad Request" in captured.out

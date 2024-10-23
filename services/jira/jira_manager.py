# Standard imports
from typing import Union

# Third-party imports
from fastapi import Request
import requests

# Local imports
from config import (
    JIRA_BASE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
)
from utils.handle_exceptions import handle_exceptions

# Helper Functions
@handle_exceptions()
def extract_issue_details(payload: Union[dict, Request]) -> dict:
    """Extract relevant issue details from the JIRA webhook payload."""
    if isinstance(payload, Request):
        payload = payload.json()
    issue = payload["issue"]
    return {
        "key": issue["key"],
        "title": issue["fields"]["summary"],
        "description": issue["fields"]["description"]
    }

@handle_exceptions(default_return_value=None, raise_on_error=False)
def add_comment_to_jira(issue_key: str, github_issue_link: str):
    """Add a comment with the GitHub issue link to the JIRA issue."""
    jira_comment_url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    comment_payload = {
        "body": f"GitHub issue created: [View on GitHub|{github_issue_link}]"
    }
    JIRA_AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
    response: requests.Response = requests.post(
      jira_comment_url,
      json=comment_payload,
      auth=JIRA_AUTH,
      headers={"Content-Type": "application/json"}
    )

    if response.status_code == 201:
        print(f"Comment added to JIRA issue {issue_key}")
    else:
        print(f"Failed to add comment to JIRA: {response.text}")

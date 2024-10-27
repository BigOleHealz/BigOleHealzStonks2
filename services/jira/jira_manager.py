# Standard imports
import hashlib
import hmac
from typing import Any, cast, Dict, Union

# Third-party imports
from fastapi import Request
import requests

# Local imports
from config import (
    JIRA_BASE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    PRODUCT_ID,
)
from services.github.github_types import (
    GitHubEventPayload,
    GitHubLabeledPayload,
    IssueInfo,
    LabelInfo,
    RepositoryInfo,
    OrganizationInfo,
    UserInfo,
    InstallationMiniInfo,
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

@handle_exceptions(raise_on_error=True)
async def verify_webhook_signature(request: Request, secret: str) -> None:
    """Verify the webhook signature for security"""
    signature: str | None = request.headers.get("X-Hub-Signature")
    if signature is None:
        raise ValueError("Missing webhook signature")
    body: bytes = await request.body()

    # Compare the computed signature with the one in the headers
    hmac_key: bytes = secret.encode()
    hmac_signature: str = hmac.new(
        key=hmac_key, msg=body, digestmod=hashlib.sha256
    ).hexdigest()
    expected_signature: str = "sha256=" + hmac_signature
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid webhook signature")


def map_jira_to_github_event_payload(jira_payload: Dict[str, Any]) -> GitHubEventPayload:
    """Map a JIRA webhook payload to a GitHubEventPayload structure."""

    issue_fields = jira_payload["issue"]["fields"]
    reporter = issue_fields["reporter"]

    # Build the GitHubLabeledPayload type
    github_payload: GitHubLabeledPayload = GitHubLabeledPayload(
        action=jira_payload["issue_event_type_name"],
        issue=IssueInfo(
            url=jira_payload["issue"]["self"],
            repository_url="",  # No direct equivalent in JIRA
            labels_url="",  # Optional, map if needed
            comments_url="",  # Optional, map if needed
            events_url="",  # Optional, map if needed
            html_url=f"https://bigolehealz.atlassian.net/browse/{jira_payload['issue']['key']}",
            id=int(jira_payload["issue"]["id"]),
            node_id=jira_payload["issue"]["key"],
            number=int(jira_payload["issue"]["id"]),
            title=issue_fields["summary"],
            user=map_user_info(reporter),
            labels=[],  # Optional: Extract JIRA labels if needed
            state="open",  # Default to 'open'
            locked=False,  # No lock status in JIRA
            assignee=map_user_info(issue_fields["assignee"]) if issue_fields.get("assignee") else None,
            assignees=[],  # Can be populated if needed
            milestone=None,
            comments=0,  # Not available in JIRA
            created_at=issue_fields["created"],
            updated_at=issue_fields["updated"],
            closed_at=None,  # No equivalent in JIRA
            author_association="reporter",
            active_lock_reason=None,
            body=issue_fields.get("description", ""),
            reactions={},
            timeline_url="",  # Optional, leave empty
            performed_via_github_app=None,
            state_reason=None,
        ),
        label=LabelInfo(
            id=0,  # Placeholder, JIRA doesn't provide label IDs
            node_id="",  # Placeholder
            url="",  # Placeholder
            name=PRODUCT_ID,
            color="",  # No color in JIRA
            default=False,
            description=issue_fields["issuetype"]["description"],
        ),
        repository=RepositoryInfo(
            id=int(issue_fields["project"]["id"]),
            node_id=issue_fields["project"]["key"],
            name=issue_fields["project"]["name"],
            full_name=issue_fields["project"]["name"],
            private=False,
            owner=map_user_info(reporter),
            html_url=issue_fields["project"]["self"],
            description=issue_fields["project"].get("description", ""),
            fork=False,
            url=issue_fields["project"]["self"],
            created_at="",
            updated_at="",
            pushed_at="",
            size=0,
            stargazers_count=0,
            watchers_count=0,
            language=None,
            has_issues=True,
            has_projects=True,
            has_downloads=True,
            has_wiki=True,
            has_pages=False,
            forks_count=0,
            archived=False,
            disabled=False,
            open_issues_count=0,
            allow_forking=True,
            is_template=False,
            web_commit_signoff_required=False,
            topics=[],
            visibility="public",
            forks=0,
            open_issues=0,
            watchers=0,
            default_branch="main",
            custom_properties={},
        ),
        organization=OrganizationInfo(
            login="JIRA Project",
            id=int(issue_fields["project"]["id"]),
            node_id=issue_fields["project"]["key"],
            url=issue_fields["project"]["self"],
            repos_url="",
            events_url="",
            hooks_url="",
            issues_url="",
            members_url="",
            public_members_url="",
            avatar_url=issue_fields["project"]["avatarUrls"]["48x48"],
            description=issue_fields["project"].get("description", ""),
        ),
        sender=map_user_info(reporter),
        installation=InstallationMiniInfo(id=56165848, node_id=issue_fields["project"]["key"]),  # Not applicable for JIRA
    )

    # Return as GitHubEventPayload type
    return cast(GitHubEventPayload, github_payload)

def map_user_info(data: Dict[str, Any]) -> UserInfo:
    """Map JIRA user to UserInfo."""
    return UserInfo(
        login=data["displayName"],
        id=data["accountId"],
        node_id=data["accountId"],
        avatar_url=data["avatarUrls"]["48x48"],
        gravatar_id="",
        url=data["self"],
        html_url=data["self"],
        followers_url="",
        following_url="",
        gists_url="",
        starred_url="",
        subscriptions_url="",
        organizations_url="",
        repos_url="",
        events_url="",
        received_events_url="",
        type="User",
        site_admin=False,
    )

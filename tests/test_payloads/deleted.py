import pytest
import json
from main import app

with open("payloads/mock_deletion_event.json") as f:
    deletion_payload = json.load(f)

def test_handle_deletion_event():
    response = app.test_client().post('/webhook', json=deletion_payload)
    assert response.status_code == 200
    assert response.json == {"status": "installation deleted"}
from services.github.github_types import GitHubEventPayload


deleted_payload: GitHubEventPayload = {
    "action": "deleted",
    "installation": {
        "id": -1,
        "account": {
            "login": "installation-test",
            "id": -1,
            "node_id": "O_kgDOB9UpXA",
            "avatar_url": "https://avatars.githubusercontent.com/u/-1?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/installation-test",
            "html_url": "https://github.com/installation-test",
            "followers_url": "https://api.github.com/users/installation-test/followers",
            "following_url": "https://api.github.com/users/installation-test/following{/other_user}",
            "gists_url": "https://api.github.com/users/installation-test/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/installation-test/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/installation-test/subscriptions",
            "organizations_url": "https://api.github.com/users/installation-test/orgs",
            "repos_url": "https://api.github.com/users/installation-test/repos",
            "events_url": "https://api.github.com/users/installation-test/events{/privacy}",
            "received_events_url": "https://api.github.com/users/installation-test/received_events",
            "type": "Organization",
            "site_admin": False,
        },
        "repository_selection": "selected",
        "access_tokens_url": "https://api.github.com/app/installations/-1/access_tokens",
        "repositories_url": "https://api.github.com/installation/repositories",
        "html_url": "https://github.com/organizations/installation-test/settings/installations/-1",
        "app_id": -1,
        "app_slug": "issue-to-pull-request",
        "target_id": -1,
        "target_type": "Organization",
        "permissions": {
            "issues": "write",
            "contents": "write",
            "metadata": "read",
            "workflows": "write",
            "pull_requests": "write",
        },
        "events": [
            "commit_comment",
            "issues",
            "issue_comment",
            "label",
            "public",
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
            "pull_request_review_thread",
        ],
        "created_at": "2024-03-21T19:09:38.000-07:00",
        "updated_at": "2024-03-21T19:09:38.000-07:00",
        "single_file_name": None,
        "has_multiple_single_files": False,
        "single_file_paths": [],
        "suspended_by": None,
        "suspended_at": None,
    },
    "repositories": [
        {
            "id": -1,
            "node_id": "R_kgDOJZc8Zg",
            "name": "main",
            "full_name": "installation-test/main",
            "private": True,
        }
    ],
    "sender": {
        "login": "username-test",
        "id": -1,
        "node_id": "MDQ6VXNlcjY2Njk5Mjkw",
        "avatar_url": "https://avatars.githubusercontent.com/u/-1?v=4",
        "gravatar_id": "",
        "url": "https://api.github.com/users/username-test",
        "html_url": "https://github.com/username-test",
        "followers_url": "https://api.github.com/users/username-test/followers",
        "following_url": "https://api.github.com/users/username-test/following{/other_user}",
        "gists_url": "https://api.github.com/users/username-test/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/username-test/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/username-test/subscriptions",
        "organizations_url": "https://api.github.com/users/username-test/orgs",
        "repos_url": "https://api.github.com/users/username-test/repos",
        "events_url": "https://api.github.com/users/username-test/events{/privacy}",
        "received_events_url": "https://api.github.com/users/username-test/received_events",
        "type": "User",
        "site_admin": False,
    },
}

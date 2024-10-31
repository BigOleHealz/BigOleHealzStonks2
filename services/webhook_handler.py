# Standard imports
from typing import cast
import re

# Local imports
from config import (
    PRODUCT_ID,
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    PR_BODY_STARTS_WITH,
    ISSUE_NUMBER_FORMAT,
)
from services.github.github_manager import (
    add_issue_templates,
    create_comment_on_issue_with_gitauto_button,
    get_installation_access_token,
    # turn_on_issue,
)
from services.github.github_types import (
    GitHubEventPayload,
    GitHubInstallationPayload,
)
from services.supabase import SupabaseManager
from services.gitauto_handler import handle_gitauto, handle_gitauto_from_jira
from services.jira.jira_manager import map_jira_to_github_event_payload
from utils.handle_exceptions import handle_exceptions

# Initialize managers
supabase_manager = SupabaseManager(url=SUPABASE_URL, key=SUPABASE_SERVICE_ROLE_KEY)


@handle_exceptions(default_return_value=None, raise_on_error=False)
async def handle_installation_created(payload: GitHubInstallationPayload) -> None:
    """Creates installation records on GitAuto APP installation"""
    installation_id: int = payload["installation"]["id"]
    owner_type: str = payload["installation"]["account"]["type"]
    owner_name: str = payload["installation"]["account"]["login"]
    owner_id: int = payload["installation"]["account"]["id"]
    repo_full_names: list[str] = [repo["full_name"] for repo in payload["repositories"]]
    user_id: int = payload["sender"]["id"]
    user_name: str = payload["sender"]["login"]
    token: str = get_installation_access_token(installation_id=installation_id)

    # Create installation record in Supabase
    supabase_manager.create_installation(
        installation_id=installation_id,
        owner_type=owner_type,
        owner_name=owner_name,
        owner_id=owner_id,
        user_id=user_id,
        user_name=user_name,
    )

    # Add issue templates to the repositories
    for i, full_name in enumerate(iterable=repo_full_names, start=1):
        print(f"\nAdding issue templates ({i}/{len(repo_full_names)}): {full_name}")
        # turn_on_issue(full_name=full_name, token=token)
        add_issue_templates(full_name=full_name, installer_name=user_name, token=token)


@handle_exceptions(default_return_value=None, raise_on_error=False)
async def handle_installation_deleted(payload: GitHubInstallationPayload) -> None:
    """Soft deletes installation record on GitAuto APP installation"""
    installation_id: int = payload["installation"]["id"]
    supabase_manager.delete_installation(installation_id=installation_id)


@handle_exceptions(default_return_value=None, raise_on_error=False)
async def handle_installation_repos_added(payload) -> None:
    installation_id: int = payload["installation"]["id"]
    repo_full_names: list[str] = [
        repo["full_name"] for repo in payload["repositories_added"]
    ]
    sender_name: str = payload["sender"]["login"]
    token: str = get_installation_access_token(installation_id=installation_id)
    for full_name in repo_full_names:
        # turn_on_issue(full_name=full_name, token=token)
        add_issue_templates(
            full_name=full_name, installer_name=sender_name, token=token
        )


@handle_exceptions(default_return_value=None, raise_on_error=True)
async def handle_webhook_event(event_name: str, payload: GitHubEventPayload) -> None:
    """
    Determine the event type and call the appropriate handler.
    Check the type of webhook event and handle accordingly.
    https://docs.github.com/en/apps/github-marketplace/using-the-github-marketplace-api-in-your-app/handling-new-purchases-and-free-trials
    https://docs.github.com/en/webhooks/webhook-events-and-payloads?actionType=purchased#marketplace_purchase
    """
    action: str = payload.get("action")
    if not action:
        return

    # if event_name == "marketplace_purchase" and action in ("purchased"):
    #     print("Marketplace purchase is triggered")
    #     await handle_installation_created(payload=payload)

    # See https://docs.github.com/en/webhooks/webhook-events-and-payloads#installation
    if event_name == "installation" and action in ("created"):
        print("Installation is created")
        await handle_installation_created(payload=payload)
        return
    if event_name == "installation" and action in ("deleted"):
        print("Installation is deleted")
        await handle_installation_deleted(payload=payload)
        return

    # Add issue templates to the repositories when GitAuto is added to a repository
    # See https://docs.github.com/en/webhooks/webhook-events-and-payloads#installation_repositories
    if event_name == "installation_repositories" and action in ("added"):
        await handle_installation_repos_added(payload=payload)
        return

    # Handle issue events
    # See https://docs.github.com/en/webhooks/webhook-events-and-payloads#issues
    if event_name == "issues":
        if action == "labeled":
            await handle_gitauto(payload=payload, trigger_type="label")
            return
        if action == "opened":
            create_comment_on_issue_with_gitauto_button(payload=payload)
            return

    # Run GitAuto when checkbox is checked (edited)
    # See https://docs.github.com/en/webhooks/webhook-events-and-payloads#issue_comment
    if event_name == "issue_comment" and action == "edited":
        issue_handled = False
        search_text = "- [x] Generate PR"
        if PRODUCT_ID != "gitauto":
            search_text += " - " + PRODUCT_ID
            if payload["comment"]["body"].find(search_text) != -1:
                issue_handled = True
                await handle_gitauto(payload=payload, trigger_type="comment")
        else:
            if (
                payload["comment"]["body"].find(search_text) != -1
                and payload["comment"]["body"].find(search_text + " - ") == -1
            ):
                issue_handled = True
                await handle_gitauto(payload=payload, trigger_type="comment")
        if not issue_handled:
            print("Edit is not an activated GitAtuo trigger.")
        return
    
    if event_name.startswith("jira:") and payload["issue"]["fields"]["assignee"]:
        
        github_payload: GitHubEventPayload = cast(GitHubEventPayload, map_jira_to_github_event_payload(jira_payload=payload))
        
        await handle_gitauto_from_jira(payload=github_payload, trigger_type="label")
    
    

    # Track merged PRs as this is also our success status
    # See https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request
    if event_name == "pull_request" and action == "closed":
        pull_request = payload.get("pull_request")
        if not pull_request:
            return

        # Check PR is merged and this is correct GitAuto environment
        if pull_request["merged_at"] is not None and pull_request["head"][
            "ref"
        ].startswith(PRODUCT_ID + ISSUE_NUMBER_FORMAT):
            # Create unique_issue_id to update merged status
            body: str = pull_request["body"]
            if not body.startswith(PR_BODY_STARTS_WITH):
                return
            pattern = re.compile(r"/issues/(\d+)")
            match = re.search(pattern, body)
            if not match:
                return
            issue_number = match.group(1)
            owner_type = payload["repository"]["owner"]["type"]
            unique_issue_id = f"{owner_type}/{payload['repository']['owner']['login']}/{payload['repository']['name']}#{issue_number}"
            supabase_manager.set_issue_to_merged(unique_issue_id=unique_issue_id)
        return

    # Unhandled events are captured here
    print(f"Event {event_name} with action {action} is not handled")

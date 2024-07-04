"""This is scheduled to run by AWS Lambda"""

import logging
import time
from config import PRODUCT_ID, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from services.github.github_manager import (
    add_label_to_issue,
    get_installation_access_token,
    get_installed_owners_and_repos,
    get_oldest_unassigned_open_issue,
)
from services.github.github_types import IssueInfo
from services.supabase import SupabaseManager

supabase_manager = SupabaseManager(url=SUPABASE_URL, key=SUPABASE_SERVICE_ROLE_KEY)


def schedule_handler(_event, _context) -> dict[str, int]:
    print("\n" * 3 + "-" * 70)

    # Get all active installation IDs from Supabase including free customers.
    installation_ids: list[int] = supabase_manager.get_installation_ids()

    # Get all owners and repositories from GitHub.
    for installation_id in installation_ids:
        # Pause for 1+ second to avoid secondary rate limits. https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api?apiVersion=2022-11-28#pause-between-mutative-requests
        time.sleep(1)

        # Get the installation access token for each installation ID.
        token = get_installation_access_token(installation_id=installation_id)
        if token is None:
            logging.info("Token is None for installation_id: %s, so skipping", installation_id)
            continue

        # Get all owners and repositories for each installation ID.
        owners_repos: list[dict[str, str]] = get_installed_owners_and_repos(
            installation_id=installation_id, token=token
        )

        # Process each owner and repository.
        for owner_repo in owners_repos:
            owner: str = owner_repo["owner"]
            repo: str = owner_repo["repo"]
            logging.info("Processing %s/%s", owner, repo)

            # Identify an oldest, open, unassigned, and not gitauto labeled issue for each repository.
            issue: IssueInfo | None = get_oldest_unassigned_open_issue(
                owner=owner, repo=repo, token=token
            )
            logging.info("Issue: %s", issue)

            # This is testing purpose.
            if owner != "gitautoai":
                continue

            # Continue to the next set of owners and repositories if there is no open issue.
            if issue is None:
                continue

            # Extract the issue number if there is an open issue.
            issue_number = issue["number"]

            # Label the issue with the product ID to trigger GitAuto.
            time.sleep(1)
            add_label_to_issue(
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                label=PRODUCT_ID,
                token=token,
            )

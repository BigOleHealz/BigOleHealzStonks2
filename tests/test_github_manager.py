# Local imports
from config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)
from services.github.github_manager import check_github_issue_exists, create_github_issue, close_github_issue
from github.Issue import Issue
from services.supabase import SupabaseManager

supabase_manager = SupabaseManager(url=SUPABASE_URL, key=SUPABASE_SERVICE_ROLE_KEY)

def test_create_github_issue() -> None:
    # Define the issue title and description
    title = "Test Issue for Verification"
    description = "This issue is created to test the check_github_issue_exists function."

    # Step 1: Create a new GitHub issue
    created_issue: Issue = create_github_issue(title=title, description=description)
    assert created_issue is not None, "Failed to create issue."
    assert created_issue.title == title, "Issue titles do not match."
    assert created_issue.body == description, "Issue descriptions do not match."
    assert created_issue.state == "open", "Issue is not open."

    # Step 2: Retrieve the issue number from the created issue
    issue_number: int = created_issue.number

    # Step 3: Check if the issue exists using the second function
    fetched_issue: Issue = check_github_issue_exists(issue_number=issue_number)
    assert fetched_issue is not None, "Issue does not exist."

    # Step 4: Assert that the issue details match
    assert fetched_issue.number == issue_number, "Issue numbers do not match."
    assert fetched_issue.title == title, "Issue titles do not match."
    assert fetched_issue.body == description, "Issue descriptions do not match."
    
    deleted_issue: Issue = close_github_issue(issue_number=issue_number)
    assert deleted_issue is not None, "Failed to delete issue."
    assert deleted_issue.state == "closed", "Issue is not closed."

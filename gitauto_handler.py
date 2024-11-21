def handle_gitauto(payload):
    issue_key = payload["issue"]["key"]
    new_branch_name = issue_key  # Set branch name to Jira issue key
    # ... rest of the function ...

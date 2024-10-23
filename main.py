# Standard imports
import json
import urllib.parse
from typing import Any

# Third-party imports
from github.Issue import Issue
import sentry_sdk
from fastapi import FastAPI, Request
from mangum import Mangum
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

# Local imports
from config import (
    ENV,
    GITHUB_WEBHOOK_SECRET,
    PRODUCT_NAME,
    SENTRY_DSN,
    UTF8
)
from scheduler import schedule_handler
from services.github.github_manager import create_github_issue, verify_webhook_signature
from services.jira.jira_manager import (
    add_comment_to_jira,
    extract_issue_details
)
from services.webhook_handler import handle_webhook_event

if ENV != "local":
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENV,
        integrations=[AwsLambdaIntegration()],
        traces_sample_rate=1.0,
    )

# Create FastAPI instance and Mangum handler. Mangum is a library that allows you to use FastAPI with AWS Lambda.
app = FastAPI()
mangum_handler = Mangum(app=app)


# Here is an entry point for the AWS Lambda function. Mangum is a library that allows you to use FastAPI with AWS Lambda.
def handler(event, context):
    if "source" in event and event["source"] == "aws.events":
        schedule_handler(_event=event, _context=context)
        return {"statusCode": 200}

    return mangum_handler(event=event, context=context)


@app.post(path="/webhook")
async def handle_webhook(request: Request) -> dict[str, str]:
    content_type: str = request.headers.get(
        "Content-Type", "Content-Type not specified"
    )
    event_name: str = request.headers.get("X-GitHub-Event", "Event not specified")
    print("\n" * 3 + "-" * 70)
    print(f"Received event: {event_name} with content type: {content_type}\n")

    # Validate if the webhook signature comes from GitHub
    await verify_webhook_signature(request=request, secret=GITHUB_WEBHOOK_SECRET)

    # Process the webhook event but never raise an exception as some event_name like "marketplace_purchase" doesn't have a payload
    try:
        request_body: bytes = await request.body()
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error in reading request body: {e}")
        request_body = b""

    payload: Any = {}
    try:
        # First try to parse the body as JSON
        payload = json.loads(s=request_body.decode(encoding=UTF8))
    except json.JSONDecodeError:
        # If JSON parsing fails, treat the body as URL-encoded
        decoded_body: dict[str, list[str]] = urllib.parse.parse_qs(
            qs=request_body.decode(encoding=UTF8)
        )
        if "payload" in decoded_body:
            payload = json.loads(s=decoded_body["payload"][0])
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error in parsing JSON payload: {e}")

    await handle_webhook_event(event_name=event_name, payload=payload)

@app.post("/jira-webhook")
async def handle_jira_webhook(request: Request):
    try:
        payload: dict = await request.json()
        jira_issue: dict = extract_issue_details(payload=payload)
        if not (jira_issue_key := jira_issue.get("key")):
            raise ValueError("JIRA issue key not found in the payload.")
        
        github_issue: Issue = create_github_issue(title=jira_issue["title"], description=jira_issue["description"])
        
        add_comment_to_jira(issue_key=jira_issue_key, github_issue_link=github_issue.html_url)
        
        return {"message": "Jira webhook processed successfully"}

    except Exception as e:
        print(f"Error in processing JIRA webhook: {e}")
        return {"message": f"Error in processing JIRA webhook: {e}"}

@app.get(path="/")
async def root() -> dict[str, str]:
    return {"message": PRODUCT_NAME}

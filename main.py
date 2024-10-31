# Standard imports
import json
import urllib.parse
from typing import Any

# Third-party imports
import sentry_sdk
from fastapi import FastAPI, Request
from mangum import Mangum
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

# Local imports
from config import (
    ENV,
    GITHUB_TEST_REPO_NAME,
    GITHUB_TEST_REPO_OWNER,
    GITHUB_WEBHOOK_SECRET,
    JIRA_WEBHOOK_SECRET,
    PRODUCT_NAME,
    SENTRY_DSN,
    UTF8
)
from scheduler import schedule_handler
from services.github.github_manager import verify_webhook_signature as verify_github_webhook_signature
from services.jira.jira_manager import (
    verify_webhook_signature as verify_jira_webhook_signature
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
    print(f"Received event: {event_name} from Agent: Github with content type: {content_type}")
    await verify_github_webhook_signature(request=request, secret=GITHUB_WEBHOOK_SECRET)

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

@app.post(path="/jira-webhook")
async def handle_webhook(request: Request) -> dict[str, str]:
    content_type: str = request.headers.get(
        "Content-Type", "Content-Type not specified"
    )
    event_name: str = (await request.json()).get("webhookEvent", "Event not specified")
    
    print("\n" * 3 + "-" * 70)
    print(f"Received event: {event_name} from Agent: JIRA with content type: {content_type}")
    await verify_jira_webhook_signature(request=request, secret=JIRA_WEBHOOK_SECRET)
    
    try:
        request_body: bytes = await request.body()
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error in reading request body: {e}")
        request_body = b""

    payload: Any = {}
    try:
        # First try to parse the body as JSON
        payload = json.loads(s=request_body.decode(encoding=UTF8))
        
        username: str = GITHUB_TEST_REPO_NAME
        payload["action"] = event_name
        payload.setdefault("installation", {})["id"] = 56165848
        payload["issue"]["fields"]["reporter"]["accountId"] = 17244643
        payload["issue"]["fields"]["creator"]["displayName"] = username
        payload["user"]["displayName"] = username
        payload["issue"]["fields"]["reporter"]["displayName"] = username
            
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


@app.get(path="/")
async def root() -> dict[str, str]:
    return {"message": PRODUCT_NAME}

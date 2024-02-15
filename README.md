# issue-to-pr

## What we do

We provide an AI agent that automatically generates pull requests from issues for backend code, enabling engineers to concentrate on core development.

## What the workflow is

### User preparation

- User: Visit the homepage or GitHub marketplace.
- User: Sign up with GiHub using the GitHub Authentication API.
- User: Install our app to repositories where the user wants to.

### Iterration thereafter

- AI: Automatically picks the most recent unclosed GitHub issue.
- AI: Assigns itself as the assignee for that issue.
- AI: Creates a new branch for that issue.
- AI: Inputs the content of that issue (text only).
- AI: Searches 5 related files in the repository based on the input.
- AI: Writes code to resolve the issue.
- AI: Double check for unnecessary lines that could cause bugs
- AI: Turns that code into files.
- AI: Commits those files.
- AI: Identifies the main branch.
- AI: Creates a new pull request.
- AI: Write a description of that pull request in xxx format

## What the tech stack is

### Application

- Main: Python
- Framework: Fast API
- Runtime: Uvicorn
- Hosting: AWS Lambda?
- DB: Supabase?
- Payment: Stripe
- Unit Testing: Pytest?

### Homepage

- Main: TypeScript and React
- CSS: Tailwind CSS
- Framework: Next.js
- Hosting: Vercel
- Payment: Stripe
- DB: Supabase
- Unit Testing: Jest
- E2E Testing: Playwright

### Sales

- Outbound Email: Artisan AI
- Outbound LinkedIn:
- Twitter:
- Scheduling: Calendly

## How to develop locally

### Tunnel to localhost with ngrok

1. Run `ngrok http --config=ngrok.yml --domain=genpr.ai 8000`.
2. ngrok will generate a URL `https://genpr.ai` that tunnels to `http://localhost:8000`.
3. Use `https://genpr.ai` as the webhook URL in the GitHub app settings.

### Create a virtual environment

1. Run `python3 -m venv venv` to create a virtual environment.
2. Run `source venv/bin/activate` to activate the virtual environment. You will see `(venv)` in the terminal.
3. Note that you need to activate the virtual environment every time you open a new terminal.

### How to run the code

1. Run `pip-compile requirements.in` to create `requirements.txt` from `requirements.in`.
2. Run `pip install -r requirements.txt` to install the dependencies.
3. Run `uvicorn main:app --reload --port 8000`.

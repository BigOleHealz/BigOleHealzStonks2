import io
import zipfile
import requests
from config import GITHUB_API_URL, TIMEOUT, UTF8
from services.github.create_headers import create_headers
from utils.handle_exceptions import handle_exceptions


def get_failed_step_log_file_name(owner: str, repo: str, run_id: int, token: str):
    """No official API documents"""
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    headers = create_headers(token=token)
    response = requests.get(url=url, headers=headers, timeout=TIMEOUT)
    if response.status_code == 404 and "Not Found" in response.text:
        return response.status_code
    response.raise_for_status()
    data = response.json()

    # Get the first failed step name
    for job in data.get("jobs", []):
        job_name = job.get("name", "unknown_job")
        for step in job.get("steps", []):
            if step.get("conclusion") == "failure":
                step_number = step.get("number")
                step_name = step.get("name")
                return f"{job_name}/{step_number}_{step_name}.txt"

    # Return None if no failed step is found
    return None


@handle_exceptions(default_return_value="", raise_on_error=False)
def get_workflow_run_path(owner: str, repo: str, run_id: int, token: str):
    """https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#get-a-workflow-run"""
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/runs/{run_id}"
    headers = create_headers(token=token)
    response = requests.get(url=url, headers=headers, timeout=TIMEOUT)
    if response.status_code == 404 and "Not Found" in response.text:
        return response.status_code
    response.raise_for_status()
    json = response.json()
    path: str = json["path"]
    return path


@handle_exceptions(default_return_value="", raise_on_error=False)
def get_workflow_run_logs(owner: str, repo: str, run_id: int, token: str):
    """https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#download-workflow-run-logs"""
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    headers = create_headers(media_type="", token=token)
    response = requests.get(url=url, headers=headers, timeout=TIMEOUT)
    if response.status_code == 404 and "Not Found" in response.text:
        return response.status_code
    response.raise_for_status()

    # Get the failed step file name
    failed_step_fname = get_failed_step_log_file_name(
        owner=owner, repo=repo, run_id=run_id, token=token
    )
    if failed_step_fname == 404:
        return failed_step_fname

    # Read the content of the zip file
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        for log_fname in zf.namelist():
            if log_fname != failed_step_fname:
                continue

            # Remove the first 28 characters from the log content
            # E.g. "2024-10-18T23:27:40.6602932Z "
            with zf.open(name=log_fname) as lf:
                content = lf.read().decode(encoding=UTF8)
                content = "\n".join(
                    line[29:] if len(line) > 29 else line
                    for line in content.splitlines()
                )
                content = f"```GitHub Check Run Log: {log_fname}\n{content}\n```"
                return content

    return None

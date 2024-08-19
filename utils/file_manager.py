# Standard imports
import logging
import os
import re
import subprocess
import tempfile

# Local imports
from config import IS_PRD, UTF8
from utils.handle_exceptions import handle_exceptions


def apply_patch(original_text: str, diff_text: str):
    """Apply a diff using the patch command via temporary files.
    Here is comparison of patch options in handling "Assume -R?" and "Apply anyway?" prompts:

    --forward:
    Assume -R? [n]: No
    Apply anyway? [n]: No

    --batch:
    Assume -R? [y]: Yes
    Apply anyway? [y]: Yes

    --force:
    Assume -R? [n]: No
    Apply anyway? [y]: Yes
    """
    with tempfile.NamedTemporaryFile(mode="w+", newline="", delete=False) as org_file:
        org_fname: str = org_file.name
        if original_text:
            s = original_text if original_text.endswith("\n") else original_text + "\n"
            org_file.write(s)

    with tempfile.NamedTemporaryFile(mode="w+", newline="", delete=False) as diff_file:
        diff_fname: str = diff_file.name
        diff_file.write(diff_text if diff_text.endswith("\n") else diff_text + "\n")

    modified_text = ""
    try:
        # New file
        if original_text == "" and "+++ " in diff_text:
            lines: list[str] = diff_text.split(sep="\n")
            new_content_lines: list[str] = [
                line[1:] if line.startswith("+") else line for line in lines[3:]
            ]
            new_content: str = "\n".join(new_content_lines)
            with open(file=org_fname, mode="w", encoding=UTF8, newline="") as new_file:
                new_file.write(new_content)

        # Modified or deleted file
        else:
            with open(file=diff_fname, mode="r", encoding=UTF8, newline="") as diff:
                subprocess.run(
                    # See https://www.man7.org/linux/man-pages/man1/patch.1.html
                    args=["patch", "-u", "--fuzz=3", "--forward", org_fname],
                    input=diff.read(),
                    text=True,  # If True, input and output are strings
                    # capture_output=True,  # Redundant so commented out
                    check=True,  # If True, raise a CalledProcessError if the return code is non-zero
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

        # If the patch was successfully applied, get the modified text
        modified_text, modified_text_repr = get_file_content_tuple(file_path=org_fname)

    except subprocess.CalledProcessError as e:
        stdout: str = e.stdout
        stderr: str = e.stderr
        cmd, code = " ".join(e.cmd), e.returncode

        # Check if the error message indicates that the patch was already applied
        msg = f"Failed to apply patch because the diff is already applied.\n\n{diff_text=}"
        if "already exists!" in stdout:
            print(msg)
            return "", msg
        if "Ignoring previously applied (or reversed) patch." in stdout:
            print(msg)
            return "", msg

        # Get the original, diff, and reject file contents for debugging
        original_text_repr: str = repr(original_text).replace(" ", "·")
        modified_text, modified_text_repr = get_file_content_tuple(file_path=org_fname)
        diff_text, diff_text_repr = get_file_content_tuple(file_path=diff_fname)
        rej_f_name: str = f"{org_fname}.rej"
        rej_text, reject_text_repr = "", ""
        if os.path.exists(path=rej_f_name):
            rej_text, reject_text_repr = get_file_content_tuple(file_path=rej_f_name)

        # Log the error and return an empty string not to break the flow
        if IS_PRD:
            msg = f"Failed to apply patch. stdout:\n{stdout}\n\nDiff content:\n{diff_text_repr}\n\nReject content:\n{reject_text_repr}\n\nOriginal content:\n{original_text_repr}\n\nModified content:\n{modified_text_repr}\n\nstderr:\n{stderr}\n\nCommand: {cmd}\n\nReturn code: {code}"
        else:
            msg = f"Failed to apply patch.\n\nDiff content:\n{diff_text}\n\nReject content:\n{reject_text_repr}\n\nstderr: {stderr}"
        logging.error(msg=msg)
        return modified_text, rej_text

    except Exception as e:  # pylint: disable=broad-except
        logging.error(msg=f"Error: {e}")
        return "", f"Error: {e}"
    finally:
        os.remove(path=org_fname)
        os.remove(path=diff_fname)

    return modified_text, ""


def clean_specific_lines(text: str) -> str:
    return "\n".join(
        [
            line
            for line in text.strip().split(sep="\n")
            if line.startswith(("+++", "---", "@@", "+", "-"))
        ]
    ).strip()


def correct_hunk_headers(diff_text: str) -> str:
    """
    Match following patterns:
    1: @@ -start1 +start2 @@
    2: @@ -start1,lines1 +start2 @@
    3: @@ -start1 +start2,lines2 @@
    4: @@ -start1,lines1 +start2,lines2 @@
    """
    # Split the diff into lines
    lines: list[str] = diff_text.splitlines()
    updated_lines: list[str] = []
    hunk_pattern: re.Pattern[str] = re.compile(
        pattern=r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
    )

    i = 0
    while i < len(lines):
        line: str = lines[i]
        match: re.Match[str] | None = hunk_pattern.match(string=line)

        # Add the line to the updated diff if it's not a hunk header
        if not match:
            updated_lines.append(line)
            i += 1
            continue

        # Correct the hunk header if match is not None
        l1, _s1, l2, _s2 = (int(x) if x is not None else 0 for x in match.groups())
        s1_actual, s2_actual = 0, 0
        i += 1

        # Count actual number of lines changed
        start_index: int = i
        while i < len(lines) and not lines[i].startswith("@@"):
            if lines[i].startswith("+"):
                s2_actual += 1
            if lines[i].startswith("-"):
                s1_actual += 1
            i += 1

        # Update the hunk header with actual numbers
        updated_hunk_header: str = f"@@ -{l1},{s1_actual} +{l2},{s2_actual} @@"
        updated_lines.append(updated_hunk_header)
        updated_lines.extend(lines[start_index:i])

    return "\n".join(updated_lines)


def extract_file_name(diff_text: str) -> str:
    match = re.search(pattern=r"^\+\+\+ (.+)$", string=diff_text, flags=re.MULTILINE)
    if match:
        return match.group(1)
    raise ValueError("No file name found in the diff text.")


@handle_exceptions(default_return_value="", raise_on_error=False)
def get_file_content(file_path: str):
    with open(file=file_path, mode="r", encoding=UTF8, newline="") as file:
        return file.read()


@handle_exceptions(default_return_value=("", ""), raise_on_error=False)
def get_file_content_tuple(file_path: str):
    with open(file=file_path, mode="r", encoding=UTF8, newline="") as file:
        text: str = file.read()
    return text, repr(text).replace(" ", "·")


def run_command(command: str, cwd: str) -> str:
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            args=command,
            capture_output=True,
            check=True,
            cwd=cwd,
            text=True,
            shell=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        # 127: Command not found so check if Git is installed
        if e.returncode == 127:
            try:
                # Check if Git is installed
                version_result = subprocess.run(
                    args="git --version",
                    capture_output=True,
                    check=True,
                    text=True,
                    shell=True,
                )
                logging.info("Git version: %s", version_result.stdout)
            except subprocess.CalledProcessError as ve:
                logging.error("Failed to get Git version: %s", ve.stderr)

        raise ValueError(f"Command failed: {e.stderr}") from e


def split_diffs(diff_text: str) -> list[str]:
    file_diffs: list[str] = re.split(
        pattern=r"(?=^---\s)", string=diff_text, flags=re.MULTILINE
    )

    # Remove the first element if it's an empty string
    if file_diffs and file_diffs[0] == "":
        file_diffs.pop(0)

    # Remove leading and trailing whitespace from each diff
    cleaned_diffs: list[str] = []
    for diff in file_diffs:
        stripped_diff: str = diff.strip()
        if not stripped_diff.endswith("\n"):
            stripped_diff += "\n"
        cleaned_diffs.append(stripped_diff)

    return cleaned_diffs

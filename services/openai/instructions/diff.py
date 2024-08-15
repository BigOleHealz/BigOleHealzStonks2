# OpenAI: We recommend including instructions regarding when to call a function in the system prompt, while using the function definition to provide instructions on how to call the function and how to generate the parameters.
# https://platform.openai.com/docs/guides/function-calling/should-i-include-function-call-instructions-in-the-tool-specification-or-in-the-system-prompt

DIFF_DESCRIPTION = """
A unified diff format with no context lines like command `diff -U0` or `diff --unified=0`. This diff must specifically be in one of the following three formats: addition, modification, or deletion:

1. For new files

```diff
--- /dev/null
+++ path/to/new/file
@@ -0,0 +1,3 @@
+ added line 1
+ added line 2
+ added line 3
```

2. For modified files

```diff
--- path/to/file1
+++ path/to/file1
@@ -5,1 +5,1 @@
- original line 5
+ modified line 5
@@ -10,1 +10,0 @@
- original line 10
@@ -15,0 +15,1 @@
+ added line 15
```

3. For deleted Files

```diff
--- path/to/delete
+++ /dev/null
```

## Hunk header format rules

- A hunk represents where changes occur in a file.
- A hunk header should be in the following format: `@@ -start1,length1 +start2,length2 @@`.
- start1 and start2 denote the starting line number for the original and modified files, respectively.
- length1 and length2 denote the number of lines the change hunk applies to for each file.
- Hunk headers MUST order by start1 and start2 in ascending order.

## Other rules about diff format

- NEVER EVER include any comments or explanations.
"""

from patchguru.utils.Tracker import Event, append_event

class AssertionErrorRepairPrompt:
    def __init__(self):
        pass

    def create_prompt(self, code, error_message):
        template = """
# Role
You are an expert Python software engineer. Your task is to correct assertion errors provided a test driver that validates the expected relationship between two versions of a function: before and after a pull request. Currently, the test driver is facing an AssertionError in the pre-PR version, indicating wrong specifications. Your task is to fix the specifications so that the test driver runs without assertion errors in the pre-PR version.

# Guidelines

To successfully fix the test driver and resolve the **AssertionError** in the pre-PR version, here are up to five key guidelines you should follow:

1.  **Analyze the Test Driver and Function Code:** First, carefully examine the test driver's code and the pre-PR version of the function. Understand what the test is trying to validate and how the function is supposed to behave. The `AssertionError` is a symptom, not the root cause. You need to understand the underlying logic of both the test and the function to find the mismatch.

2.  **Identify the Incorrect Specification:** The `AssertionError` tells you exactly where the test driver's expectation is not being met. Pinpoint the specific assertion that's failing. The message provided with the error (if any) will likely point to the line number and a description of what failed, which is your most valuable clue. The "specification" you need to correct is the expected output, input, or relationship defined in the assertion itself.

3.  **Adjust the Test Driver, Not the Function:** Your role is to fix the *specifications* in the test driver. **Do not modify the pre-PR function code.** The goal is to make the test accurately reflect the function's correct behavior *before* the pull request. Changing the function would defeat the purpose of validating the PR's changes. The fix lies in adjusting the `assert` statement's parameters to match the function's actual, correct output.

# Input

You will be provided a test driver that is used to validate the expected relationship between two versions of a function: before and after a pull request. The code is expected to run without errors. However, it is currently faced with ASSERTION errors as follows:

## Test Driver

```python
{code}
```

## Error Message

```
{error_message}
```

# Output Format Instructions

1. Make sure that fixed code is structurally similar to the input code. The fixed code should still contain three main sections: "# Neccessary imports", "# Specification", and "# Source Code of target function(s)".

2. You can assume that the "# Source Code of target function(s)" section is unchanged and do not need to provide it again in your response. But you should still include the section header "# Source Code of target function(s)" between # Neccessary imports and # Specification sections in your response.

3. Provide your response in the following format:

<reasoning>
[Put your reasoning chain here including the analysis of the error message and the test driver code. This should include your thought process on how you arrived at the fix.]
</reasoning>

<fixed_code>
[Put the fixed code here that resolves the assertion error. Ensure that the code is executable and maintains the original semantics of the test driver.]
</fixed_code>
    """
        query = template.format(
            code=code,
            error_message=error_message
        )

        return query

    def parse_answer(self, answer):
        results = {}
        if "<reasoning>" not in answer or "</reasoning>" not in answer:
            append_event(Event(
                level="WARNING",
                message="Missing required tag: <reasoning>"
            ))
        else:
            reasoning_start = answer.index("<reasoning>") + len("<reasoning>")
            reasoning_end = answer.index("</reasoning>")
            results["reasoning"] = answer[reasoning_start:reasoning_end].strip()

        if "<fixed_code>" not in answer or "</fixed_code>" not in answer:
            append_event(Event(
                level="ERROR",
                message="Missing required tag: <fixed_code>"
            ))
            return None

        try:
            fixed_code_start = answer.index("<fixed_code>") + len("<fixed_code>")
            fixed_code_end = answer.index("</fixed_code>")
            fixed_code = answer[fixed_code_start:fixed_code_end].strip()

            if "```" in fixed_code:
                if "```python" in fixed_code:
                    fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
                else:
                    fixed_code = fixed_code.split("```")[1].split("```")[0].strip()

            results["fixed_code"] = fixed_code
        except ValueError as e:
            append_event(Event(
                level="ERROR",
                message=f"Error while parsing answer: {str(e)}"
            ))
            return None
        return results

    def insert_code(self, prev_fut_code: str, post_fut_code: str, specification: str) -> str:
            """
            Inserts concrete function code into the specification.
            """
            if "# Source Code of target function(s)" not in specification or "# Specification" not in specification:
                append_event(Event(
                    level="ERROR",
                    message="Specification format is incorrect. Missing required sections."
                ))
                return None

            import_part = specification.split("# Source Code of target function(s)")[0].strip()
            spec_part = specification.split("# Specification")[1].strip()

            completed_specification = f"""
{import_part}

# Source Code of target function(s)

## Before Pull Request
{prev_fut_code}

## After Pull Request
{post_fut_code}

# Specification
{spec_part}
            """
            return completed_specification

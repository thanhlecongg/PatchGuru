from patchguru.utils.Tracker import Event, append_event

class SyntaxErrorRepairPrompt:
    def __init__(self):
        pass

    def create_prompt(self, code, error_message):
        template = """
# Role
You are an expert Python software engineer. Your task is to correct syntax errors in the provided Python code based on the accompanying error message.

# Guidelines

1. **Only Debug on Target Sections**: Provided Python code is a test driver with three main sections: "# Neccessary imports", "# Specification", and "# Source Code of target function(s)". You MUST focus all debugging efforts on the "# Neccessary imports" and "# Specification" sections. The "# Source Code of target function(s)" section is guaranteed to be correct and should not be changed.

2.  **Read the Error Message Carefully:** The traceback is your most valuable tool. Python's error messages are often very specific and will tell you the exact file, line number, and type of error. Pay close attention to the error type (e.g., `SyntaxError`, `IndentationError`, `NameError`) and the message that follows, as it often hints at what is wrong.

3.  **Focus on the Indicated Line and its Neighbors:** Once you identify the line number from the error message, examine that line of code first. If the error isn't immediately obvious, look at the line directly above it. Syntax errors often occur because of a missing colon, parenthesis, or bracket on the preceding line.

4.  **Check for Common Syntax Mistakes:** Be on the lookout for frequent errors such as:
    * **Missing or Mismatched Brackets/Parentheses:** Ensure every opening of bracket, parenthesis, or brace has a corresponding closing one.
    * **Incorrect Indentation:** Python uses indentation to define code blocks. Mixing spaces and tabs or having an inconsistent number of spaces will cause an `IndentationError`.
    * **Missing Dependencies:** Ensure all necessary imports are present and correctly spelled.

# Input

You will be provided a test driver that is used to validate the expected relationship between two versions of a function: before and after a pull request. The code is expected to run without errors. However, it is currently faced with SYNTAX errors as follows:

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
[Put the fixed code here that resolves the syntax error. Ensure that the code is executable and maintains the original semantics of the test driver.]
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

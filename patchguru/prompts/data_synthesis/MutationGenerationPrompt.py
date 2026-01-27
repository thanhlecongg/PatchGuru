from patchguru.utils.Logger import get_logger


class MutationGenerationPrompt:
    def __init__(self):
        self.logger = get_logger("mutation_generation_prompt")
        self.logger.debug("MutationGenerationPrompt initialized")

    def create_prompt(self, code: str):
        template = """
You are a coding assistant that specializes in generating mutations for mutation testing in Python code.

# Input

You will be provided a Python code snippet. Your task is to generate mutations for the provided code snippet that can be used for mutation testing. The mutations should be syntactically correct but should change the semantics of the code in a way that can be used to test the robustness of the code against various types of faults.

## Code Snippet

```python
{code}
```

# Instructions
## Task

Your task is to analyze the provided code snippet and generate mutations that can be used for mutation testing. You should do step-by-step reasoning as follows:
1. Analyze the provided code to understand its structure and functionality.
2. Identify potential points in the code where mutations can be applied.
3. Generate mutations that change the semantics of the code while maintaining syntactic correctness.

## Constraints

- Mutations should be syntactically correct Python code.
- Mutations should change the semantics of the code in a way that can be used for mutation testing.
- Ensure that the generated mutations are diverse and cover various types of faults.
- Do not change identifiers such as variable names, function names, or class names.
- Provide full modified code snippets for each mutation.

## Output Format

Provide three different mutations in the following format:

<mutation_1>
[Put the first mutation here]
</mutation_1>

<mutation_2>
[Put the second mutation here]
</mutation_2>

<mutation_3>
[Put the third mutation here]
</mutation_3>
        """
        query = template.format(code=code)

        self.logger.debug(f"Created prompt:\n {query}")
        self.logger.debug("MutationGenerationPrompt created successfully")
        return query

    def parse_answer(self, answer: str) -> dict | None:
        self.logger.debug("Parsing answer for MutationGenerationPrompt")
        if "<mutation_1>" not in answer:
            self.logger.error("Missing required tag: <mutation_1>")
            return None
        if "<mutation_2>" not in answer:
            self.logger.error("Missing required tag: <mutation_2>")
            return None
        if "<mutation_3>" not in answer:
            self.logger.error("Missing required tag: <mutation_3>")
            return None

        results = []

        try:
            mutation_1_start = answer.index("<mutation_1>") + len("<mutation_1>")
            if "</mutation_1>" in answer:
                mutation_1_end = answer.index("</mutation_1>")
                mutation_1 = answer[mutation_1_start:mutation_1_end].strip()
            else:
                mutation_1_end = answer.index("<mutation_2>")
                mutation_1 = answer[mutation_1_start:mutation_1_end].strip()

            if "```" in mutation_1:
                if "```python" in mutation_1:
                    mutation_1 = mutation_1.split("```python")[1].split("```")[0].strip()
                else:
                    mutation_1 = mutation_1.split("```")[1].split("```")[0].strip()

            results.append(mutation_1)

            mutation_2_start = answer.index("<mutation_2>") + len("<mutation_2>")
            if "</mutation_2>" in answer:
                mutation_2_end = answer.index("</mutation_2>")
                mutation_2 = answer[mutation_2_start:mutation_2_end].strip()
            else:
                mutation_2_end = answer.index("<mutation_3>")
                mutation_2 = answer[mutation_2_start:mutation_2_end].strip()

            if "```" in mutation_2:
                if "```python" in mutation_2:
                    mutation_2 = mutation_2.split("```python")[1].split("```")[0].strip()
                else:
                    mutation_2 = mutation_2.split("```")[1].split("```")[0].strip()

            results.append(mutation_2)

            mutation_3_start = answer.index("<mutation_3>") + len("<mutation_3>")
            if "</mutation_3>" in answer:
                mutation_3_end = answer.index("</mutation_3>")
                mutation_3 = answer[mutation_3_start:mutation_3_end].strip()
            else:
                mutation_3_end = len(answer)
                mutation_3 = answer[mutation_3_start:mutation_3_end].strip()

            if "```" in mutation_3:
                if "```python" in mutation_3:
                    mutation_3 = mutation_3.split("```python")[1].split("```")[0].strip()
                else:
                    mutation_3 = mutation_3.split("```")[1].split("```")[0].strip()

            results.append(mutation_3)

        except ValueError as e:
            self.logger.error(f"Error parsing the answer: {e}")
            return None

        self.logger.debug(f"Parsed mutations: {results}")
        return {
            "mutation_1": results[0],
            "mutation_2": results[1],
            "mutation_3": results[2]
        }

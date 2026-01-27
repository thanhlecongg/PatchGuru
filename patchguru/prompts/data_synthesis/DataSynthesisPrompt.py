from patchguru.utils.Logger import get_logger


class DataSynthesisPrompt:
    def __init__(self):
        self.logger = get_logger("data_synthesis")
        self.logger.info("DataSynthesisPrompt initialized")

    def create_prompt(
        self,
        description: str,
    ) -> str:
        self.logger.debug(f"Creating prompt with description length: {len(description)}")

        template = """
You are expert software engineer. Your task is synthesize a Pull Request (PR) that contains two versions of a function. The two versions should be related to each other according to the description below.

# Description
{description}

# Task
Create a PR that contains two versions of a function and PR details that explains the changes made. Please strictly follows the instructions below:
- The PR should contain two versions of a function, one before the change and one after the change. Pre-PR version should be denoted by "pre_" prefix and post-PR version should be denoted by "post_" prefix. These versions should be related to each other according to the description provided. If description requires that they have the same output, please make their syntax different but their output the same.
- Each function should be complex and realistic. Their function parameters and return types should be basic types such as int, str, list, dict, etc. Do not use complex types or custom classes. Also, please annotate the function parameters and return types with type hints.
- PR should also includes details should following a real PR description including title, description, and conversations beetween developers.
Provide the results using the following format:

<PR Details>
...
</PR Details>

<Function Name>
...
</Function Name>

<Pre-PR Version>
...
</Pre-PR Version>

<Post-PR Version>
...
</Post-PR Version>
        """

        result = template.format(description=description)
        self.logger.debug("Prompt created successfully")
        return result

    def parse_answer(self, answer: str) -> dict | None:
        self.logger.debug(f"Parsing answer with length: {len(answer)}")

        results = {}
        _mapping = {
            "PR Details": "pr_details",
            "Function Name": "function_name",
            "Pre-PR Version": "pre_pr_version",
            "Post-PR Version": "post_pr_version",
        }
        try:
            for tag, key in _mapping.items():
                if f"<{tag}>" not in answer or f"</{tag}>" not in answer:
                    self.logger.error(f"Missing required tag: {tag}")
                    raise ValueError(f"Missing required tag: {tag}")

                extracted_answer = answer.split(f"<{tag}>")[1].split(f"</{tag}>")[0].strip()

                if "```" in extracted_answer:
                    if "```python" in extracted_answer:
                        extracted_answer = extracted_answer.split("```python")[1].split("```")[0].strip()
                    else:
                        extracted_answer = extracted_answer.split("```")[1].split("```")[0].strip()

                results[key] = extracted_answer

            self.logger.info("Answer parsed successfully")
            return results

        except Exception as e:
            self.logger.error(f"Error parsing answer: {e!s}", exc_info=True)
            self.logger.debug(f"Full answer content: {answer}")
            return None

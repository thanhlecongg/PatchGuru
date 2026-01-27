from patchguru.utils.Tracker import Event, append_event

class IntentAnalysisPrompt:
    def __init__(self):
        pass

    def create_prompt(
        self,
        pull_request_details: str,
        prev_fut_code: str,
        prev_fut_names: str,
        post_fut_signatures: str,
        available_import: str = "",
        enclosing_class: str = "",
    ) -> str:
        template = """
# Role
You are an expert software developer. Your task is to:
- Infer the developer's intent behind the pull request (PR).
- Write Python assertions comparing the pre-PR and post-PR versions.
- Generate a test driver that can be executed to validate the assertions automatically.

# Guidelines

1. **Understand the Context:** This is your starting point. Read the original implementations of the function(s) before the PR and the broader context in which they operate, such as the enclosing class or module, if applicable. Understand what the function(s) are supposed to do, their inputs, outputs, and any edge cases they handle. This foundational knowledge is crucial for effective review.

2.  **Infer the Developer's Intent:** Next, read the PR details carefully. Look for clues in the title, description, and any comments, discussions and related references (e.g., PRs and issues). Then try to answer the following questions:
- What is the developer trying to accomplish?
- Is it a bug fix, a new feature, or a performance tweak?
- What specific problem or limitation in the original code is being addressed?
- How does the proposed change improve or alter the original semantics?
Your entire review hinges on your accurate understanding of this intent.

3.  **Define the Expected Behavior:** Based on the inferred intent, clearly state the desired outcome. For example, if it's a bug fix, describe what the system **should do now** that it didn't do before. If it's a new feature, describe the exact functionality it must provide.

4.  **Identify the Invariant Properties:** What aspects of the system should remain unchanged after the PR is merged? For example, if a database query is being optimized, the data it returns should be the same. This helps ensure that the change doesn't introduce unintended side effects.

5.  **Create a Testable Hypothesis:** This step is crucial for validating code changes in PR. In ideal cases, your hypothesis should not just describe the old and new behaviors in isolation, but instead state the explicit causal relationship between them. It is the narrative that your assertions will prove.

      * **Ideal Format:** "Given input `X`, the pre-PR version returns `Y`, while the post-PR version will return `Z`, where `Z` is a filtered version of `Y`."

      * **Example:**

          * **Inferred Intent:** A fix for a user profile data sanitization function. The bug is that it correctly filters profanity but fails to remove malicious URLs. The fix should add URL filtering.
          * **Hypothesis:** "When a user-provided string containing both profanity and a malicious URL is passed to the sanitization function, the pre-PR version will return a string with the profanity removed but the URL intact, while the post-PR version will return a string with both the profanity and the URL removed."

6.  **Write Precise Python Assertions:** This is a key step. You will write assertions that directly express the relationship between the pre-PR and post-PR versions. Instead of just asserting the final outcome, your assertions will compare the behaviors of both versions. Ensure that your assertions are precise, unambiguous, and directly tied to the inferred intent and hypothesis. Besides, you MUST provide generalized assertions that can be executed various input values. Avoid hardcoding specific input values in your assertions.

      * **Example (Data Filtering from above):**
          * **Scenario Setup:** A mock string containing both types of unsanitized data.
        ```python
        # Assume a helper function that simulates the script on a given version
        def pre_sanitize_input(input_string):
            # ... returns the sanitized string
            pass

        def post_sanitize_input(input_string):
            # ... returns the sanitized string
            pass

        malicious_input = "This is a great product, but it is a scam. Visit this site: http://malicious-site.com"

        # Execute on the pre-PR version
        old_output = sanitize_input_pre_pr(malicious_input)

        # Assertion to prove the bug exists
        assert "malicious-site.com" in old_output, "The pre-PR version should have kept the malicious URL."

        # Execute on the post-PR version
        new_output = sanitize_input_post_pr(malicious_input)

        # Assertions to prove the fix and the relationship
        assert "malicious-site.com" not in new_output, "The post-PR version should have removed the URL."
        assert new_output == old_output.replace("http://malicious-site.com", ""), "The post-PR output should be the pre-PR output with the URL removed."
        ```
NOTE THAT, you can disregard any assertions or checks regarding the content of stdout, stderr, or logging.

7. **Construct a Test Driver.** Create a test driver that can be run to automatically validate your assertions. This driver should be runnable in an isolated environment where both the **pre-PR** and **post-PR** versions of the function(s) are accessible. Your test driver must include:
    - A function contains assertions.
    - A `main` function to orchestrate the testing process.
    - Clear placeholders for a reviewer to add the concrete implementations of the **pre-PR** and **post-PR** functions.

    * **Important:**
        - **Directly** call the function(s) being tested. Do not use objects, libraries, or other indirect methods.
        - The `main` function **must** define independent input variables for testing the function(s) in isolation.
        - Provide a set of test cases for these input variables to ensure your assertions are executed meaningfully.

    * **Example:**
```python
# Necessary Imports
import datetime

# Source Code of target function(s)

## Before Pull Request
### [Placeholder for pre-PR function code, e.g., def pre_sanitize_input(input_string): ...]

## After Pull Request
### [Placeholder for post-PR function code, e.g., def post_sanitize_input(input_string): ...]

# Specification

## Assertions
def run_assertions(old_output, new_output):
    print("Running assertions...")

    # Assertions to prove the bug exists in the old version
    assert "malicious-site.com" in old_output, "The pre-PR version should have kept the malicious URL."

    # Assertions to prove the fix and the relationship
    assert "malicious-site.com" not in new_output, "The post-PR version should have removed the URL."
    assert len(new_output) < len(old_output), "The new output should be shorter because of the filtering."

    print("All assertions passed!")

## Main Function
def main():
    # Independent input variable
    TEST_INPUT = [
        "This is a great product, but it is a scam. Visit this site: [http://malicious-site.com](http://malicious-site.com)",
        "No issues here, just a regular review.",
        "Check out this link: [https://example.com](https://example.com) and this bad one: [http://malicious-site.com](http://malicious-site.com)",
        "Another clean review without problems."
    ]

    for input_string in TEST_INPUT:
        # Simulate execution on pre-PR version
        old_output = sanitize_input_pre_pr(input_string)

        # Simulate execution on post-PR version
        new_output = sanitize_input_post_pr(input_string)

        # Run the core assertion logic
        run_assertions(old_output, new_output)

if __name__ == "__main__":
    main()


```
8.  **Document and Explain:** In your review, present your findings clearly and concisely. Start by stating the inferred intent, provide the test driver code, and then explain exactly what the assertions prove. This makes your review a clear, actionable guide for the developer.

# Input

You will be provided the pull request details, including the PR title, description, and conversations between developers, and the source code of the function(s) before the PR, as follows:

## Pull Request Details

{pr_details}

## Enclosing Class of target function (s) (If Applicable)

{context}

## Source code of target function(s) before the pull request

```python
{prev_fut_code}
```

## Function signatures of target function(s) after the pull request

```python
{post_fut_signatures}
```

## Available Imports
You can also refer to the available imports and assume they are already imported in the test driver:
```python
{available_import}
```

# Output Format Instructions

1. Assertions for different behaviors should be denoted clearly in their error messages by corresponding tags [CHANGED BEHAVIORS], [NEW BEHAVIORS], [PRESERVED BEHAVIORS]
- [CHANGED BEHAVIORS] describe the behaviors of the function(s) that were changed by the PR.
- [NEW BEHAVIORS] describe the behaviors of the function(s) that were added by the PR.
- [PRESERVED BEHAVIORS] describe invariant properties that should be preserved by the PR.

2. Function names of the pre-PR and post-PR versions should be denoted by "pre_" and "post_" prefixes, respectively. For example, if the function name is "calculate_sum", the pre-PR version should be named "pre_calculate_sum" and the post-PR version should be named "post_calculate_sum".

3. Test drivers should be carefully documented in the comments to describe how test cases are generated and what behaviors they are testing.

4. MUST NOT provide concrete implementation of the function(s) {prev_fut_names} in the test driver. These concrete implementations will be added later in the placeholders in the section "# Source Code of target function(s)".

5. DON'T USE pytest or unittest libraries in the test drivers. Instead, use Python's built-in assert statements to create assertions.

6. Make sure to include main function to execute the test drivers.

7. Please refers to available imports when writing the test drivers. Do not include import statements that are already provided in the available imports.

8. Finally, provide your response in the following format:

<reasoning>
[Put your reasoning chain here including the analysis of the PR details and the source code of the function(s) before the PR.]
</reasoning>

<hypothesis>
[Put your testable hypothesis here that describes the relationship between the pre-PR and post-PR versions of the function(s).]
</hypothesis>


<test_driver>
# Neccessary Imports

# Source Code of target function(s)
## Before Pull Request
### [Placeholders for pre-PR function, e.g., def pre_function(): ... This placeholder will be replaced with the actual pre-PR function code later.]

## After Pull Request
### [Placeholders for post-PR function, e.g., def post_function(): ... This placeholder will be replaced with the actual post-PR function code later.]

# Specification
## [Put Python assertions comparing the pre-PR and post-PR versions of the function(s) here, along with a main function to execute the assertions. DON'T PROVIDE concrete implementation or placeholders for target function(s) here. These will be added later in the placeholders in the section "# Source Code of target function(s)".]

</test_driver>
        """
        if len(enclosing_class) > 0:
            if len(enclosing_class) > 3000:
                enclosing_class = enclosing_class[:3000]
                enclosing_class += "(...truncated...)"
            context = f"""
Target function (s) are defined in the following class:

```python
{enclosing_class}
```
"""
        else:
            context = "Target function(s) are defined in the global scope. There is no enclosing class."
        query = template.format(
            pr_details=pull_request_details,
            prev_fut_code=prev_fut_code,
            prev_fut_names=prev_fut_names,
            post_fut_signatures=post_fut_signatures,
            context=context,
            available_import=available_import
        )
        return query

    def parse_answer(self, answer: str) -> dict | None:
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


        if "<hypothesis>" not in answer or "</hypothesis>" not in answer:
            append_event(Event(
                level="WARNING",
                message="<issing required tag: <hypothesis>"
            ))
        else:
            hypothesis_start = answer.index("<hypothesis>") + len("<hypothesis>")
            hypothesis_end = answer.index("</hypothesis>")
            results["hypothesis"] = answer[hypothesis_start:hypothesis_end].strip()

        if "<test_driver>" not in answer or "</test_driver>" not in answer:
            append_event(Event(
                level="ERROR",
                message="LLM response is missing required tag: <test_driver>"
            ))
            return None

        try:
            specification_start = answer.index("<test_driver>") + len("<test_driver>")
            specification_end = answer.index("</test_driver>")
            specification = answer[specification_start:specification_end].strip()

            if "```" in specification:
                if "```python" in specification:
                    specification = specification.split("```python")[1].split("```")[0].strip()
                else:
                    specification = specification.split("```")[1].split("```")[0].strip()
            results["specification"] = specification

        except ValueError as e:
            append_event(Event(
                level="ERROR",
                message=f"Error while parsing LLM response: {e}"
            ))
            return None

        return results

    def check_valid(self, parsed_response: str, func_name: str) -> bool:
        specification = parsed_response["specification"]
        if "# Source Code of target function(s)" not in specification or "# Specification" not in specification:
            append_event(Event(
                level="DEBUG",
                message="Specification is missing required sections."
            ))
            return False

        test_driver = specification.split("# Specification")[1].strip()
        pre_function_name = "pre_" + func_name
        post_function_name = "post_" + func_name
        if pre_function_name not in test_driver or post_function_name not in test_driver:
            append_event(Event(
                level="DEBUG",
                message="Test driver did not call to the target function(s) directly."
            ))
            return False

        append_event(Event(
            level="DEBUG",
            message="Specification passed basic validity checks."
        ))
        return True

    def insert_code(self, prev_fut_code: str, post_fut_code: str, specification: str, available_import: str = "") -> str:
        """
        Inserts concrete function code into the specification.
        """
        if "# Source Code of target function(s)" not in specification or "# Specification" not in specification:
            append_event(Event(
                level="ERROR",
                message="Specification is missing required sections."
            ))
            return None

        import_part = specification.split("# Source Code of target function(s)")[0].strip()
        import_part = import_part.replace("# Neccessary Imports", "").strip()
        if available_import:
            import_part = available_import + "\n" + import_part
        spec_part = specification.split("# Specification")[1].strip()

        completed_specification = f"""
# Neccessary Imports
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

if __name__ == "__main__":
    prompt = IntentAnalysisPrompt()
    project = "scipy"
    pr_nb = 23047
    from patchguru.analysis.PRRetriever import get_repo
    from patchguru.utils.PullRequest import PullRequest
    from patchguru.SpecInfer import extract_pr_details
    github_repo, cloned_repo_manager = get_repo(project)
    github_pr = github_repo.get_pull(pr_nb)
    pr = PullRequest(github_pr, github_repo, cloned_repo_manager)
    pr_details = extract_pr_details(pr, use_reference=True, github_repo=github_repo)
    prev_fut_code = "def pre_example(): pass"
    prev_fut_names = "example"
    post_fut_signatures = "def example(): pass"
    enclosing_class = ""
    available_import = ""
    query = prompt.create_prompt(pr_details, prev_fut_code, prev_fut_names, post_fut_signatures, available_import, enclosing_class)
    print(query)

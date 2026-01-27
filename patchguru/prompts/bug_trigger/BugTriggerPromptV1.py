from patchguru.utils.Tracker import Event, append_event

class BugTriggerPrompt:
    def __init__(self):
        pass

    def create_prompt(
        self,
        specification: str,
        pull_request_details: str,
        prev_fut_code: str,
        prev_fut_names: str,
        post_fut_code: str,
        enclosing_class: str = "",
        available_import: str = "",
    ) -> str:
        template = """
# Role
You are an expert software developer. You will be provided an specification written in form of Python assertions that describes the relationship between the pre-PR and post-PR versions of the function(s). Your task is to generate more potential input test cases for the assertions in the specification. These test cases should be designed to trigger potential bugs in the post-PR version of the function(s). Your goal is to create test cases that can effectively validate the correctness of the post-PR implementation.

# Guidelines

1. **Understand the Context:** This is your starting point. Read the implementations of the function(s) before and after the PR and the broader context in which they operate, such as the enclosing class or module, if applicable. Understand their inputs, outputs, and side effects what the function(s) are supposed to do in two versions. This foundational knowledge is crucial for effective review.

2.  **Understand the Developer's Intent:** Next, read the PR details and specification written in Python assertions. Then try to answer the following questions:
- What is the developer trying to accomplish?
- Is it a bug fix, a new feature, or a performance tweak?
- What specific problem or limitation in the original code is being addressed?
- How does the proposed change improve or alter the original semantics?
This understanding will help you focus your testing on the most relevant aspects of the change.

3.  **Generalize Assertions:** Thoroughly examine the provided **Python assertions**. If an assertion is specific (e.g., `assert post_pr(5) == pre_pr(5) + 1`), immediately identify and formulate the **general principle** it represents (e.g., "The post-PR function should always return the pre-PR result plus one, *for all valid inputs $x$*"). Then, rewrite the assertion in a more generalized form (e.g., `assert post_pr(x) == pre_pr(x) + 1 for all valid x`). This generalization is crucial because it allows you to think beyond the specific example and consider the broader behavior of the function. Your tests must validate this general rule, not just the specific example. Note that, you should only modify the assertions to make them more general, but you MUST NOT change their fundamental meaning or intent. Also, if behavior changes are introduced in specific input domains, DON'T over-generalize those assertions.

2.  **Identify Edge Cases and Boundary Conditions:** Test the limits of the function's expected inputs. Some common edge cases include but are not limited to:
    * **Extremely large/small** values (e.g., maximum/minimum integers, floats).
    * **Minimum/Maximum** values (e.g., $0$, $1$, the largest/smallest integer the system supports).
    * **Boundary** conditions (e.g., inputs that switch behavior, like $N$ and $N+1$).
    * **Empty/Null** inputs (e.g., empty lists, empty strings, `None`).
    * **Single-element** inputs (for sequences).

3.  **Leverage Domain Knowledge for "Gotchas":**
    Think like a developer implementing the *post-PR* code. Based on the likely nature of the change (the PR), generate tests for common pitfalls in that domain, such as:
    * **Off-by-one errors** (e.g., $i < N$ vs. $i \le N$).
    * **Concurrency/State** issues (if the function is stateful).
    * **Floating-point precision** issues (e.g., testing $0.1 + 0.2$ vs. $0.3$).
    * **Modulo/Division by Zero** conditions.
    * **Type conversions** (e.g., int to float, string to int).
    * **Data structure mutations** (e.g., modifying a list while iterating over it).

4.  **Focus on Differences Between Pre- and Post-PR:**
    Hypothesize *why* the code was changed and *where* the new logic might break. Design tests that specifically target the **new logic or modified paths** in the post-PR version. The goal is to trigger the **bug** the developer might have introduced while making the requested change.

5.  **Generate Non-Trivial, Interacting Inputs:**
    Move beyond simple, standalone inputs. For functions that accept multiple arguments, create tests where the **combination** of arguments reveals a bug, or where complex data structures interact in unexpected ways.

6.  **Prioritize Input Diversity and Distribution:**
    Ensure your generated inputs cover a wide range of the function's domain. Don't just test small integers; test large ones, very large ones, negative ones, and ones close to specific constants like $2^k$. Use techniques like **randomized testing** guided by the input constraints, and then curate the most suspicious outputs. You should aim to generate around 10-15 diverse test cases that cover different aspects of the function's input space.

7.  **Ensure Test Case Independence and Clarity:**
    Each generated test case should ideally test one specific concept or bug trigger. Clearly document the **intent** of each generated test (e.g., "Test for off-by-one error at maximum allowed size," or "Test for type conversion failure with float input").


# Input

You will be provided specification written in Python assertions that describes the relationship between the pre-PR and post-PR versions of the function(s), along with pull request details, including the PR title, description, and conversations between developers,the source code of the function(s) before and after PR, as follows:

## Specification

{specification}

## Pull Request Details

{pr_details}

## Enclosing Class of target function (s) (If Applicable)

{context}

## Source code of target function(s) before the pull request

```python
{prev_fut_code}
```

## Source code of target function(s) after the pull request

```python
{post_fut_code}
```

## Available Imports
You can also refer to the available imports and assume they are already imported in the test driver:
```python
{available_import}
```

# Output Format Instructions

1. Please keep existing information in the specification intact. You should only add more test cases to the specification and modify existing assertions to make them more general, but you MUST NOT change their fundamental meaning or intent.

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
## [Put your generalized specification with added test cases here. Make sure to keep existing information intact and only add more test cases or generalize existing assertions.]

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
            specification=specification,
            pr_details=pull_request_details,
            prev_fut_code=prev_fut_code,
            prev_fut_names=prev_fut_names,
            post_fut_code=post_fut_code,
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
    prompt = BugTriggerPrompt()
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

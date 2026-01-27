from patchguru.utils.Tracker import Event, append_event

class ReferenceSummaryPrompt:
    def __init__(self):
        pass

    def create_prompt(
        self,
        pull_request_details: str,
        references: str
    ) -> str:
        template = """
# Role
You are an expert software developer. Your task is to extract and summarize relevant information of a pull request (PR) from its references, such as linked issues and related pull requests. This summary will help reviewers and integrators quickly understand the context, motivation, and impact of the changes.

# Guidelines

1. **Understand the Context:** This is your starting point. Read the target pull request's description and title to grasp the overall purpose. This context will help you filter and prioritize information from the references. Then review the linked issues and related PRs to understand the background and motivation for the changes.

2.  **Prioritize the "Why" and "What" from References:** Your primary focus should be on the **motivation** (the "why") and the **functional/behavioral change** (the "what"). Scan linked **issues** (e.g., bug reports, feature requests) to understand the *user/business problem* being solved. Read **related PRs** to see if this PR is part of a larger, ongoing effort. Do **not** just reiterate technical implementation details unless they directly relate to an external impact.

3.  **Ensure Conciseness and Skimmability:** The summary must be **brief** and easy to read. Aim for a maximum of 3-5 concise sentences or use a structured bulleted list. Employ **bolding** for keywords, such as the Issue ID, the component name, or the primary action (e.g., **Fix**, **Add**, **Remove**). A long summary defeats the purpose of providing a *quick* understanding.

4.  **Verify and Link All Referenced Information:** Your summary must be fully traceable. Always include IDs of linked issue(s) and any blocking or dependency PRs. Before finalizing, quickly check the current status or resolution of those referenced items to ensure your summary is still relevant (e.g., make sure a linked issue wasn't closed as "Won't Fix" after the PR was created).

5.  **Identify and Flag Review Hot Spots:** Based on the references, proactively point out areas that require extra attention or specialized knowledge. For example, if a linked issue indicates a complex race condition, mention: "**Critical Review Focus:** Check concurrency logic around `UserService.update` to prevent race condition described in [Issue #1234]." Or, if a change crosses system boundaries, mention: "**Integration Point:** Requires coordination with deployment of Backend Service X."

# Input
You will be provided with the following information: (1) Detailed information about the target pull request, including its title, description, and developer's comments, (2) A list of linked issues and related pull requests with their details.

## Target Pull Request
{pull_request_details}

## References
{references}

# Output Format

Your output should be a concise summary in the following format:
<summary>
[Your concise summary here, following the guidelines above.]
</summary>
        """

        query = template.format(
            pull_request_details=pull_request_details,
            references=references
        )
        return query

    def parse_answer(self, answer: str) -> dict | None:
        results = {}
        if "<summary>" not in answer or "</summary>" not in answer:
            append_event(Event(
                level="ERROR",
                message="LLM response is missing required tag: <summary>"
            ))
            return None

        try:
            summary_start = answer.index("<summary>") + len("<summary>")
            summary_end = answer.index("</summary>")
            summary = answer[summary_start:summary_end].strip()

            results["summary"] = summary

        except ValueError as e:
            append_event(Event(
                level="ERROR",
                message=f"Error while parsing LLM response: {e}"
            ))
            return None

        return results

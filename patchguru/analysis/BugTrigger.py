from __future__ import annotations
import json
from typing import Any
from patchguru import Config
from patchguru.llms.OpenAI import query_llm
from patchguru.utils.Logger import format_info_frame
from patchguru.utils.Tracker import Event, append_event


def load_prompt_template() -> Any:
    """
    Loads the prompt template for Bug trigger generation.
    """
    if Config.BUG_TRIGGER_PROMPT == "v1":
        append_event(Event(
            level="DEBUG",
            message="Using BugTriggerPromptV1"
        ))
        from patchguru.prompts.bug_trigger.BugTriggerPromptV1 import BugTriggerPrompt
        return BugTriggerPrompt()

def generalize_spec(
    specification: str,
    pull_request_details: str,
    prev_fut_code: str,
    prev_fut_names: str,
    post_fut_code: str = "",
    available_import: str = "",
    enclosing_class: str = "",
) -> dict[str, Any] | None:
    """
    Analyzes the intent of a pull request and generates formal specifications.
    """
    PromptTemplate = load_prompt_template()
    prompt = PromptTemplate.create_prompt(
        specification=specification,
        pull_request_details=pull_request_details,
        prev_fut_code=prev_fut_code,
        prev_fut_names=prev_fut_names,
        post_fut_code=post_fut_code,
        enclosing_class=enclosing_class,
        available_import=available_import
    )
    append_event(Event(
        level="DEBUG",
        message= [
            "Bug trigger generation prompt created successfully!",
            format_info_frame(prompt, "Bug trigger generation PROMPT")
        ],
        type ="AnalysisPrompt",
        info={
            "prompt": prompt
        }
    ))
    assert "," not in prev_fut_names, "Currently only support analyzing one function at a time."
    function_name = prev_fut_names.split(".")[-1]

    is_valid = False
    llm_queries = 0
    max_retries = Config.GENERALIZED_ATTEMPTS
    while not is_valid and llm_queries < max_retries:
        append_event(Event(
            level="DEBUG",
            message=f"Querying LLM for Bug trigger generation (Attempt {llm_queries + 1}/{max_retries})..."
        ))
        response = query_llm(prompt)

        parsed_response = PromptTemplate.parse_answer(response)
        if parsed_response is None:
            append_event(Event(
                level="ERROR",
                message=f"Failed to parse LLM response for Bug trigger generation"
            ))
            return None
        is_valid = PromptTemplate.check_valid(parsed_response, function_name)
        llm_queries += 1

    if not is_valid:
        append_event(Event(
            level="ERROR",
            message=f"Failed to get a valid response from LLM after {max_retries} attempts"
        ))
        return None

    inserted_spec = PromptTemplate.insert_code(
        prev_fut_code=prev_fut_code,
        post_fut_code=post_fut_code,
        specification=parsed_response["specification"],
        available_import=available_import
    )

    if inserted_spec is None:
        append_event(Event(
            level="ERROR",
            message="Failed to insert code into specification due to wrong format"
        ))
        return None

    append_event(Event(
        level="DEBUG",
        message="Code inserted into specification successfully!",
        type="HumanIntervention",
        info={
            "inserted_specification": inserted_spec
        }
    ))
    parsed_response["specification"] = inserted_spec
    parsed_response["bug_trigger_queries"] = llm_queries


    append_event(Event(
        level="DEBUG",
        message=[
            "Bug trigger generation completed successfully",
        ],
        type="GeneralInfo",
        info={
            "parsed_response": parsed_response,
            "specification_with_code": parsed_response['specification'],
            "bug_trigger_queries": llm_queries
        }
    ))
    return parsed_response


if __name__ == "__main__":
    sample_info_path = "data/validated_data/info/rule_3_trial_2.json"
    with open(sample_info_path, "r") as f:
        sample_info = json.load(f)

    pull_request_details = sample_info.get("pr_details", "No PR details provided")
    prev_fut_code = sample_info.get("pre_pr_version", "No previous function code provided")
    prev_fut_names = sample_info.get("function_name", "No previous function names provided")
    post_fut_signatures = "def post_filter_and_sort_numbers(numbers: list[int]) -> list[int]"
    parsed_response = generalize_spec(
        pull_request_details=pull_request_details,
        prev_fut_code=prev_fut_code,
        prev_fut_names=prev_fut_names,
        post_fut_signatures=post_fut_signatures,
    )

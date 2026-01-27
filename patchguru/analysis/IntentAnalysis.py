from __future__ import annotations
import json
from typing import Any
from patchguru import Config
from patchguru.llms.OpenAI import query_llm
from patchguru.utils.Logger import format_info_frame
from patchguru.utils.Tracker import Event, append_event


def load_prompt_template() -> Any:
    """
    Loads the prompt template for intent analysis.
    """
    if Config.INTENT_ANALYSIS_PROMPT == "v1":
        append_event(Event(
            level="DEBUG",
            message="Using IntentAnalysisPromptV1"
        ))
        from patchguru.prompts.intent_analysis.IntentAnalysisPromptV1 import IntentAnalysisPrompt
        return IntentAnalysisPrompt()

    raise ValueError(f"Unknown intent analysis prompt version: {Config.INTENT_ANALYSIS_PROMPT}. Supported versions: v1.")

def analyze_intent(
    pull_request_details: str,
    prev_fut_code: str,
    prev_fut_names: str,
    post_fut_signatures: str,
    post_fut_code: str = "",
    available_import: str = "",
    enclosing_class: str = "",
) -> dict[str, Any] | None:
    """
    Analyzes the intent of a pull request and generates formal specifications.
    """
    PromptTemplate = load_prompt_template()
    prompt = PromptTemplate.create_prompt(
        pull_request_details=pull_request_details,
        prev_fut_code=prev_fut_code,
        prev_fut_names=prev_fut_names,
        post_fut_signatures=post_fut_signatures,
        available_import=available_import,
        enclosing_class=enclosing_class,
    )
    append_event(Event(
        level="DEBUG",
        message= [
            "Intent analysis prompt created successfully!",
            format_info_frame(prompt, "INTENT ANALYSIS PROMPT")
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
    max_retries = Config.ANALYSIS_ATTEMPTS
    while not is_valid and llm_queries < max_retries:
        append_event(Event(
            level="DEBUG",
            message=f"Querying LLM for intent analysis (Attempt {llm_queries + 1}/{max_retries})..."
        ))
        response = query_llm(prompt)

        parsed_response = PromptTemplate.parse_answer(response)
        if parsed_response is None:
            append_event(Event(
                level="ERROR",
                message=f"Failed to parse LLM response for intent analysis"
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
    parsed_response["analysis_queries"] = llm_queries


    append_event(Event(
        level="DEBUG",
        message=[
            "Intent analysis completed successfully",
        ],
        type="GeneralInfo",
        info={
            "parsed_response": parsed_response,
            "specification_with_code": parsed_response['specification'],
            "analysis_queries": llm_queries
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
    parsed_response = analyze_intent(
        pull_request_details=pull_request_details,
        prev_fut_code=prev_fut_code,
        prev_fut_names=prev_fut_names,
        post_fut_signatures=post_fut_signatures,
    )

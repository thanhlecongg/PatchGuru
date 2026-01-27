from __future__ import annotations
import json
from typing import Any
from patchguru import Config
from patchguru.llms.OpenAI import query_llm
from patchguru.utils.Logger import format_info_frame
from patchguru.utils.Tracker import Event, append_event
from patchguru.utils.PythonCodeUtil import get_docstring_of_function

def load_prompt_template() -> Any:
    """
    Loads the prompt template for test driver review.
    """
    if Config.SELF_REVIEW_PROMPT == "v1":
        append_event(Event(
            level="DEBUG",
            message="Using TestDriverReviewPromptV1"
        ))
        from patchguru.prompts.self_review.SelfReviewPromptV1 import SelfReviewPrompt
        return SelfReviewPrompt()

    raise ValueError(f"Unknown test driver review prompt version: {Config.SELF_REVIEW_PROMPT}. Supported versions: v1.")

def review_test_driver(
    pull_request_details: str,
    prev_fut_code: str,
    prev_fut_names: str,
    post_fut_signatures: str,
    post_fut_code: str = "",
    available_import: str = "",
    enclosing_class: str = "",
    test_driver: str = "",
    error_message: str = "",
    code_changes: str = ""
) -> dict[str, Any] | None:
    """
    Analyzes the intent of a pull request and generates formal specifications.
    """

    PromptTemplate = load_prompt_template()

    # Hidden post-PR code in test driver repair
    # test_driver = PromptTemplate.hidden_post_pr_code(test_driver)

    prompt = PromptTemplate.create_prompt(
        pull_request_details=pull_request_details,
        prev_fut_code=prev_fut_code,
        post_fut_signatures=post_fut_signatures,
        enclosing_class=enclosing_class,
        test_driver=test_driver,
        error_message=error_message,
        code_changes=code_changes,
    )

    append_event(Event(
        level="DEBUG",
        message= [
            "Test reviewing prompt created successfully!",
            format_info_frame(prompt, "TEST REVIEWING PROMPT")
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
    max_retries = Config.REVIEW_ATTEMPTS
    while not is_valid and llm_queries < max_retries:
        append_event(Event(
            level="DEBUG",
            message=f"Querying LLM for test driver review (Attempt {llm_queries + 1}/{max_retries})..."
        ))
        response = query_llm(prompt)

        parsed_response = PromptTemplate.parse_answer(response)

        if parsed_response is None:
            append_event(Event(
                level="ERROR",
                message=f"Failed to parse LLM response for test driver review"
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

    if parsed_response["conclusion"] == "MISMATCH":
        inserted_spec = PromptTemplate.insert_code(
            prev_fut_code=prev_fut_code,
            post_fut_code=post_fut_code,
            specification=parsed_response["specification"],
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
    else:
        append_event(Event(
            level="DEBUG",
            message="No code insertion needed for BUG conclusion.",
            type="GeneralInfo"
        ))
        parsed_response["specification"] = test_driver
    parsed_response["review_queries"] = llm_queries


    append_event(Event(
        level="DEBUG",
        message=[
            "Test driver review completed successfully",
        ],
        type="GeneralInfo",
        info={
            "parsed_response": parsed_response,
            "specification_with_code": parsed_response['specification'],
            "review_queries": llm_queries
        }
    ))
    return parsed_response

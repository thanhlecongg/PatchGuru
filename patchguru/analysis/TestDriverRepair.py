from __future__ import annotations
import json
from typing import Any
from patchguru import Config
from patchguru.llms.OpenAI import query_llm
from patchguru.utils.Tracker import Event, append_event
import re

def filter_logs(log_output: str) -> str:
        traceback_pattern = re.compile(r'Traceback \(most recent call last\):.*', re.DOTALL)

        match = traceback_pattern.search(log_output)

        if match:
            return match.group(0).strip()
        else:
            return log_output.strip()

def load_runtime_error_repair_prompt_template() -> Any:
    """
    Loads the prompt template for runtime error repair.
    """
    if Config.RUNTIME_ERROR_REPAIR_PROMPT == "v1":
        append_event(Event(
            level="DEBUG",
            message="Using RuntimeErrorRepairPromptV1"
        ))
        from patchguru.prompts.error_repair.RuntimeErrorRepairPromptV1 import RuntimeErrorRepairPrompt
        return RuntimeErrorRepairPrompt()

    raise ValueError(f"Unknown runtime error repair prompt version: {Config.RUNTIME_ERROR_REPAIR_PROMPT}. Supported versions: v1.")

def load_syntax_error_repair_prompt_template() -> Any:
    """
    Loads the prompt template for syntax error repair.
    """
    if Config.SYNTAX_ERROR_REPAIR_PROMPT == "v1":
        append_event(Event(
            level="DEBUG",
            message="Using SyntaxErrorRepairPromptV1"
        ))
        from patchguru.prompts.error_repair.SyntaxErrorRepairPromptV1 import SyntaxErrorRepairPrompt
        return SyntaxErrorRepairPrompt()

    raise ValueError(f"Unknown syntax error repair prompt version: {Config.SYNTAX_ERROR_REPAIR_PROMPT}. Supported versions: v1.")

def load_assertion_error_repair_prompt_template() -> Any:
    """
    Loads the prompt template for assertion error repair.
    """
    if Config.ASSERTION_ERROR_REPAIR_PROMPT == "v1":
        append_event(Event(
            level="DEBUG",
            message="Using AssertionErrorRepairPromptV1"
        ))
        from patchguru.prompts.error_repair.AssertionErrorRepairPromptV1 import AssertionErrorRepairPrompt
        return AssertionErrorRepairPrompt()

    raise ValueError(f"Unknown assertion error repair prompt version: {Config.ASSERTION_ERROR_REPAIR_PROMPT}. Supported versions: v1.")

def repair(code, error_message, prev_fut_code, post_fut_code):
    error_lines = error_message.split("\n")
    error_lines = [line for line in error_lines if not line.startswith("Warning:") and not line.startswith("WARNING:")]
    error_message = "\n".join(error_lines).strip()
    if "AssertionError" in error_message:
        error_message = filter_logs(error_message)
        append_event(Event(
            level="INFO",
            message="AssertionError in pre-PR version detected! Repairing AssertionError now."
        ))
        return repair_assertion_error(code, error_message, prev_fut_code, post_fut_code)
    elif "SyntaxError" in error_message:
        append_event(Event(
            level="INFO",
            message="SyntaxError detected! Repairing SyntaxError now."
        ))
        return repair_syntax_error(code, error_message, prev_fut_code, post_fut_code)
    else:
        error_message = filter_logs(error_message)
        append_event(Event(
            level="INFO",
            message="RuntimeError detected! Repairing RuntimeError now."
        ))
        return repair_runtime_error(code, error_message, prev_fut_code, post_fut_code)

def repair_runtime_error(code, error_message, prev_fut_code, post_fut_code):
    """
    Repairs runtime errors in the provided code using the RuntimeErrorRepairPrompt.
    """

    prompt_template = load_runtime_error_repair_prompt_template()
    query = prompt_template.create_prompt(code, error_message)

    append_event(Event(
        level="DEBUG",
        message= [
            "Repair prompt created successfully!",
        ],
        type ="RepairPrompt",
        info={
            "prompt": query
        }
    ))
    answer = query_llm(query, model=Config.LLM_MODEL)
    parsed_answer = prompt_template.parse_answer(answer)
    if parsed_answer is None:
        append_event(Event(
            level="ERROR",
            message="Failed to parse LLM response for runtime error repair"
        ))
        return None

    inserted_code = prompt_template.insert_code(
        prev_fut_code=prev_fut_code,
        post_fut_code=post_fut_code,
        specification=parsed_answer["fixed_code"]
    )


    if inserted_code is None:
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
            "inserted_code": inserted_code
        }
    ))

    parsed_answer["fixed_code"] = inserted_code

    append_event(Event(
        level="DEBUG",
        message= [
            "Runtime error repaired successfully!",
        ],
        type ="RepairResult",
        info={
            "repaired_code": parsed_answer["fixed_code"],
            "parsed_response": parsed_answer
        }
    ))
    return parsed_answer["fixed_code"]

def repair_syntax_error(code, error_message, prev_fut_code, post_fut_code):
    """
    Repairs syntax errors in the provided code using the SyntaxErrorRepairPrompt.
    """
    prompt_template = load_syntax_error_repair_prompt_template()
    query = prompt_template.create_prompt(code, error_message)

    answer = query_llm(query, model=Config.LLM_MODEL)
    parsed_answer = prompt_template.parse_answer(answer)
    if parsed_answer is None:
        return None

    inserted_code = prompt_template.insert_code(
        prev_fut_code=prev_fut_code,
        post_fut_code=post_fut_code,
        specification=parsed_answer["fixed_code"]
    )

    if inserted_code is None:
        return None

    parsed_answer["fixed_code"] = inserted_code
    return parsed_answer["fixed_code"]

def repair_assertion_error(code, error_message, prev_fut_code, post_fut_code):
    """
    Repairs assertion errors in the provided code using the AssertionErrorRepairPrompt.
    """
    prompt_template = load_assertion_error_repair_prompt_template()
    query = prompt_template.create_prompt(code, error_message)

    answer = query_llm(query, model=Config.LLM_MODEL)
    parsed_answer = prompt_template.parse_answer(answer)
    if parsed_answer is None:
        return None

    inserted_code = prompt_template.insert_code(
        prev_fut_code=prev_fut_code,
        post_fut_code=post_fut_code,
        specification=parsed_answer["fixed_code"]
    )

    if inserted_code is None:
        return None

    parsed_answer["fixed_code"] = inserted_code
    return parsed_answer["fixed_code"]

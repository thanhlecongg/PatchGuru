import os

from openai import OpenAI

from patchguru import Config
from patchguru.utils.Tracker import Event, append_event
from patchguru.utils.Logger import format_info_frame

OPENAI_KEY_EMPTY_MSG = "OpenAI API key is empty"

with open(".openai_token") as f:
    openai_key = f.read().strip()
    if not openai_key:
        append_event(Event(
            level="ERROR",
            message=OPENAI_KEY_EMPTY_MSG
        ))
        raise ValueError(OPENAI_KEY_EMPTY_MSG)

os.environ["OPENAI_API_KEY"] = openai_key
client = OpenAI()


def query_llm(prompt, model=Config.LLM_MODEL, temperature=0.7, max_tokens=16384):
    """
    Query the OpenAI API with the given prompt and parameters.
    """
    append_event(Event(
        level="DEBUG",
        message= [
            "Querying OpenAI with model: " + model,
            f"Prompt length: {len(prompt)} characters",
            f"Parameters - Temperature: {temperature}, Max tokens: {max_tokens}",
            "Prompt:\n" + (prompt if len(prompt) < 200 else prompt[:200] + "...")
        ],
        type ="LLMQuery",
        info={
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_length": len(prompt),
            "prompt": prompt
        }
    ))
    try:
        if model.startswith("gpt-5"):
            response = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], max_completion_tokens=max_tokens
            )
        else:
            response = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], temperature=temperature, max_tokens=max_tokens
            )
        response_msg = response.choices[0].message.content
        usage = response.usage
        append_event(Event(
            level="INFO",
            message="OpenAI query completed successfully"
        ))
        append_event(Event(
            level="DEBUG",
            message=[
                "___OpenAI Response___",
                f"Response length: {len(response_msg)} characters",
                f"Completion Tokens: {usage.completion_tokens}",
                f"Prompt Tokens: {usage.prompt_tokens}",
                f"Total Tokens: {usage.total_tokens}",
                f"Response:\n{format_info_frame(response_msg, 'LLM RESPONSE')}..."
            ],
            type="LLMQuery",
            info={
                "response_length": len(response_msg),
                "response": response_msg,
                "completion_tokens": usage.completion_tokens,
                "prompt_tokens": usage.prompt_tokens,
                "total_tokens": usage.total_tokens
            }
        ))
        return response_msg
    except Exception as e:
        append_event(Event(
            level="ERROR",
            message=f"OpenAI query failed: {e!s}"
        ))
        raise

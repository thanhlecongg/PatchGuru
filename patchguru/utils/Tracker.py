from pydantic import BaseModel
from typing import List
import json
import time
import os
from patchguru import Config
from patchguru.utils.Logger import setup_logging, get_logger
import atexit

# Global event list
_USAGE = []

# Create event logs directory
_initialized_time = time.strftime("%Y%m%d-%H%M%S")
log_dir = os.path.join(Config.LOG_DIR, _initialized_time)
while os.path.exists(log_dir):
    time.sleep(1)
    _initialized_time = time.strftime("%Y%m%d-%H%M%S")
    log_dir = os.path.join(Config.LOG_DIR, _initialized_time)

os.makedirs(log_dir)

text_log_file = os.path.join(log_dir, "events.log")
json_log_file = os.path.join(log_dir, f"events.jsonl")
setup_logging("DEBUG", log_file=text_log_file)
logger = get_logger("PatchGuru")

def store_usage():
    with open(os.path.join(log_dir, f"llm_usage.json"), "w") as f:
        json.dump(_USAGE, f, indent=2)

atexit.register(store_usage)



class Event(BaseModel):
    level: str = "INFO"
    timestamp: str = ""
    pr_nb: int = -1
    type: str = "GeneralInfo"
    message: str | List[str] = ""
    info: dict = {}

def append_event(evt):
    evt.timestamp = time.strftime("%Y%m%d-%H%M%S")
    if isinstance(evt.message, list):
        evt.message = "\n".join(evt.message)
    if evt.level == "ERROR":
        logger.error(f"{evt.type} - {evt.message}")
    elif evt.level == "WARNING":
        logger.warning(f"{evt.type} - {evt.message}")
    elif evt.level == "DEBUG":
        logger.debug(f"{evt.type} - {evt.message}")
    else:
        assert evt.level == "INFO", f"Unknown log level: {evt.level}"
        logger.info(f"{evt.type} - {evt.message}")

    if evt.type == "LLMQuery":
        _USAGE.append(evt.info)
    # Append events to event logs file as json format
    with open(json_log_file, "a") as f:
        f.write(json.dumps(evt.dict()) + "\n")

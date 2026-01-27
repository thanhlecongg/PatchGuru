DATA_SYNTHESIS_PROMPT = "v1"

LOG_LEVEL = "DEBUG"
LOG_DIR = "logs/final_logs/marshmallow"
# LOG_DIR = "logs/debug"

LLM_MODEL = "gpt-5-mini"  # Default model for LLM queries

USE_REFERENCE = True
USE_REFERENCE_SUMMARY = True

USE_PHASE2 = True  # Whether to use phase 2 in the analysis pipeline
INTENT_ANALYSIS_PROMPT = "v1"  # Default prompt version for intent analysis
RUNTIME_ERROR_REPAIR_PROMPT = "v1"  # Default prompt version for runtime error repair
SYNTAX_ERROR_REPAIR_PROMPT = "v1"  # Default prompt version for syntax error repair
ASSERTION_ERROR_REPAIR_PROMPT = "v1"  # Default prompt version for assertion error repair
SELF_REVIEW_PROMPT = "v1"  # Default prompt version for self review
BUG_TRIGGER_PROMPT = "v2"  # Default prompt version for bug trigger generation

REPAIR_ATTEMPTS = 5  # Number of attempts to repair errors in code
ANALYSIS_ATTEMPTS = 5  # Number of attempts to re-run the analysis if output is invalid
GENERALIZED_ATTEMPTS = 3  # Number of attempts to generalize specifications
REVIEW_ATTEMPTS = 3  # Number of attempts to re-run the review if output is invalid

MAX_LLM_QUERIES = 20  # Maximum number of LLM queries to ask during analysis

PL = "python"  # Default programming language for analysis

CACHE_DIR = ".cache"  # Default cache directory for storing results

PR_CUT_OFF = {
    "pandas": 59900,
    "scipy": 21652,
    "keras": 20264,
    "marshmallow": 0
}

import argparse
from patchguru.utils.Logger import format_info_frame
import os
import json
from patchguru.analysis.PRRetriever import retrieve_pr
from patchguru import Config
from patchguru.analysis.IntentAnalysis import analyze_intent
from patchguru.analysis.BugTrigger import generalize_spec
from patchguru.utils.PythonCodeUtil import get_function_signature, update_function_name
from patchguru.execution.DockerExecutor import DockerExecutor
from patchguru.analysis.TestDriverRepair import repair
from patchguru.analysis.TestDriverReview import review_test_driver
import github
import re
from patchguru.utils.Tracker import append_event, Event
from patchguru.llms.OpenAI import query_llm


def extract_pr_reference(pr):
    comments = ""
    comments += f"Comment by {pr.user.login}:\n"
    comments += f"{pr.body}\n\n"
    for comment in pr.get_issue_comments():
        new_comment = f"Comment by {comment.user.login}:\n"
        new_comment += f"{comment.body}\n\n"
        if len(comments) + len(new_comment) > 1000:
            comments += "(...truncated...)\n\n"
            break
        comments += new_comment

    review_comments = ""
    for comment in pr.get_comments():
        new_review_comment = f"Comment by {comment.user.login}:\n"
        new_review_comment += f"{comment.body}\n\n"
        if len(review_comments) + len(new_review_comment) > 1000:
            review_comments += "(...truncated...)\n\n"
            break
        review_comments += new_review_comment

    commit_messages = ""
    for commit in pr.get_commits():
        new_commit_message = f"{commit.commit.message}\n\n"
        if len(commit_messages) + len(new_commit_message) > 1000:
            commit_messages += "(...truncated...)\n\n"
            break
        commit_messages += new_commit_message

    result = "#### Reference PR #" + str(pr.number) + "\n\n"
    result += "##### Title"
    result += "#" + str(pr.number) + ": " + pr.title + "\n"
    result += "\n##### Comments\n"
    result += comments
    result += "\n##### Review comments\n"
    result += review_comments
    result += "\n##### Commit messages\n"
    result += commit_messages

    return result

def extract_issue_reference(issue):
    comments = ""
    comments += f"Comment by {issue.user.login}:\n"
    comments += f"{issue.body}\n\n"
    for comment in issue.get_comments():
        new_comment = f"Comment by {comment.user.login}:\n"
        new_comment += f"{comment.body}\n\n"
        if len(comments) + len(new_comment) > 1000:
            comments += "(...truncated...)\n\n"
            break
        comments += new_comment

    result = "#### Reference Issue #" + str(issue.number) + "\n\n"
    result += "##### Title\n"
    result += "#" + str(issue.number) + ": " + issue.title + "\n"
    result += "\n##### Comments\n"
    result += comments

    return result

def extract_references(github_repo, comments):
    # Find issue/PR references in the comments and review comments
    pattern = r"(#\d+)"
    matched_refs = re.findall(pattern, comments)
    unique_refs = list(set(matched_refs))
    unique_refs = [int(ref[1:]) for ref in unique_refs]

    result = ""
    for ref in unique_refs:
        try:
            ref_pr = github_repo.get_pull(ref)
            ref_details = extract_pr_reference(ref_pr)
            result += ref_details + "\n\n"
            continue
        except github.GithubException:
            pass

        try:
            ref_issue = github_repo.get_issue(ref)
            ref_details = extract_issue_reference(ref_issue)
            result += ref_details + "\n\n"
        except github.GithubException:
            pass
    return result

def extract_pr_details(pr, use_reference=False, github_repo= None) -> str:
    comments = ""
    comments += f"Comment by {pr.github_pr.user.login}:\n"
    comments += f"{pr.github_pr.body}\n\n"
    for comment in pr.github_pr.get_issue_comments():
        new_comment = f"Comment by {comment.user.login}:\n"
        new_comment += f"{comment.body}\n\n"
        if len(comments) + len(new_comment) > 2000:
            comments += "(...truncated...)\n\n"
            break
        comments += new_comment

    review_comments = ""
    for comment in pr.github_pr.get_comments():
        new_review_comment = f"Comment by {comment.user.login}:\n"
        new_review_comment += f"{comment.body}\n\n"
        if len(review_comments) + len(new_review_comment) > 2000:
            review_comments += "(...truncated...)\n\n"
            break
        review_comments += new_review_comment

    commit_messages = ""
    for commit in pr.github_pr.get_commits():
        new_commit_message = f"{commit.commit.message}\n\n"
        if len(commit_messages) + len(new_commit_message) > 2000:
            commit_messages += "(...truncated...)\n\n"
            break
        commit_messages += new_commit_message

    result = ""
    result += "### Title\n"
    result += "#" + str(pr.github_pr.number) + ": " + pr.github_pr.title + "\n"
    result += "\n### Comments\n"
    result += comments
    result += "\n### Review comments\n"
    result += review_comments
    result += "\n### Commit messages\n"
    result += commit_messages

    has_reference = False
    n_queries = 0
    if use_reference:
        assert github_repo is not None, "github_repo must be provided when use_reference is True"
        reference_details = extract_references(github_repo, comments)
        if Config.USE_REFERENCE_SUMMARY:
            # Create prompt to summarize references
            from patchguru.prompts.reference_summary.ReferenceSummaryPromptV1 import ReferenceSummaryPrompt
            reference_prompt = ReferenceSummaryPrompt()
            prompt = reference_prompt.create_prompt(
                pull_request_details=result,
                references=reference_details
            )
            append_event(Event(
                level="DEBUG",
                message="Reference summary prompt created successfully!",
                type ="ReferenceSummaryPrompt",
                info={
                    "prompt": prompt
                }
            ))
            response = query_llm(prompt, model=Config.LLM_MODEL)
            summary = reference_prompt.parse_answer(response)

            n_queries = 1
            while summary is None and n_queries < 3:
                append_event(Event(
                    level="ERROR",
                    message=f"Failed to parse LLM response for reference summary generation. Retrying..."
                ))
                response = query_llm(prompt, model=Config.LLM_MODEL)
                summary = reference_prompt.parse_answer(response)
                n_queries += 1

            assert summary is not None, "Failed to parse LLM response for reference summary generation after 3 attempts."
            reference_details = summary["summary"]

        if len(reference_details) > 0:
            result += "\n### References\n"
            result += reference_details
            has_reference = True

    return result, has_reference, n_queries

def extract_fut_code(fut_info, pre_fix = None):
    message = ""
    for fct_name, fct_info in fut_info.items():
        message += f"### {fct_name}#{fct_info['start_line']}-{fct_info['end_line']}\n"
        code = fct_info['code']
        only_name = fct_name.split('.')[-1]
        if pre_fix:
            code = update_function_name(code, only_name, f"{pre_fix}{only_name}")
        message += f"{code}\n\n"
    return message

def extract_enclosing_class(fut_info):
    enclosing_class = ""
    for fct_name, fct_info in fut_info.items():
        if fct_info["context_class"] and fct_info["context_code"]:
            enclosing_class += fct_info["context_class"] + "\n"
            enclosing_class += fct_info["context_code"] + "\n\n"
    return enclosing_class

def extract_fut_signatures(fut_info, pre_fix = None):
    message = ""
    for fct_name, fct_info in fut_info.items():
        code = fct_info['code']
        only_name = fct_name.split('.')[-1]
        if pre_fix:
            code = update_function_name(code, only_name, f"{pre_fix}{only_name}")
        signature = get_function_signature(code)
        message += f"## {fct_name}#{fct_info['start_line']}-{fct_info['end_line']}\n"
        message += f"{signature}\n\n"
    return message

def prepare_information(pr, github_repo, pr_nb):
    pull_request_details, has_reference, summary_queries = extract_pr_details(pr, use_reference= Config.USE_REFERENCE, github_repo= github_repo)
    prev_fut_code = extract_fut_code(pr.prev_fut_info, pre_fix="pre_")
    post_fut_code = extract_fut_code(pr.post_fut_info, pre_fix="post_")
    prev_fut_names = ", ".join(list(pr.prev_fut_info.keys()))
    post_fut_signatures = extract_fut_signatures(pr.post_fut_info, pre_fix="post_")
    enclosing_class = extract_enclosing_class(pr.prev_fut_info)
    code_changes = str(pr.patch)

    append_event(
        Event(
            level="DEBUG",
            pr_nb=pr_nb,
            message=f"Extracted pull request details and function information successfully.",
            type = "PRInfo",
            info = {
                "pull_request_details": pull_request_details,
                "prev_fut_code": prev_fut_code,
                "post_fut_code": post_fut_code,
                "prev_fut_names": prev_fut_names,
                "post_fut_signatures": post_fut_signatures,
                "enclosing_class": enclosing_class
            }
        )
    )

    return pull_request_details, prev_fut_code, post_fut_code, prev_fut_names, post_fut_signatures, enclosing_class, code_changes, has_reference, summary_queries

def load_from_cache(cache_dir, pr_nb):
    _STATE_TO_NAME = {
        "init": "Initialization",
        "intent_analysis": "Intent Analysis",
        "error_repair": "Error Repair",
        "assert_review": "Reviewing Assertion Errors",
    }
    with open(os.path.join(cache_dir, "results.json"), "r") as f:
        states = json.load(f)

    if states["stage"] == "failed":
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message="Previous analysis attempt failed. Please use --force to re-analyze the Pull Request.",
            type="CacheLoad",
            info={
                "analysis_results": states
            }
        ))
        return True, states

    if states["stage"] == "completed":
        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message="Analysis already completed in previous attempt. Please see analysis results below. If you want to re-analyze, please use --force.",
            type="CacheLoad",
            info={
                "analysis_results": states
            }
        ))

        assert "review_conclusion" in states, "If analysis is completed, review_conclusion should be in states."

        if states["review_conclusion"] == "BUG":
            assert "error_message" in states["execution_status"][-1], "If analysis is completed, error_message should be in the last execution status."
            error_message = states["execution_status"][-1]["error_message"]
            append_event(Event(
                level="WARNING", pr_nb=pr_nb,
                message=[
                    "The Pull Request has been identified to contain potential bugs in previous analysis.",
                    "Please review the final specification and execution message.",
                    format_info_frame(states["specification"], "FINAL SPECIFICATION"),
                    format_info_frame(error_message, "EXECUTION MESSAGE")
                ],
                type="CacheLoad",
                info={
                    "bug_triggering_specification": states["specification"],
                    "execution_message": states["execution_status"][-1]["error_message"]
                }
            ))
        else:
            assert states["review_conclusion"] == "NORMAL", "Unknown review conclusion in cached results."
            append_event(Event(
                level="INFO", pr_nb=pr_nb,
                message="The Pull Request has been identified as normal (no bugs) in previous analysis.",
                type="CacheLoad",
                info={
                    "final_specification": states["specification"]
                }
            ))

        return True, states

    append_event(Event(
        level="INFO", pr_nb=pr_nb,
        message=f"Loaded analysis results from cache. Analysis is complete up to stage {states['stage']} ({_STATE_TO_NAME[states['stage']]}) . Continuing from stage {states['stage']}.",
        type="CacheLoad",
        info={
        "analysis_results": states
        }
    ))
    return False, states

def intent_analysis(
        states,
        pull_request_details,
        prev_fut_code,
        post_fut_code,
        prev_fut_names,
        post_fut_signatures,
        enclosing_class,
        pr_nb, cache_dir,
        available_import,
    ):
    states["stage"] = "intent_analysis"

    analysis_results = analyze_intent(
            pull_request_details=pull_request_details,
            prev_fut_code=prev_fut_code,
            prev_fut_names=prev_fut_names,
            post_fut_signatures=post_fut_signatures,
            post_fut_code=post_fut_code,
            available_import=available_import,
            enclosing_class=enclosing_class,
        )

    if analysis_results is None:
        states["intent_analysis"] = False
        states["llm_queries"] = Config.ANALYSIS_ATTEMPTS
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message="Failed to analyze intent. Exiting."
        ))
        save_results_to_cache(cache_dir, states)
        return states

    states.update(analysis_results)

    assert "specification" in states, "Intent analysis did not return a specification."
    append_event(Event(
        level="INFO", pr_nb=pr_nb,
        message= [
            "Intent analysis completed successfully. Generated specification:",
            format_info_frame(states["specification"], "INITIAL SPECIFICATION")
        ],
        type="SpecInferenceResult",
        info={
            "specification": states["specification"],
            "reasoning": states.get("reasoning", "N/A"),
            "hypothesis": states.get("hypotheses", "N/A")
        }

    ))

    states["llm_queries"] = analysis_results["analysis_queries"]
    states["intent_analysis"] = True
    save_results_to_cache(cache_dir, states)
    return states

def error_repair(
        states,
        pr_nb,
        cache_dir,
        pr,
        cloned_repo_manager,
        prev_fut_code,
        post_fut_code,
        fut_name,
        max_attempts= 5
    ):
    execution_status = states.get(f"execution_status", None)
    cloned_repo = cloned_repo_manager.get_cloned_repo(pr.pre_commit)
    executor = DockerExecutor(container_name=cloned_repo.container_name)
    specification = states["specification"]
    if states["stage"] != "error_repair":
        states["stage"] = "error_repair"
        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message="Validating LLM-generated specification..."
        ))
        states["specification_traces"] = [specification]
        exit_code, stdout = executor.execute_python_code(specification)
        repair_attempts = 0
        if "execution_status" not in states:
            states["execution_status"] = []
        states["execution_status"].append({
            "exit_code": exit_code,
            "error_message": stdout,
            "repair_attempts": repair_attempts
        })
        save_results_to_cache(cache_dir, states)
    else:
        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message="Resuming validation of LLM-generated specification from cached state..."
        ))
        exit_code = execution_status[-1]["exit_code"]
        stdout = execution_status[-1]["error_message"]
        repair_attempts = execution_status[-1]["repair_attempts"]

    # reset llm_queries for repair attempts
    states["llm_queries"] -= repair_attempts

    is_assertion_error = False
    # Repair loop until success or max attempts reached
    while (exit_code != 0 and repair_attempts < max_attempts):

        # If assertion error happens in post-PR functions, we stop the repair attempts
        if "AssertionError" in stdout and not (("pre-pr" in stdout.lower() and "post-pr" not in stdout.lower()) or ("pre_" + fut_name in stdout.lower() and "post_" + fut_name not in stdout.lower())):
            append_event(Event(
                level="INFO", pr_nb=pr_nb,
                message="Validation ended with AssertionError indicating potential bugs in the PR. Stopping repair attempts."
            ))
            is_assertion_error = True
            break

        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message=f"Validation failed! => Attempting to repair the specification (Attempt {repair_attempts + 1})..."
        ))

        # Call to LLM-Fixer to repair the specification
        fixed_specification = repair(
            code=specification,
            error_message=stdout,
            prev_fut_code=prev_fut_code,
            post_fut_code=post_fut_code
        )

        if fixed_specification is None:
            append_event(Event(
                level="WARNING", pr_nb=pr_nb,
                message="Response from repair is None. Re-trying..."
            ))
            repair_attempts += 1
            continue

        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message= [
                f"Repaired specification (Attempt {repair_attempts + 1}):",
                format_info_frame(fixed_specification, "REPAIRED SPECIFICATION (ATTEMPT " + str(repair_attempts + 1) + ")")
            ],
            type="RepairResult",
            info={
                "specification_before_repair": specification,
                "repaired_specification": fixed_specification,
                "n_attempts": repair_attempts + 1
            }
        ))

        specification = fixed_specification
        exit_code, stdout = executor.execute_python_code(specification)
        repair_attempts += 1

        # Update states and save to cache
        states["specification"] = specification
        states["specification_traces"].append(specification)
        states[f"execution_status"].append({
            "exit_code": exit_code,
            "error_message": stdout,
            "repair_attempts": repair_attempts
        })
        save_results_to_cache(cache_dir, states)

    if exit_code != 0 and not is_assertion_error:
        assert repair_attempts >= max_attempts, "If exit_code is not 0, repair_attempts should reach max_attempts."
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message=f"Failed to validate specification after {max_attempts} attempts. Exiting..."
        ))

        states["llm_queries"] += repair_attempts
        states[f"error_repair"] = False
        save_results_to_cache(cache_dir, states)
        return states

    states["llm_queries"] += repair_attempts
    states[f"error_repair"] = True
    save_results_to_cache(cache_dir, states)
    return states

def assertion_errors_review(
        states,
        pr_nb,
        cache_dir,
        pull_request_details,
        prev_fut_code,
        post_fut_code,
        prev_fut_names,
        post_fut_signatures,
        available_import,
        enclosing_class,
        code_changes
    ):
    error_message = states[f"execution_status"][-1]["error_message"]
    exit_code = states[f"execution_status"][-1]["exit_code"]
    specification = states["specification"]
    if exit_code != 0:
        assert "AssertionError" in error_message, "Only AssertionError should reach the review stage."
        states["stage"] = "assert_review"
        append_event(Event(
            level="WARNING", pr_nb=pr_nb,
            message= [
                "Potential bugs found in the Pull Request! Please review the specification and execution message.",
                "---------------------- Bug-Triggering Specification -----------------",
                specification,
                "---------------------- Execution Message -----------------",
                error_message
            ],
            info={
                "bug_triggering_specification": specification,
                "execution_message": error_message
            }
        ))

        review_results = review_test_driver(
            pull_request_details = pull_request_details,
            prev_fut_code= prev_fut_code,
            prev_fut_names= prev_fut_names,
            post_fut_signatures= post_fut_signatures,
            post_fut_code= post_fut_code,
            available_import= available_import,
            enclosing_class= enclosing_class,
            test_driver= specification,
            error_message= error_message,
            code_changes= code_changes
        )

        if review_results is None:
            states["llm_queries"] += Config.REVIEW_ATTEMPTS
            states["assert_review"] = False
            append_event(Event(
                level="ERROR", pr_nb=pr_nb,
                message="Failed to analyze intent. Exiting."
            ))
            save_results_to_cache(cache_dir, states)
            return states

        states["review_conclusion"] = review_results["conclusion"]
        states["review_reasoning"] = review_results.get("reasoning", "")
        states["review_queries"] = review_results["review_queries"]

        if "review_traces" not in states:
            states["review_traces"] = []

        states["review_traces"].append({
            "conclusion": review_results["conclusion"],
            "reasoning": review_results.get("reasoning", ""),
            "revised_specification": review_results.get("specification", specification),
            "review_queries": review_results["review_queries"]
        })

        if review_results["conclusion"] == "MISMATCH":
            append_event(Event(
                level="INFO", pr_nb=pr_nb,
                message= [
                    "Test driver review completed. Conclusion: MISMATCH. The specification does not accurately reflect the intended behavior of the modified function(s).",
                    "Please review the revised specification:",
                    format_info_frame(review_results["specification"], "REVISED SPECIFICATION AFTER REVIEW")
                ],
                type="SpecReviewResult",
                info={
                    "conclusion": review_results["conclusion"],
                    "reasoning": review_results.get("reasoning", ""),
                    "revised_specification": review_results["specification"]
                }
            ))
            states["specification"] = review_results["specification"]
            states["specification_traces"].append(states["specification"])

        elif review_results["conclusion"] == "BUG":
            append_event(Event(
                level="WARNING", pr_nb=pr_nb,
                message= [
                    "Test driver review completed. Conclusion: BUG. The specification accurately reflects the intended behavior, indicating potential bugs in the modified function(s).",
                    "Please review the specification and execution message.",
                    format_info_frame(states["specification"], "BUG-TRIGGERING SPECIFICATION"),
                    format_info_frame(error_message, "EXECUTION MESSAGE")
                ],
                type="SpecReviewResult",
                info={
                    "conclusion": states["review_conclusion"],
                    "reasoning": states["review_reasoning"],
                    "bug_triggering_specification": states["specification"],
                    "execution_message": error_message
                }
            ))
            states["stage"] = "completed"

        else:
            raise ValueError(f"Unknown conclusion from test driver review: {review_results['conclusion']}")

        states["llm_queries"] += review_results["review_queries"]
        states["assert_review"] = True

    else:
        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message="No assertion errors found in the Pull Request with the generated specification. Skipping stage 3 (Reviewing Assertion Errors).",
        ))
        states["review_conclusion"] = "NORMAL"
        states["stage"] = "completed"

    states["assert_review"] = True
    save_results_to_cache(cache_dir, states)
    return states

def bug_trigger_generation(
        states,
        original_specification,
        pull_request_details,
        prev_fut_code,
        post_fut_code,
        prev_fut_names,
        post_fut_signatures,
        enclosing_class,
        pr_nb, cache_dir,
        available_import,
    ):
    states["stage"] = "bug_trigger_generation"

    analysis_results = generalize_spec(
            specification=original_specification,
            pull_request_details=pull_request_details,
            prev_fut_code=prev_fut_code,
            prev_fut_names=prev_fut_names,
            post_fut_code=post_fut_code,
            available_import=available_import,
            enclosing_class=enclosing_class,
        )

    if analysis_results is None:
        states["bug_trigger_generation"] = False
        states["llm_queries"] = Config.ANALYSIS_ATTEMPTS
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message="Failed to analyze intent. Exiting."
        ))
        save_results_to_cache(cache_dir, states)
        return states

    states.update(analysis_results)

    assert "specification" in states, "Bug trigger generation did not return a specification."
    append_event(Event(
        level="INFO", pr_nb=pr_nb,
        message= [
            "Bug trigger generation completed successfully. Generated specification:",
            format_info_frame(states["specification"], "GENERALIZED SPECIFICATION")
        ],
        type="SpecInferenceResult",
        info={
            "specification": states["specification"],
            "reasoning": states.get("reasoning", "N/A"),
            "hypothesis": states.get("hypotheses", "N/A")
        }

    ))

    states["llm_queries"] += analysis_results["bug_trigger_queries"]
    states["bug_trigger_generation"] = True
    save_results_to_cache(cache_dir, states)
    return states

def spec_infer(
        pr_nb: int,
        force: bool = False,
        cache_dir: str = None,
        pull_request_details: str = None,
        prev_fut_code: str = None,
        post_fut_code: str = None,
        prev_fut_names: str = None,
        post_fut_signatures: str = None,
        enclosing_class: str = None,
        pr = None,
        cloned_repo_manager = None,
        fut_name: str = None,
        code_changes: str = None,
        summary_queries: int = 0,
    ) -> int:

    ### Check and load from cache if available
    states = {
        "stage": "init",
        "llm_queries": 0,
    }
    if os.path.exists(os.path.join(cache_dir, "results.json")) and not force:
        append_event(
            Event(
                level="INFO",
                pr_nb=pr_nb,
                message="Intent analysis results already cached. Loading from cache..."
            )
        )

        is_complete, states = load_from_cache(cache_dir, pr_nb)
        if is_complete:
            return states

    # Stage 1: Intent Analysis
    if states["stage"] == "init":
        states = intent_analysis(states, pull_request_details, prev_fut_code, post_fut_code, prev_fut_names, post_fut_signatures, enclosing_class, pr_nb, cache_dir, pr.import_string)
        states["llm_queries"] += summary_queries
        if not states["intent_analysis"]:
            states["stage"] = "failed"
            save_results_to_cache(cache_dir, states)
            return states

    # Stage 2: Error Repair and Bug Review
    while states["stage"] not in ["completed", "failed"] and states["llm_queries"] < Config.MAX_LLM_QUERIES:
        states = error_repair(states, pr_nb, cache_dir, pr, cloned_repo_manager, prev_fut_code, post_fut_code, fut_name, Config.REPAIR_ATTEMPTS)

        if not states[f"error_repair"]:
            states["stage"] = "failed"
            break

        states = assertion_errors_review(states, pr_nb, cache_dir, pull_request_details, prev_fut_code, post_fut_code, prev_fut_names, post_fut_signatures, pr.import_string, enclosing_class, code_changes)

        if not states["assert_review"]:
            states["stage"] = "failed"
            break

    if states["stage"] != "completed":
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message="Analysis did not complete successfully within the allowed number of LLM queries. Exiting."
        ))
        states["stage"] = "failed"
        save_results_to_cache(cache_dir, states)
        return states

    if states["review_conclusion"] == "BUG":
        error_message = states["execution_status"][-1]["error_message"]

        append_event(Event(
            level="WARNING", pr_nb=pr_nb,
            message= [
                "Specification inference completed. Issues found in the Pull Request.",
                "Please review the final specification and execution message.",
                format_info_frame(states["specification"], "FINAL SPECIFICATION"),
                format_info_frame(error_message, "EXECUTION MESSAGE")
            ]
        ))
    elif states["review_conclusion"] == "NORMAL":
        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message="Specification inference completed successfully. No issues found in the Pull Request.",
            type="AnalysisComplete",
        ))
    else:
        raise ValueError(f"Unknown review conclusion: {states['review_conclusion']}")

    save_results_to_cache(cache_dir, states)
    return states

def spec_generalization(
        pr_nb: int,
        force: bool = False,
        cache_dir: str = None,
        original_specification: str = None,
        pull_request_details: str = None,
        prev_fut_code: str = None,
        post_fut_code: str = None,
        prev_fut_names: str = None,
        post_fut_signatures: str = None,
        enclosing_class: str = None,
        pr = None,
        cloned_repo_manager = None,
        fut_name: str = None,
        code_changes: str = None,
    ) -> int:

    ### Check and load from cache if available
    states = {
        "stage": "init",
        "llm_queries": 0,
    }
    if os.path.exists(os.path.join(cache_dir, "results.json")) and not force:
        append_event(
            Event(
                level="INFO",
                pr_nb=pr_nb,
                message="Bug trigger generation results already cached. Loading from cache..."
            )
        )

        is_complete, states = load_from_cache(cache_dir, pr_nb)
        if is_complete:
            return states

    # Stage 1: Bug Trigger Generation
    if states["stage"] == "init":
        states = bug_trigger_generation(states, original_specification, pull_request_details, prev_fut_code, post_fut_code, prev_fut_names, post_fut_signatures, enclosing_class, pr_nb, cache_dir, pr.import_string)
        if not states["bug_trigger_generation"]:
            states["stage"] = "failed"
            save_results_to_cache(cache_dir, states)
            return states

    # Stage 2: Error Repair and Bug Review
    while states["stage"] not in ["completed", "failed"] and states["llm_queries"] < Config.MAX_LLM_QUERIES:
        states = error_repair(states, pr_nb, cache_dir, pr, cloned_repo_manager, prev_fut_code, post_fut_code, fut_name, Config.REPAIR_ATTEMPTS)

        if not states[f"error_repair"]:
            states["stage"] = "failed"
            break

        states = assertion_errors_review(states, pr_nb, cache_dir, pull_request_details, prev_fut_code, post_fut_code, prev_fut_names, post_fut_signatures, pr.import_string, enclosing_class, code_changes)

        if not states["assert_review"]:
            states["stage"] = "failed"
            break

    if states["stage"] != "completed":
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message="Analysis did not complete successfully within the allowed number of LLM queries. Exiting."
        ))
        states["stage"] = "failed"
        save_results_to_cache(cache_dir, states)
        return states

    if states["review_conclusion"] == "BUG":
        error_message = states["execution_status"][-1]["error_message"]

        append_event(Event(
            level="WARNING", pr_nb=pr_nb,
            message= [
                "Specification generalization completed. Issues found in the Pull Request.",
                "Please review the final specification and execution message.",
                format_info_frame(states["specification"], "FINAL SPECIFICATION"),
                format_info_frame(error_message, "EXECUTION MESSAGE")
            ]
        ))
    elif states["review_conclusion"] == "NORMAL":
        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message="Specification generalization completed successfully. No issues found in the Pull Request.",
            type="AnalysisComplete",
        ))
    else:
        raise ValueError(f"Unknown review conclusion: {states['review_conclusion']}")

    save_results_to_cache(cache_dir, states)
    return states

def analyze(project: str, pr_nb: int, force: bool = False) -> None:
    append_event(
        Event(
            level="INFO",
            pr_nb=pr_nb,
            message=f"Starting analysis for PR #{pr_nb} in project {project}",
        )
    )
    cache_dir = os.path.join(Config.CACHE_DIR, "oracles", project, str(pr_nb))
    os.makedirs(cache_dir, exist_ok=True)

    # Save config used for this analysis
    config_dict = {
        "INTENT_ANALYSIS_PROMPT": Config.INTENT_ANALYSIS_PROMPT,
        "SELF_REVIEW_PROMPT": Config.SELF_REVIEW_PROMPT,
        "RUNTIME_ERROR_REPAIR_PROMPT": Config.RUNTIME_ERROR_REPAIR_PROMPT,
        "ASSERTION_ERROR_REPAIR_PROMPT": Config.ASSERTION_ERROR_REPAIR_PROMPT,
        "SYNTAX_ERROR_REPAIR_PROMPT": Config.SYNTAX_ERROR_REPAIR_PROMPT,
        "MAX_LLM_QUERIES": Config.MAX_LLM_QUERIES,
        "ANALYSIS_ATTEMPTS": Config.ANALYSIS_ATTEMPTS,
        "REVIEW_ATTEMPTS": Config.REVIEW_ATTEMPTS,
        "REPAIR_ATTEMPTS": Config.REPAIR_ATTEMPTS,
        "USE_REFERENCE": Config.USE_REFERENCE,
        "LLM_MODEL": Config.LLM_MODEL,
        "USE_REFERENCE_SUMMARY": Config.USE_REFERENCE_SUMMARY,
    }

    with open(os.path.join(cache_dir, "config.json"), "w") as f:
        json.dump(config_dict, f, indent=4)

    os.makedirs(cache_dir, exist_ok=True)
    append_event(
        Event(
            level="DEBUG",
            pr_nb=pr_nb,
            message=f"Cache directory set to {cache_dir}",
        )
    )

    ## Retrieve and do lightweight analysis of the target PR
    pr, cloned_repo_manager, github_repo = retrieve_pr(project, pr_nb)
    if pr is None:
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message=f"Failed to retrieve Pull Request. Exiting."
        ))
        return

    pull_request_details, prev_fut_code, post_fut_code, prev_fut_names, post_fut_signatures, enclosing_class, code_changes, has_reference, summary_queries = prepare_information(pr, github_repo, pr_nb)

    assert len(prev_fut_names.split(",")) == 1, "Currently only support PRs that modify one function."

    fut_name = prev_fut_names.split(",")[0].split(".")[-1]

    phase1_ending_stages = spec_infer(
        pr_nb= pr_nb,
        force= force,
        cache_dir= cache_dir,
        pull_request_details= pull_request_details,
        prev_fut_code= prev_fut_code,
        post_fut_code= post_fut_code,
        prev_fut_names= prev_fut_names,
        post_fut_signatures= post_fut_signatures,
        enclosing_class= enclosing_class,
        pr = pr,
        cloned_repo_manager = cloned_repo_manager,
        fut_name= fut_name,
        code_changes= code_changes,
        summary_queries = summary_queries
    )

    if not Config.USE_PHASE2:
        return

    if phase1_ending_stages["stage"] != "completed":
        append_event(Event(
            level="ERROR", pr_nb=pr_nb,
            message="Specification inference failed. Exiting."
        ))
        return

    phase1_specification = phase1_ending_stages["specification"]
    phase1_conclusion = phase1_ending_stages["review_conclusion"]

    if phase1_conclusion == "BUG":
        append_event(Event(
            level="INFO", pr_nb=pr_nb,
            message="The Pull Request has been identified to contain potential bugs in phase 1 (Specification Inference). Skipping phase 2 (Specification Generalization).",
            type="GeneralInfo",
            info={
                "reason": "Potential bugs identified in phase 1",
                "final_specification": phase1_specification,
                "execution_message": phase1_ending_stages["execution_status"][-1]["error_message"]
            }
        ))
        return

    cache_dir_phase2 = os.path.join(Config.CACHE_DIR, "oracles", project, str(pr_nb), "phase2")
    specification = spec_generalization(
        pr_nb= pr_nb,
        force= force,
        cache_dir= cache_dir_phase2,
        original_specification= phase1_specification,
        pull_request_details= pull_request_details,
        prev_fut_code= prev_fut_code,
        post_fut_code= post_fut_code,
        prev_fut_names= prev_fut_names,
        post_fut_signatures= post_fut_signatures,
        enclosing_class= enclosing_class,
        pr = pr,
        cloned_repo_manager = cloned_repo_manager,
        fut_name= fut_name,
        code_changes= code_changes
    )



def save_results_to_cache(cache_dir, results):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    with open(os.path.join(cache_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=4)

    with open(os.path.join(cache_dir, "specification.py"), "w") as f:
        if "specification" in results:
            f.write(results["specification"])
        else:
            f.write("# No specification generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch Reviewer CLI")
    parser.add_argument("--project", type=str, required=True, help="Project name (e.g., pandas, scikit-learn)")
    parser.add_argument("--pr_nb", type=int, required=True, help="Pull Request number to review")
    parser.add_argument("--force", action="store_true", help="Force re-analysis even if results are cached")
    args = parser.parse_args()
    analyze(args.project, args.pr_nb, args.force)

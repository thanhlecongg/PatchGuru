import argparse
import os
import json
import numpy as np
from datetime import datetime, timezone


def parse_logs(log_dir):
    log_files = os.listdir(log_dir)
    usage_results = {}
    for log_file in log_files:
        event_path = os.path.join(log_dir, log_file, "events.jsonl")
        usage_path = os.path.join(log_dir, log_file, "llm_usage.json")

        # Load events
        events = []
        assert os.path.exists(event_path), f"Event file not found: {event_path}"
        with open(event_path, "r") as f:
            for line in f:
                events.append(json.loads(line))

        # Load LLM usage
        llm_usage = []
        assert os.path.exists(usage_path), f"LLM usage file not found: {usage_path}"
        with open(usage_path, "r") as f:
            data = json.load(f)
            for entry in data:
                if "completion_tokens" in entry:
                    llm_usage.append(entry)


        pr_nb = events[0]["pr_nb"]
        assert pr_nb not in usage_results, f"Duplicate PR number found: {pr_nb}, {os.path.join(log_dir, log_file)}, {usage_results[pr_nb]['log_dir']}"
        usage_results[str(pr_nb)] = {
            "events": events,
            "llm_usage": llm_usage,
            "log_dir": os.path.join(log_dir, log_file)
        }
    return usage_results

def analyze(project):
    result_dir = f".cache/oracles/{project}"
    data_id_path = f".cache/pr_ids/{project}.txt"
    log_dir = f"logs/{project}"
    with open(data_id_path, "r") as f:
        data_ids = [line.strip() for line in f]

    n_warnings = 0
    n_bug = 0
    n_mismatch = 0
    log_results = parse_logs(log_dir)
    for data_id in data_ids:
        assert data_id in log_results, f"Data ID {data_id} not found in logs for project {project}"
        for event in log_results[data_id]["events"]:
            if "type" in event and event["type"] == "SpecReviewResult":
                n_warnings += 1
                if "Test driver review completed. Conclusion: BUG" in event["message"]:
                    n_bug += 1
                elif "Test driver review completed. Conclusion: MISMATCH" in event["message"]:
                    n_mismatch += 1
                else:
                    assert False, f"Unexpected conclusion in SpecReviewResult for Data ID {data_id}: {event['message']}"
                break
            
    
                
            

            
                
    return n_warnings, n_bug, n_mismatch

    

if __name__ == "__main__":
    _MAPPING = {
        "pandas": "Pandas",
        "scipy": "SciPy",
        "keras": "Keras",
        "marshmallow": "Marshmallow"
    }
    
    n_warnings = 0
    n_bugs = 0
    n_mismatches = 0
    n_tp_in_bug = 0
    n_fp_in_bug = 0
    n_tp_in_mismatch = 0
    n_fp_in_mismatch = 0
    for project in ["pandas", "scipy", "keras", "marshmallow"]:
        project_name = _MAPPING[project]
        project_warnings, project_bugs, project_mismatches = analyze(project)
        n_warnings += project_warnings
        n_bugs += project_bugs
        n_mismatches += project_mismatches
        with open(f".cache/manual_annotation/RQ4/{project}/bug_cases.txt", "r") as f:
            for line in f:
                splitted_line = line.strip().split()
                label = splitted_line[1]
                if label == "TP":
                    n_tp_in_bug += 1
                elif label == "FP":
                    n_fp_in_bug += 1
                else:
                    assert False, f"Invalid label in bug_cases.txt for project {project}: {line}"
        with open(f".cache/manual_annotation/RQ4/{project}/mismatch_cases.txt", "r") as f:
            for line in f:
                splitted_line = line.strip().split()
                label = splitted_line[1]
                if label == "TP":
                    n_tp_in_mismatch += 1
                elif label == "FP":
                    n_fp_in_mismatch += 1
                else:
                    assert False, f"Invalid label in mismatch_cases.txt for project {project}: {line}"
            

    
    
    print(f"Total number of warnings across all projects: {n_warnings}")
    print(f"Total number of bugs identified across all projects: {n_bugs}")
    print(f"Total number of mismatches identified across all projects: {n_mismatches}")
    print(f"Number of true positives in bug cases: {n_tp_in_bug}")
    print(f"Number of false positives in bug cases: {n_fp_in_bug}")
    print(f"Number of true positives in mismatch cases: {n_tp_in_mismatch}")
    print(f"Number of false positives in mismatch cases: {n_fp_in_mismatch}")
    estimated_tp = n_tp_in_bug + n_tp_in_mismatch/20 * (n_mismatches)
    estimated_fp = n_fp_in_bug + n_fp_in_mismatch/20 * (n_mismatches)
    print(f"Estimated true positives across all warnings: {estimated_tp}")
    print(f"Estimated false positives across all warnings: {estimated_fp}")
    print(f"Estimated precision: {estimated_tp / (estimated_tp + estimated_fp):.2f}")

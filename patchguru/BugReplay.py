import argparse
import os
import json

from patchguru.execution.DockerExecutor import DockerExecutor
from patchguru.utils.PullRequest import PullRequest
from patchguru.analysis.PRRetriever import get_repo
import time

CACHE_DIR = ".cache/RQ2/"

def replay(repo_name: str, pr_number: int, timeout: int):
    result_path = os.path.join(CACHE_DIR, repo_name, str(pr_number), "phase2", "results.json")
    if not os.path.exists(result_path):
        result_path = os.path.join(CACHE_DIR, repo_name, str(pr_number), "results.json")
    print(result_path)
    assert os.path.exists(result_path), f"Result file not found for PR {pr_number} in repo {repo_name}"

    # Load result from result_path
    with open(result_path, "r") as f:
        result_data = json.load(f)

    review_conclusion = result_data.get("review_conclusion", None)
    assert review_conclusion == "BUG"
    review_reasoning = result_data.get("review_reasoning", "")
    with open("viewer/viewer.txt", "w") as f:
        f.write(f"Review Conclusion: {review_conclusion}\n")
        f.write(f"Review Reasoning: \n{review_reasoning}\n")

    print(f"Replaying bug triggering process for PR {pr_number} in repo {repo_name}")
    print(f"You can check bug explaination in viewer/viewer.txt")

    github_repo, cloned_repo_manager = get_repo(args.repo)
    github_pr = github_repo.get_pull(args.pr)
    pr = PullRequest(github_pr, github_repo, cloned_repo_manager)
    commit = pr.pre_commit
    print(f"Using pre-change commit: {commit}")
    print(f"post-change commit: {pr.post_commit}")
    cloned_repo = cloned_repo_manager.get_cloned_repo(commit)
    container_name = cloned_repo.container_name
    docker_executor = DockerExecutor(container_name)

    spec_path = result_path.replace("results.json", "specification.py")
    print(f"Replaying bug triggering code from specification: {spec_path}")

    while True:
        start_time = time.time()
        with open(spec_path, "r") as f:
            code = f.read()
        exit_code, output = docker_executor.execute_python_code(code, timeout=timeout)
        print(output)
        print(f"Time taken for import: {time.time() - start_time} seconds")
        input("Press Enter to re-run the code...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay bug triggering process in a Docker container for a given PR.")
    parser.add_argument("--project", required=True, help="Repository name (e.g., keras)")
    parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout for code execution (seconds)")
    args = parser.parse_args()
    replay(args.project, args.pr, args.timeout)

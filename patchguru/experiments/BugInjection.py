import argparse
from patchguru.analysis.PRRetriever import retrieve_pr
from patchguru.utils.CodeMutation import create_mutator, mutate
def generate_mutants_with_mutpy(code: SyntaxWarning) -> dict:
    mutator = create_mutator(
        experimental_operators=True,
        operator=None,
        disable_operator=[],
        order=1,
        percentage=100
    )
    return mutate(mutator, code)

def bug_injection(project, pr_number, max_injected_bugs=3):
    # Load PR information
    pr, cloned_repo_manager, github_repo = retrieve_pr(project, pr_number)
    assert len(pr.changed_functions) == 1, "This script only supports PRs with a single changed function."
    print(pr.changed_functions)
    print(pr.post_fut_info.keys())
    fut_info = pr.post_fut_info[list(pr.post_fut_info.keys())[0]]
    print(fut_info.keys())
    file_path = fut_info["file_path"]
    start_line = fut_info["start_line"]
    end_line = fut_info["end_line"]
    code = fut_info["code"]
    cloned_repo = cloned_repo_manager.get_cloned_repo(pr.post_commit)
    container_name = cloned_repo.container_name
    print(cloned_repo_manager.repo_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect PRs for a given project.")
    parser.add_argument("-p", "--project", type=str, required=True, help="Project name (e.g., 'scipy' or 'pandas')")
    parser.add_argument("-m", "--max_injected_bugs", type=int, default=3, help="Maximum number of bugs to inject per PR (default: 3)")
    parser.add_argument("-n", "--pr_number", type=int, required=True, help="Pull request number")
    args = parser.parse_args()
    bug_injection(args.project, args.pr_number, args.max_injected_bugs)

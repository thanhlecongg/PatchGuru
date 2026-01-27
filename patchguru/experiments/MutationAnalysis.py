import os
import json
from patchguru.utils.PullRequest import PullRequest
from patchguru.analysis.PRRetriever import get_repo
from patchguru.execution.DockerExecutor import DockerExecutor
from patchguru.utils.CodeMutation import generate_mutants, beautify_code
from patchguru.utils.PythonCodeUtil import update_function_name
import termcolor
import argparse
import difflib
from hashlib import blake2b

def decorate(text, color=None, on_color=None, attrs=None):
    termcolor.colored(text, color, on_color, attrs)

def extract_fut_code(fut_info, pre_fix = None):
    assert len(fut_info.items()) == 1, "Only single function change is supported in this analysis."
    fct_name, fct_info = list(fut_info.items())[0]
    code = fct_info['code']
    only_name = fct_name.split('.')[-1]
    if pre_fix:
        code = update_function_name(code, only_name, f"{pre_fix}{only_name}")
    return code

def do_mutation(spec_path, result_dir, github_repo, pr_id , cloned_repo_manager, repo_name):
    os.makedirs(result_dir, exist_ok=True)
    with open(spec_path, "r") as f:
        spec = f.read()

    github_pr = github_repo.get_pull(pr_id)
    pr = PullRequest(github_pr, github_repo, cloned_repo_manager)
    commit = pr.pre_commit
    cloned_repo = cloned_repo_manager.get_cloned_repo(commit)
    container_name = cloned_repo.container_name
    docker_executor = DockerExecutor(container_name)

    post_fut_code_without_prefix = extract_fut_code(pr.post_fut_info)
    pre_fut_code_without_prefix = extract_fut_code(pr.prev_fut_info)
    post_fut_code_without_prefix = beautify_code(post_fut_code_without_prefix)
    pre_fut_code_without_prefix = beautify_code(pre_fut_code_without_prefix)
    diff = difflib.unified_diff(
        pre_fut_code_without_prefix.splitlines(),
        post_fut_code_without_prefix.splitlines(),
        lineterm='',
    )
    added_lines = []
    for line in diff:
        if line.startswith('+') and not line.startswith('+++') and len(line.strip()) > 1:
            added_lines.append(line[1:].strip())

    post_fut_code = extract_fut_code(pr.post_fut_info, pre_fix="post_")
    pre_fut_code = extract_fut_code(pr.prev_fut_info, pre_fix="pre_")


    before = spec.split("## Before Pull Request")[0]
    after = spec.split("# Specification")[1]
    spec = f"{before}## Before Pull Request\n{pre_fut_code}\n## After Pull Request\n{post_fut_code}\n# Formal Specification{after}"
    n_mutant_pass = 0
    n_mutant_fail_assert = 0
    n_mutant_fail_other = 0
    try:
        mutants = generate_mutants(post_fut_code)
    except Exception as e:
        print(f"Error generating mutants for PR {pr_id}: {e}")
        return
    relevant_mutants = []

    if os.path.exists(os.path.join(result_dir, "mutation_results.json")):
        # Load existing results to avoid re-computation
        with open(os.path.join(result_dir, "mutation_results.json"), "r") as f:
            existing_results = json.load(f)
        execution_results = existing_results.get("execution_results", {})
        n_mutant_pass = existing_results.get("n_mutant_pass", 0)
        n_mutant_fail_assert = existing_results.get("n_mutant_fail_assert", 0)
        n_mutant_fail_other = existing_results.get("n_mutant_fail_other", 0)
    else:
        execution_results = {}
    for idx, mutant in enumerate(mutants):
        diff = difflib.unified_diff(
            post_fut_code.splitlines(),
            mutant.splitlines(),
            lineterm='',
        )
        removed_lines = []
        for line in diff:
            if line.startswith('-') and not line.startswith('---') and len(line.strip()) > 1:
                removed_lines.append(line[1:].strip())

        is_relevant = any(removed_line in added_lines for removed_line in removed_lines)
        if is_relevant:
            hash_id = blake2b(mutant.encode()).hexdigest()
            if hash_id in execution_results:
                print(f"Skipping already tested mutant {idx+1}/{len(mutants)} for PR {pr_id}")
                continue  # Skip already tested mutants
            relevant_mutants.append(mutant)
            print(f"Testing mutant {idx+1}/{len(mutants)} for PR {pr_id}")
            before = spec.split("## After Pull Request")[0]
            after = spec.split("# Formal Specification")[1]
            mutated_spec = f"{before}## After Pull Request\n{mutant}\n# Formal Specification{after}"
            exit_code, output = docker_executor.execute_python_code(mutated_spec, timeout=300)
            print(output)
            print("-" * 40)
            mutant_file_name = f"mutant_{idx+1}_fail.py"
            if exit_code == 0:
                mutant_file_name = f"mutant_{idx+1}_pass.py"
                n_mutant_pass += 1
            else:
                if "AssertionError" in output:
                    mutant_file_name = f"mutant_{idx+1}_assert.py"
                    n_mutant_fail_assert += 1
                else:
                    n_mutant_fail_other += 1
            with open(os.path.join(result_dir, mutant_file_name), "w") as f:
                    f.write(mutated_spec)
            execution_results[hash_id] = {
                "exit_code": exit_code,
                "output": output,
            }
    # Save mutation results
    mutation_results = {
        "total_mutants": len(mutants),
        "relevant_mutants": len(relevant_mutants),
        "execution_results": execution_results,
        "n_mutant_pass": n_mutant_pass,
        "n_mutant_fail_assert": n_mutant_fail_assert,
        "n_mutant_fail_other": n_mutant_fail_other,
    }
    with open(os.path.join(result_dir, "mutation_results.json"), "w") as f:
        json.dump(mutation_results, f, indent=4)

def main(repo_name, analysis_result_dir):
    pr_ids_file = f"data/pr_data/prs/{repo_name}.txt"
    target_pr_ids = []
    with open(pr_ids_file) as f:
        for line in f:
            target_pr_ids.append(int(line.strip()))
    target_pr_ids = sorted(target_pr_ids)
    github_repo, cloned_repo_manager = get_repo(repo_name)
    for pr_id in target_pr_ids:
        if pr_id >= 2244:
            continue
        phase1_spec_path = os.path.join(analysis_result_dir, str(pr_id), "specification.py")
        phase2_spec_path = os.path.join(analysis_result_dir, str(pr_id), "phase2", "specification.py")
        if os.path.exists(phase1_spec_path):
            spec_path = phase1_spec_path
            result_dir = os.path.join(".cache", "mutation_testing", "patchguru", repo_name, str(pr_id))
            analysis_result_path = os.path.join(analysis_result_dir, str(pr_id), "results.json")
            with open(analysis_result_path) as f:
                analysis_result = json.load(f)
            if "stage" not in analysis_result or analysis_result["stage"] != "completed":
                print(f"Skipping PR {pr_id} mutation analysis due to incomplete analysis.")
                continue
            do_mutation(spec_path, result_dir, github_repo, pr_id, cloned_repo_manager, repo_name)

        if os.path.exists(phase2_spec_path):
            spec_path = phase2_spec_path
            result_dir = os.path.join(".cache", "mutation_testing", "patchguru", repo_name, str(pr_id), "phase2")
            analysis_result_path = os.path.join(analysis_result_dir, str(pr_id), "phase2", "results.json")
            with open(analysis_result_path) as f:
                analysis_result = json.load(f)
            if "stage" not in analysis_result or analysis_result["stage"] != "completed":
                print(f"Skipping PR {pr_id} phase2 mutation analysis due to incomplete analysis.")
                continue
            do_mutation(spec_path, result_dir, github_repo, pr_id, cloned_repo_manager, repo_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mutation analysis for a given repo")
    parser.add_argument("--repo", type=str, required=True, help="Repository name (e.g., pandas)")
    parser.add_argument("--result_dir", type=str, required=True, help="Directory to store results")
    args = parser.parse_args()
    main(args.repo, args.result_dir)

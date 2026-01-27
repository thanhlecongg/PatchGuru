import os
import argparse
import termcolor

from patchguru.utils.PythonCodeUtil import update_function_name, insert_print_statement
from patchguru.utils.PullRequest import PullRequest
from patchguru.analysis.PRRetriever import get_repo
from patchguru.execution.DockerExecutor import DockerExecutor
import time
import json
import re

PRINT_STRING = "PatchGuru: Function called !!!"
PRINT_LINE = f"print('{PRINT_STRING}', end=' ')"

def extract_output_logs_single(output: str, test_folder: str):
    log_lines = output.splitlines()
    START_MARKER = "== test session starts =="
    is_start = False
    current_test = None
    current_log = ""
    test_results = {}
    relevant_test_cases = set()
    for i, line in enumerate(log_lines):
        if START_MARKER in line:
            is_start = True
            continue

        if line.startswith("==="):
            if current_test is not None:
                current_log = current_log.strip()
                status = current_log.split(" ")[-1]
                test_results[current_test] = {
                    "status": 0 if status == "PASSED" else 1,
                    "log": current_log
                }
                if PRINT_STRING in current_log and status == "PASSED":
                    relevant_test_cases.add(current_test)
            break
        if is_start:
            if line.startswith(test_folder):
                if current_test is not None:
                    current_log = current_log.strip()
                    status = current_log.split(" ")[-1]
                    test_results[current_test] = {
                        "status": 0 if status == "PASSED" else 1,
                        "log": current_log
                    }
                    if PRINT_STRING in current_log and status == "PASSED":
                        relevant_test_cases.add(current_test)

                splitted_line = line.split(" ")
                current_test = splitted_line[0].strip()
                current_log = " ".join(splitted_line[1:])
            else:
                current_log += " " + line
    return test_results, relevant_test_cases

def check_output_logs_single(output: str, test_folder: str):
    log_lines = output.splitlines()
    START_MARKER = "== test session starts =="
    is_start = False
    current_test = None
    current_log = ""
    is_failed = False
    for i, line in enumerate(log_lines):
        if START_MARKER in line:
            is_start = True
            continue

        if line.startswith("==="):
            if current_test is not None:
                current_log = current_log.strip()
                status = current_log.split(" ")[-1]
                status = current_log.split("[")[0].strip()
                if status == "FAILED" or status == "ERROR":
                    is_failed = True
            break
        if is_start:
            if line.startswith(test_folder):
                if current_test is not None:
                    status = current_log.split(" ")[-1]
                    status = current_log.split("[")[0].strip()
                    if status == "FAILED" or status == "ERROR":
                        is_failed = True

                splitted_line = line.split(" ")
                current_test = splitted_line[0].strip()
                current_log = " ".join(splitted_line[1:])
            else:
                current_log += " " + line

    return is_failed

def parse_log_line(log_line):
    pattern = re.compile(r"\[gw\d+\]\s+\[\s*\d+%\]\s+(\w+)\s+(.+)")

    match = pattern.search(log_line)
    if match:
        status = match.group(1)
        test_id = match.group(2).strip()

        return {
            'status': status,
            'test': test_id
        }
    return None

def extract_output_logs_parallel(output: str, test_folder: str):
    log_lines = output.splitlines()
    START_MARKER = "== test session starts =="
    is_start = False
    current_test = None
    current_log = ""
    test_results = {}
    relevant_test_cases = set()
    for i, line in enumerate(log_lines):
        if START_MARKER in line:
            is_start = True
            continue

        if is_start:
            if line.startswith("==="):
                is_start = False
                break
            parsed_logs = parse_log_line(line)
            if parsed_logs != None:
                current_test = parsed_logs['test']
                status = parsed_logs['status']
                test_results[current_test] = {
                    "status": 0 if status == "PASSED" else 1,
                    "log": line
                }
                pass

    return test_results, relevant_test_cases

def check_output_logs_parallel(output: str, test_folder: str):
    log_lines = output.splitlines()
    START_MARKER = "== test session starts =="
    is_start = False
    for i, line in enumerate(log_lines):
        if START_MARKER in line:
            is_start = True
            continue

        if is_start:
            if line.startswith("==="):
                is_start = False
                break
            parsed_logs = parse_log_line(line)
            if parsed_logs != None:
                status = parsed_logs['status']
                if status == "FAILED" or status == "ERROR":
                    return True

    return False

def get_function_indentation(code_lines, start_line):
    func_indentation = ""
    for char in code_lines[start_line - 1]:
        if char in [' ', '\t']:
            func_indentation += char
        else:
            break
    return func_indentation

def replace_code(file_path: str, start_line: int, end_line: int, new_code: str):
    original_code_lines = open(file_path, "r").readlines()

    # Get indentation of the function
    func_indentation = get_function_indentation(original_code_lines, start_line)

    post_pr_code_with_print_lines = new_code.splitlines(keepends=True)
    # Adjust indentation of the inserted print line
    post_pr_code_with_print_lines = [func_indentation + line for line in post_pr_code_with_print_lines]

    updated_code_lines = original_code_lines[:start_line-1] + \
                            post_pr_code_with_print_lines + \
                            original_code_lines[end_line:]
    updated_code = "".join(updated_code_lines)
    return updated_code

def test_pr(repo_name: str, pr_id: int, mutation_dir: str, github_repo, cloned_repo_manager):
    # if int(pr_id) < 23095 and repo_name == "scipy":
    if int(pr_id) < 2244 and repo_name == "marshmallow":
    # if int(pr_id) != 22910:
        return
    if repo_name == "pandas":
        TEST_CMD = "pytest -o log_cli=true --log-cli-level=INFO -s"
        TEST_FOLDER = "pandas/tests/"
        _SINGLE_TEST_OPTIONS = ["-o", "log_cli=true", "--log-cli-level=INFO", "-s", "--maxfail=1"]
        SINGLE_TEST_CMD = ["pytest"]
        check_output_logs = check_output_logs_single
        extract_output_logs = extract_output_logs_single
    if repo_name == "marshmallow":
        TEST_CMD = "pytest home/marshmallow/tests/ -o log_cli=true --log-cli-level=INFO -s"
        TEST_FOLDER = "home/marshmallow/tests/"
        _SINGLE_TEST_OPTIONS = ["-o", "log_cli=true", "--log-cli-level=INFO", "-s", "--maxfail=1"]
        SINGLE_TEST_CMD = ["pytest"]
        check_output_logs = check_output_logs_single
        extract_output_logs = extract_output_logs_single
    elif repo_name == "keras":
        TEST_CMD = "pytest /home/keras/keras/ --log-cli-level=INFO -s"
        TEST_FOLDER = "home/keras/keras/"
        _SINGLE_TEST_OPTIONS = ["-o", "log_cli=true", "--log-cli-level=INFO", "-s", "--maxfail=1"]
        SINGLE_TEST_CMD = ["pytest"]
        check_output_logs = check_output_logs_single
        extract_output_logs = extract_output_logs_single
    elif repo_name == "scipy":
        if int(pr_id) >= 23095:
            TEST_CMD = "spin test -v -- -o log_cli=true --log-cli-level=INFO -s --continue-on-collection-errors"
            _SINGLE_TEST_OPTIONS = ["-v", "--", "--maxfail=1"]
            SINGLE_TEST_CMD = ["spin", "test"]
        else:
            TEST_CMD = "python dev.py test -v -- -o log_cli=true --log-cli-level=INFO -s --continue-on-collection-errors"
            _SINGLE_TEST_OPTIONS = ["-v", "--", "--maxfail=1"]
            SINGLE_TEST_CMD = ["python", "dev.py", "test"]

        TEST_FOLDER = "scipy/"
        check_output_logs = check_output_logs_single
        extract_output_logs = extract_output_logs_single

    else:
        raise NotImplementedError(f"Repository {repo_name} not supported yet.")

    save_dir = os.path.join(".cache/mutation_testing", "regression_tests", repo_name, pr_id)
    os.makedirs(save_dir, exist_ok=True)
    pr_mutation_dir = os.path.join(mutation_dir, pr_id)
    mutant_files = [f for f in os.listdir(pr_mutation_dir) if f.startswith("mutant_") and f.endswith(".py")]
    print(f"PR {pr_id} has {len(mutant_files)} mutant files.")
    if len(mutant_files) == 0:
        print(termcolor.colored(f"No mutant files found for PR {pr_id}, skipping...", "yellow"))
        return
    print(termcolor.colored(f"Analyzing PR {pr_id} with {len(mutant_files)} mutants...", "green"))

    # Load pr info
    github_pr = github_repo.get_pull(int(pr_id))
    pr = PullRequest(github_pr, github_repo, cloned_repo_manager)
    function_id = list(pr.post_fut_info.keys())[0]
    function_name = function_id.split('.')[-1]
    cloned_repo = cloned_repo_manager.get_cloned_repo(pr.post_commit)
    print(cloned_repo.repo.working_dir)
    # Check if "dev.py" exists in the repo for scipy
    if repo_name == "scipy":
        dev_py_path = os.path.join(cloned_repo.repo.working_dir, "dev.py")
        if not os.path.exists(dev_py_path):
            # Force to use spin test
            TEST_CMD = "spin test -v -- -o log_cli=true --log-cli-level=INFO -s --continue-on-collection-errors"
            _SINGLE_TEST_OPTIONS = ["-v", "--", "--maxfail=1"]
            SINGLE_TEST_CMD = ["spin", "test"]

    container_name = cloned_repo.container_name
    docker_executor = DockerExecutor(container_name)
    post_pr_code = list(pr.post_fut_info.values())[0]["code"]

    start_line = pr.post_fut_info[function_id]["start_line"]
    end_line = pr.post_fut_info[function_id]["end_line"]

    file_path = list(pr.post_fut_info.values())[0]["file_path"]
    abs_file_path = os.path.join(cloned_repo.repo.working_dir, file_path)

    # Filter tests
    relevant_test_cases = set()
    print(os.path.join(save_dir, "relevant_test_cases.txt"))
    if os.path.exists(os.path.join(save_dir, "relevant_test_cases.txt")):
        print(termcolor.colored(f"Relevant test cases already exist for PR {pr_id}, loading...", "blue"))
        for line in open(os.path.join(save_dir, "relevant_test_cases.txt"), "r"):
            relevant_test_cases.add(line.strip())
    else:
        print(termcolor.colored(f"Identifying relevant test cases for PR {pr_id}...", "blue"))
        start_time = time.time()
        # Checkout post commit
        post_pr_code_with_print = insert_print_statement(
            post_pr_code, PRINT_LINE
        )

        updated_code = replace_code(
            abs_file_path, start_line, end_line, post_pr_code_with_print
        )

        # Write updated code back to file
        abs_backup_path = abs_file_path + ".backup"
        if not os.path.exists(abs_backup_path):
            os.system(f"cp {abs_file_path} {abs_backup_path}")

        with open(abs_file_path, "w") as f:
            f.write(updated_code)

        # Run tests
        if os.path.exists(os.path.join(save_dir, "full_test_output.txt")):
            print(termcolor.colored(f"Full test output already exists for PR {pr_id}, loading...", "blue"))
            with open(os.path.join(save_dir, "full_test_output.txt"), "r") as f:
                output = f.read()
        else:
            exit_code, output = docker_executor.execute_shell_command(TEST_CMD)
            with open(os.path.join(save_dir, "full_test_output.txt"), "w") as f:
                f.write(output)
        _, relevant_test_cases = extract_output_logs(output, TEST_FOLDER)
        with open(os.path.join(save_dir, "relevant_test_cases.txt"), "w") as f:
            for test_case in relevant_test_cases:
                f.write(f"{test_case}\n")

        # Restore original code
        os.system(f"mv {abs_backup_path} {abs_file_path}")
        print(f"Time taken to identify relevant tests: {time.time() - start_time} seconds")

    if os.path.exists(os.path.join(save_dir, "mutation_summary.json")):
        print(termcolor.colored(f"Mutation summary already exists for PR {pr_id}, skipping mutation analysis...", "yellow"))
        return

    if len(relevant_test_cases) == 0:
        print(termcolor.colored(f"No relevant test cases found for PR {pr_id}, skipping mutation analysis...", "yellow"))
        # dump summary to a json file
        summary = {
            "n_killed_mutants": 0,
            "n_survived_mutants": len(mutant_files),
            "total_mutants": len(mutant_files)
        }

        with open(os.path.join(save_dir, "mutation_summary.json"), "w") as f:
            json.dump(summary, f, indent=4)
        return

    # Fix incomplete test cases, e.g., pandas/tests/extension/test_arrow.py::TestArrowArray::test_container_shift[timestamp[ns,
    # Do this by: check if their is any open "[" but not closed "]"
    fixed_relevant_test_cases = set()
    for test_case in relevant_test_cases:
        if repo_name == "keras":
            test_case = "/" + test_case  # because keras test cases start with "/"
        if test_case.count("[") > test_case.count("]") or repo_name == "keras":
            new_test_case = test_case.split("[")[0]
            fixed_relevant_test_cases.add(new_test_case)
        else:
            fixed_relevant_test_cases.add(test_case)

    relevant_test_cases = fixed_relevant_test_cases
    print(termcolor.colored(f"Relevant test cases for PR {pr_id}: {' '.join(relevant_test_cases)}", "green"))
    # test_cmd = _SINGLE_TEST_CMD.format(" ".join(fixed_relevant_test_cases))
    test_cmd = SINGLE_TEST_CMD + list(relevant_test_cases) + list(_SINGLE_TEST_OPTIONS)
    n_killed_mutants = 0
    n_survived_mutants = 0
    for mutant_file in mutant_files:
        mutant_path = os.path.join(pr_mutation_dir, mutant_file)
        with open(mutant_path, "r") as f:
            mutant_code = f.read()
        assert "## After Pull Request" in mutant_code, f"Mutant file {mutant_file} does not contain the required separator."
        assert "# Formal Specification" in mutant_code, f"Mutant file {mutant_file} does not contain the required specification marker."
        post_pr_mutated_code = mutant_code.split("## After Pull Request")[1].split("# Formal Specification")[0].strip()
        post_pr_mutated_code = update_function_name(post_pr_mutated_code, f"post_{function_name}", function_name)

        updated_code = replace_code(
            abs_file_path, start_line, end_line, post_pr_mutated_code
        )
        # Write updated code back to file
        abs_backup_path = abs_file_path + ".backup"
        if not os.path.exists(abs_backup_path):
            os.system(f"cp {abs_file_path} {abs_backup_path}")

        with open(abs_file_path, "w") as f:
            f.write(updated_code)

        # Run tests
        exit_code, output = docker_executor.execute_shell_command(test_cmd)

        is_failed = check_output_logs(output, TEST_FOLDER)
        if is_failed:
            result_file_name = mutant_file.replace(".py", "_result_killed.txt")
            n_killed_mutants += 1
        else:
            result_file_name = mutant_file.replace(".py", "_result_survived.txt")
            n_survived_mutants += 1
        save_path = os.path.join(save_dir, result_file_name)
        with open(save_path, "w") as f:
            f.write(output)

        # Restore original code
        os.system(f"mv {abs_backup_path} {abs_file_path}")

    # dump summary to a json file
    summary = {
        "n_killed_mutants": n_killed_mutants,
        "n_survived_mutants": n_survived_mutants,
        "total_mutants": n_killed_mutants + n_survived_mutants
    }

    with open(os.path.join(save_dir, "mutation_summary.json"), "w") as f:
        json.dump(summary, f, indent=4)

def main(repo_name: str, mutation_dir: str):
    pr_ids = os.listdir(mutation_dir)
    github_repo, cloned_repo_manager = get_repo(repo_name)

    os.makedirs(os.path.join(".cache/mutation_testing", "regression_tests", repo_name), exist_ok=True)
    for pr_id in pr_ids:
        test_pr(repo_name, pr_id, mutation_dir, github_repo, cloned_repo_manager)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mutation analysis for a given repo")
    parser.add_argument("--repo", type=str, required=True, help="Repository name (e.g., pandas)")
    parser.add_argument("--mutation_dir", type=str, required=True, help="Directory to store results")
    args = parser.parse_args()
    main(args.repo, args.mutation_dir)

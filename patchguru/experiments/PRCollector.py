from patchguru.analysis.PRRetriever import get_repo, retrieve_pr
from patchguru.utils.Logger import get_logger
from tqdm import tqdm
import os
from patchguru import Config
import argparse
import time

# Format start time for log file naming
start_time = time.strftime("%Y%m%d-%H%M%S")
logger = get_logger(__name__, log_file=f"logs/pr_collector_{start_time}.log")

def collect_single_changed_function_prs(project_name, n_prs=10):
    logger.info(f"Collecting PRs for project {project_name}...")
    dataset_dir = ".cache/pr_data/single_changed_function_prs"
    os.makedirs(dataset_dir, exist_ok=True)
    dataset_path = os.path.join(dataset_dir, f"{project_name}.txt")
    dataset = set()
    if os.path.exists(dataset_path):
        logger.info(f"Cache found at {dataset_path}, loading existing PRs")
        with open(dataset_path, "r") as f:
            for line in f:
                pr_number = int(line.strip())
                dataset.add(pr_number)
        return dataset

    github_repo, _ = get_repo(project_name)
    logger.info(f"Currently collected {len(dataset)} PRs, continuing collection up to {n_prs}")
    selected_prs = github_repo.get_pulls(state="closed", sort="created", direction="desc")
    selected_prs = [pr for pr in selected_prs if pr.number >= Config.PR_CUT_OFF[project_name]]
    logger.info(f"Total PRs after filtering: {len(selected_prs)}")
    for pr_info in tqdm(selected_prs, desc=f"Collecting PRs for {project_name}"):
        logger.info(f"Dataset size: {len(dataset)}")
        logger.info(len(dataset) >= n_prs)
        if len(dataset) >= n_prs:
            break
        pr_number = int(pr_info.number)

        try:
            pr, _, _ = retrieve_pr(project_name, pr_number)
            if len(pr.changed_functions) == 1 and len(pr.added_functions) == 0 and len(pr.removed_functions) == 0:
                dataset.add(pr_number)
                with open(dataset_path, "w") as f:
                    for pr_number in dataset:
                        f.write(f"{pr_number}\n")
        except Exception as e:
            logger.error(f"Failed to retrieve PR #{pr_number}: {e}")
            continue

    logger.info(f"Collected {len(dataset)}{len(selected_prs)} PRs for project {project_name}. Saving to {dataset_path}")
    with open(dataset_path, "w") as f:
        for pr_number in dataset:
            f.write(f"{pr_number}\n")
    return dataset

def filter_backported_prs(project_name, dataset):
    new_dataset = []
    for pr_nb in dataset:
        # Query pr infomation
        pr, _, _ = retrieve_pr(project_name, pr_nb)
        if "backport" in pr.title.lower():
            logger.info(f"Removed backported PR #{pr_nb}")
            continue
        new_dataset.append(pr_nb)
        print(pr.title)

    dataset_dir = ".cache/pr_data/single_changed_function_prs"
    os.makedirs(dataset_dir, exist_ok=True)
    dataset_path = os.path.join(dataset_dir, f"{project_name}.txt")
    logger.info(f"Saving filtered PRs to {dataset_path}")
    with open(dataset_path, "w") as f:
        for pr_number in new_dataset:
            f.write(f"{pr_number}\n")
    return new_dataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect PRs for a given project.")
    parser.add_argument("-p", "--project", type=str, required=True, help="Project name (e.g., 'scipy' or 'pandas')")
    parser.add_argument("-n", "--n_prs", type=int, default=100, help="Number of PRs to collect (default: 100)")
    args = parser.parse_args()
    dataset = collect_single_changed_function_prs(args.project, n_prs=args.n_prs)

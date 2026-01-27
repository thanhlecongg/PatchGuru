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
    n_normal_cases = 0
    n_failures = 0
    incompleted_prs = []
    bug_found_prs = []

    log_results = parse_logs(log_dir)
    for data_id in data_ids:
        is_failed = False
        data_path = os.path.join(result_dir, data_id, "results.json")
        if not os.path.exists(data_path):
            incompleted_prs.append(data_id)
            continue
        with open(data_path, "r") as f:
            data = json.load(f)
        if data["stage"] in ["completed", "failed"]:
            if data["stage"] == "completed":
                llm_queries = data["llm_queries"]
                if data["review_conclusion"] == "BUG":
                    bug_found_prs.append((os.path.join(result_dir, data_id), data["execution_status"][-1]["error_message"]))
                    n_warnings += 1

                elif data["review_conclusion"] == "NORMAL":
                    phase2_path = os.path.join(result_dir, data_id, "phase2", "results.json")
                    assert os.path.exists(phase2_path), f"Phase 2 results not found for PR {data_id}"
                    with open(phase2_path, "r") as f:
                        phase2_data = json.load(f)
                    if phase2_data["stage"] == "completed":
                        llm_queries += phase2_data["llm_queries"]
                        if phase2_data["review_conclusion"] == "BUG":
                            n_warnings += 1
                            bug_found_prs.append((os.path.join(result_dir, data_id, "phase2"), phase2_data["execution_status"][-1]["error_message"]))
                        elif phase2_data["review_conclusion"] == "NORMAL":
                            n_normal_cases += 1
                    else:
                        is_failed = True
                        n_failures += 1

                else:
                    raise ValueError(f"Unknown review conclusion: {data['review_conclusion']}")
            else:
                is_failed = True
                n_failures += 1
                continue
            if not is_failed:
                assert len(log_results[data_id]["llm_usage"]) == llm_queries, f"LLM queries mismatch for PR {data_id}: log {len(log_results[data_id]['llm_usage'])}, result {llm_queries}, {log_results[data_id]['log_dir']}"
        else:
            incompleted_prs.append(data_id)

    summary = {
        "Total PRs": len(data_ids),
        "#Warnings": n_warnings,
        "#Normal": n_normal_cases,
        "#Oracles": n_warnings + n_normal_cases,
        "#Failures": n_failures,
    }

    # Calculate token usage statistics
    input_token_usage = {}
    output_token_usage = {}
    time_usage = {}

    for pr_nb, log_data in log_results.items():
        input_tokens = 0
        output_tokens = 0
        for usage in log_data["llm_usage"]:
            input_tokens += usage['prompt_tokens']
            output_tokens += usage['completion_tokens']
        input_token_usage[pr_nb] = input_tokens
        output_token_usage[pr_nb] = output_tokens

        first_event_time = log_data["events"][0]["timestamp"]
        last_event_time = log_data["events"][-1]["timestamp"]

        # Convert back to seconds
        first_event_time = datetime.strptime(first_event_time, "%Y%m%d-%H%M%S")
        last_event_time = datetime.strptime(last_event_time, "%Y%m%d-%H%M%S")
        duration = (last_event_time - first_event_time).total_seconds()
        time_usage[pr_nb] = duration

    return input_token_usage, output_token_usage, time_usage, summary

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd
    from matplotlib.ticker import FuncFormatter

    input_token_usage = {}
    output_token_usage = {}
    time_usage = {}
    summary = {}
    _MAPPING = {
        "pandas": "Pandas",
        "scipy": "SciPy",
        "keras": "Keras",
        "marshmallow": "Marshmallow"
    }
    for project in ["pandas", "scipy", "keras", "marshmallow"]:
        project_name = _MAPPING[project]
        project_input_token_usage, project_output_token_usage, project_time_usage, project_summary = analyze(project)
        input_token_usage[project_name] = project_input_token_usage
        output_token_usage[project_name] = project_output_token_usage
        time_usage[project_name] = project_time_usage
        summary[project_name] = project_summary
        
    # Read results of annotated warnings if available
    if os.path.exists(".cache/WarningAnnotation.xlsx"):
        for project in summary.keys():
            # Load sheet for the project
            project_df = pd.read_excel(".cache/WarningAnnotation.xlsx", sheet_name=project.capitalize())
            n_fp = 0
            n_tp = 0
            for idx, row in project_df.iterrows():
                if pd.isna(row["PR"]):
                    continue
                fp = row["FP"]
                tp = row["TP"]
                if fp == 1:
                    n_fp += 1
                if tp == 1:
                    n_tp += 1
            assert n_tp + n_fp == summary[project]["#Warnings"], f"Mismatch in warnings for project {project}, summary {summary[project]['#Warnings']}, annotated {n_tp + n_fp}"
            summary[project]["#TP"] = n_tp
            summary[project]["#FP"] = n_fp
            summary[project]["Precision"] = round(n_tp / (n_tp + n_fp), 2) if (n_tp + n_fp) > 0 else 0.0
    
    # Print table summary
    print("--------------- RQ1: Effectiveness of PatchGuru (Table 1) ---------------")
    df_summary = pd.DataFrame.from_dict(summary, orient="index")
    print(df_summary)      

    # Print overall summary of average token usage and time usage
    overall_records = []
    merged_time = []
    merged_input_tokens = []
    merged_output_tokens = []
    for project, project_summary in summary.items():
        n_oracles = project_summary["#Oracles"]
        avg_input_tokens = np.mean(list(input_token_usage[project].values()))
        avg_output_tokens = np.mean(list(output_token_usage[project].values()))
        avg_time = np.mean(list(time_usage[project].values()))
        merged_time.extend(list(time_usage[project].values()))
        merged_input_tokens.extend(list(input_token_usage[project].values()))
        merged_output_tokens.extend(list(output_token_usage[project].values()))
        overall_records.append({
            "Project": project,
            "Avg Input Tokens": round(avg_input_tokens, 1),
            "Avg Output Tokens": round(avg_output_tokens, 1),
            "Avg Time (m)": round(avg_time/60, 1),
            "#Oracles": n_oracles,
            "Cost Input ($)": round(avg_input_tokens * (0.25 / 1_000_000), 6),
            "Cost Output ($)": round(avg_output_tokens * (2.0 / 1_000_000), 6),
            "Total Cost ($)": round((avg_input_tokens * (0.25 / 1_000_000)) + (avg_output_tokens * (2.0 / 1_000_000)), 6)
        })
    
    # Calculate total averages
    overall_records.append({
        "Project": "Overall",
        "Avg Input Tokens": round(np.mean(merged_input_tokens), 1),
        "Avg Output Tokens": round(np.mean(merged_output_tokens), 1),
        "Avg Time (m)": round(np.mean(merged_time)/60, 1),
        "#Oracles": sum([summary[proj]["#Oracles"] for proj in summary]),
        "Cost Input ($)": round(np.mean(merged_input_tokens) * (0.25 / 1_000_000), 6),
        "Cost Output ($)": round(np.mean(merged_output_tokens) * (2.0 / 1_000_000), 6),
        "Total Cost ($)": round((np.mean(merged_input_tokens) * (0.25 / 1_000_000)) + (np.mean(merged_output_tokens) * (2.0 / 1_000_000)), 6)
    })
    
    df_overall = pd.DataFrame.from_records(overall_records)
    print("\n--------------- RQ3: Costs and Time ---------------")
    print(df_overall)    
    
    print("\nDrawing Violin Plots for Token and Time Usage (Figure 4)\n")
    # Create violin plots with mean and median lines
    from matplotlib.lines import Line2D
    
    metrics = [
        ("input_token_usage", "Input Tokens"),
        ("output_token_usage", "Output Tokens"),
        ("time_usage", "Time (seconds)")
    ]

    # Formatter to display thousands as K on y-axis
    def k_formatter(x, pos):
        if x >= 1000 or x <= -1000:
            s = f"{x/1000:.1f}".rstrip('0').rstrip('.')
            return f"{s}K"
        return f"{x:.0f}"

    # Cost rates per token (USD)
    INPUT_COST_PER_TOKEN = 0.25 / 1_000_000
    OUTPUT_COST_PER_TOKEN = 2.0 / 1_000_000

    # Formatter factory to show cost on secondary y-axis
    def make_cost_formatter(rate):
        def _fmt(x, pos):
            dollars = x * rate
            if abs(dollars) >= 1000:
                s = f"{dollars/1000:.1f}".rstrip('0').rstrip('.')
                return f"${s}K"
            # Use more precision for small values
            if abs(dollars) < 1:
                return f"${dollars:.3f}"
            return f"${dollars:.2f}"
        return FuncFormatter(_fmt)
    
    for metric_key, metric_label in metrics:
        metric_data = [input_token_usage, output_token_usage, time_usage]
        data_dict = metric_data[metrics.index((metric_key, metric_label))]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Prepare data for violin plot
        project_names = list(data_dict.keys())
        data_values = [list(data_dict[proj].values()) for proj in project_names]
        
        # Create violin plot
        parts = ax.violinplot(data_values, positions=range(len(project_names)), widths=0.6, 
                              showmeans=False, showextrema=False, showmedians=False)
        
        # Style violin plot bodies
        for pc in parts['bodies']:
            pc.set_facecolor('skyblue')
            pc.set_edgecolor('black')
            pc.set_alpha(0.7)
        
        # Add median and mean lines for each project
        medians = [np.median(vals) for vals in data_values]
        means = [np.mean(vals) for vals in data_values]
        
        for x, (median, mean) in enumerate(zip(medians, means)):
            ax.hlines(median, x - 0.3, x + 0.3, colors='blue', linewidth=2, label='Median' if x == 0 else '')
            ax.hlines(mean, x - 0.3, x + 0.3, colors='red', linestyles='dashed', linewidth=1.5, label='Mean' if x == 0 else '')
            
            # Format values with K suffix for thousands
            def format_value(val):
                if val >= 1000:
                    return f"{val/1000:.1f}K"
                return f"{val:.1f}"
            
            # Add text labels for median and mean with smart positioning
            y_range = max(data_values[x]) - min(data_values[x])
            offset = 0.05 * y_range if y_range != 0 else 1
            
        # Configure plot
        ax.set_xticks(range(len(project_names)))
        ax.set_xticklabels(project_names, fontsize=24)
        ax.set_ylabel(metric_label, fontsize=24)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Set font size of y-ticks
        ax.tick_params(axis='y', labelsize=20)
        # Format y-axis ticks as K for thousands
        ax.yaxis.set_major_formatter(FuncFormatter(k_formatter))

        # Add corresponding right-side cost axis for token plots
        rate = None
        if metric_key == "input_token_usage":
            rate = INPUT_COST_PER_TOKEN
        elif metric_key == "output_token_usage":
            rate = OUTPUT_COST_PER_TOKEN

        if rate is not None:
            ax2 = ax.twinx()
            ax2.set_ylim(ax.get_ylim())
            ax2.yaxis.set_major_formatter(make_cost_formatter(rate))
            ax2.set_ylabel("Cost ($)", fontsize=24)
            ax2.tick_params(axis='y', labelsize=20)
        
        # Add legend
        legend_elements = [
            Line2D([0], [0], color='blue', linewidth=2, label='Median'),
            Line2D([0], [0], color='red', linestyle='--', linewidth=1.5, label='Mean')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=20)
        
        plt.tight_layout()
        output_file = f".cache/violin_plot/{metric_key}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved figure to {output_file}")
        plt.show()
    

    

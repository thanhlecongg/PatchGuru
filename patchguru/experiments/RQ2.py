import os
import numpy as np
import json
import pandas as pd
from scipy.stats import wilcoxon
import matplotlib.pyplot as plt
import seaborn as sns

PROJECTS = ["scipy", "marshmallow", "pandas", "keras"]
PHASE = "phase2"

# Store results for unified plot
all_results = {}

for project in PROJECTS:
    data_ids = []
    with open(f".cache/pr_ids/{project}.txt", "r") as f:
        for line in f:
            data_ids.append(line.strip())

    patchguru_completion_rates = []
    regression_completion_rates = []
    combined_completion_rates = []
    
    for data_id in os.listdir(f".cache/oracles/{project}"):
        if data_id not in data_ids:
            print(f"Data ID {data_id} not in target list for project {project}, skipping.")

    for data_id in data_ids:
        patchguru_dir = f".cache/mutation_testing/{project}/patchguru" + f"/{data_id}"
        regression_dir = f".cache/mutation_testing/{project}/regression_tests" + f"/{data_id}"
        patchguru_path = os.path.join(patchguru_dir, "mutation_results.json")
        regression_path = os.path.join(regression_dir, "mutation_summary.json")

        if PHASE == "phase2":
            phase2_patchguru_path = os.path.join(patchguru_dir, "phase2", "mutation_results.json")
            if os.path.exists(phase2_patchguru_path):
                patchguru_path = phase2_patchguru_path
                patchguru_dir = os.path.join(patchguru_dir, "phase2")

        if not os.path.exists(patchguru_path) or not os.path.exists(regression_path):
            continue

        with open(patchguru_path) as f:
            mutation_results = json.load(f)

        patchguru_survived = mutation_results["n_mutant_pass"]
        patchguru_killed = mutation_results["n_mutant_fail_assert"] + mutation_results["n_mutant_fail_other"]
        n_total = patchguru_survived + patchguru_killed

        if n_total == 0:
            continue

        completion_rate = patchguru_killed / n_total
        patchguru_completion_rates.append(completion_rate)

        with open(regression_path) as f:
            regression_results = json.load(f)

        regression_survived = regression_results["n_survived_mutants"]
        regression_killed = regression_results["n_killed_mutants"]
        n_total_regression = regression_survived + regression_killed
        assert n_total == n_total_regression, f"Mismatch in total mutants for {data_id}"

        regression_completion_rate = regression_killed / n_total_regression
        regression_completion_rates.append(regression_completion_rate)
        
        detailed_results = {
            "patchguru": {},
            "regression": {}
        }
        for file_name in os.listdir(patchguru_dir):
            if file_name.startswith("mutant_"):
                _id = file_name.split("_")[1]
                _res = file_name.split("_")[-1]
                if _res.replace(".py", "") == "pass":
                    detailed_results["patchguru"][_id] = "survived"
                else:
                    detailed_results["patchguru"][_id] = "killed"
        
        for file_name in os.listdir(regression_dir):
            if file_name.startswith("mutant_"):
                _id = file_name.split("_")[1]
                _res = file_name.split("_")[-1]
                if _res.replace(".txt", "") == "survived":
                    detailed_results["regression"][_id] = "survived"
                else:
                    detailed_results["regression"][_id] = "killed"
        
        combined_killed = 0
        for mutant_id in detailed_results["patchguru"]:
            if mutant_id not in detailed_results["regression"]:
                assert len(detailed_results["regression"].keys()) == 0, "If one method has no result, both should have no result"
                if (detailed_results["patchguru"][mutant_id] == "killed"):
                    combined_killed += 1
            else:
                if (detailed_results["patchguru"][mutant_id] == "killed" or 
                    detailed_results["regression"][mutant_id] == "killed"):
                    combined_killed += 1
        combined_completion_rate = combined_killed / n_total
        combined_completion_rates.append(combined_completion_rate)
        
    if len(patchguru_completion_rates) > 0:
        all_results[project] = {
            'PatchGuru': patchguru_completion_rates,
            'Regression Tests': regression_completion_rates,
            'Combined': combined_completion_rates
        }
    else:
        print("No data available for statistical analysis")

_MAPPING = {
    "scipy": "SciPy",
    "marshmallow": "Marshmallow",
    "pandas": "Pandas",
    "keras": "Keras"
}

records = []
for project, methods in all_results.items():
    for method, rates in methods.items():
        for rate in rates:
            records.append({
                "Project": _MAPPING[project],
                "Method": method,
                "Completion Rate": rate,
            })

print("--------------- RQ2: Adequacy of Inferred Patch Oracles ---------------")
print("----- Table 3 -----")
df = pd.DataFrame.from_records(records)
print("\nCompletion Rates Summary:")
print(df.pivot_table(index='Project', columns='Method', values='Completion Rate', aggfunc='mean').round(2))
overall_summary = df.pivot_table(index='Method', values='Completion Rate', aggfunc=['mean', 'std']).round(2)
print("\nOverall Completion Rates Summary:")
print(overall_summary)

# Draw violin plots similar to mutation_testing_3
from matplotlib.lines import Line2D

METHOD_COLORS = {
    'PatchGuru': 'skyblue',
    'Regression Tests': 'lightgreen',
    'Combined': 'lightcoral'
}

# Single grouped figure: compare methods per project
methods = ['PatchGuru', 'Regression Tests', 'Combined']
projects = sorted(set(df['Project'].unique()))

# Prepare data dict: project -> method -> list of values
proj_method_values = {proj: {m: [] for m in methods} for proj in projects}
for proj in projects:
    for m in methods:
        vals = df[(df['Project'] == proj) & (df['Method'] == m)]['Completion Rate'].tolist()
        proj_method_values[proj][m] = vals

fig, ax = plt.subplots(figsize=(12, 7))

# Offsets for side-by-side violins within each project
offsets = {
    'PatchGuru': -0.25,
    'Regression Tests': 0.0,
    'Combined': 0.25
}
width = 0.25

from matplotlib.patches import Patch
method_legend = []

# Plot each method with its own set of violins at offset positions
for m in methods:
    data_values = []
    positions = []
    for i, proj in enumerate(projects):
        vals = proj_method_values[proj][m]
        if len(vals) == 0:
            continue
        data_values.append(vals)
        positions.append(i + offsets[m])

    if len(data_values) == 0:
        continue

    parts = ax.violinplot(
        data_values,
        positions=positions,
        widths=width,
        showmeans=False,
        showextrema=False,
        showmedians=False
    )
    for pc in parts['bodies']:
        pc.set_facecolor(METHOD_COLORS.get(m, 'skyblue'))
        pc.set_edgecolor('black')
        pc.set_alpha(0.7)

    # Add median and mean lines per small violin
    medians = [np.median(vals) for vals in data_values]
    means = [np.mean(vals) for vals in data_values]
    for x, (median, mean) in zip(positions, zip(medians, means)):
        ax.hlines(median, x - width/2, x + width/2, colors='red', linewidth=2)
        ax.hlines(mean, x - width/2, x + width/2, colors='blue', linestyles='dashed', linewidth=1.5)

    method_legend.append(Patch(facecolor=METHOD_COLORS.get(m, 'skyblue'), edgecolor='black', label=m))

# Formatting: center ticks at project indices
ax.set_xticks(range(len(projects)))
ax.set_xticklabels(projects, fontsize=24)
ax.set_ylabel('Mutation Score', fontsize=24)
# Increase y-axis font size
ax.tick_params(axis='y', labelsize=20)
ax.grid(axis='y', linestyle='--', alpha=0.7)
ax.set_ylim(-0.05, 1.05)

# Legends: one for methods, one for mean/median
stat_legend = [
    Line2D([0], [0], color='red', linewidth=2, label='Median'),
    Line2D([0], [0], color='blue', linestyle='--', linewidth=1.5, label='Mean')
]
leg1 = ax.legend(handles=method_legend, loc='lower left', fontsize=20)
ax.add_artist(leg1)
ax.legend(handles=stat_legend, loc='lower right', fontsize=20)

plt.tight_layout()
print("----- Figure 3 -----")
output_file = ".cache/violin_plot/completion_rate.png"
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"Saved figure to {output_file}")
plt.show()

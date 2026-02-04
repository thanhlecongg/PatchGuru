# PatchGuru: Patch Oracle Inference from Natural Language Artifacts with Large Language Models

PatchGuru is an LLM-powered tool that automatically infer patch oracles from natural language artifacts in pull requests and utilizes them to detect the inconsistencies between code changes and their corresponding descriptions.

Paper: [TO BE RELEASE]()

## Installation

### Setup Enviroments of PatchGuru
PatchGuru uses two kinds of Docker containers:

- A Visual Studio Code Dev Container for running PatchGuru itself. See [devcontainer.json](.devcontainer/devcontainer.json).
- Docker-in-docker containers for target projects to analyze with PatchGuru. These containers are created when creating the dev container. See [postCreateCommands.sh](.devcontainer/postCreateCommand.sh).

To install and run PatchGuru, follow these steps:

1) Install [Visual Studio Code](https://code.visualstudio.com/download) and its ["Dev Containers" extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).

2) Open PatchGuru in Visual Studio Code:
   
   ```code <main_dir_of_this_project>```

3) In Visual Studio Code, build the Dev Container and reopen the project in the container:

    ```Ctrl + Shift + P```

    ```Dev Containers: Rebuild and Reopen in Container```

    This will take a couple of minutes, because in addition to Testora, it will set up three instances of the project under analysis. We use three instances to efficiently switch between the commits just before and just after a PR, as well as the latest commit in the main branch. 

4) In the main directory, create a file `.openai_token` with an OpenAI API key. This is required for invoking an LLM, which is an essential part of Testora.

5) In the main directory, create a file `.github_token` with a (free to create) GitHub API key. This is required because Testora interacts with the GitHub API to retrieve details about the PRs to analyze.

### Setup Enviroments of Target Projects
Currently, PatchGuru supports the analysis on four Python projects: Scipy, Pandas, Marshmallow and Keras. To setup these project, please do one for two following ways:
1. Uncomment selected projects in [postCreateCommands.sh](.devcontainer/postCreateCommand.sh)
2. Or, just run `bash .devcontainer/setup_{project}` inside the docker container of PatchGuru

If you wish to setup a new target project, please provide a script following setup scripts of current projects. Feel free to submit the PRs to add these scripts to PatchGuru

## Usage

> [!NOTE]
> PatchGuru currently supports only pull requests that modify a single source function (excluding test functions).


`patchguru/SpecInfer.py` is the main entry point to run PatchGuru. To apply it to a specific PR of a project, please use the following command:

```
python3 -m patchguru.SpecInfer --project [PROJECT NAME, e.g., pandas] --pr_nb [ID of the target PR]
```

For example, if you want to analyze PR#707 of Marshmallow, please run:

```
python3 -m patchguru.SpecInfer --project marshmallow --pr_nb 707
```

## Results Reported in the Paper

Please download our data from [Figshare](https://figshare.com/s/02089e7f903926ad0cdf). This data contains two folders: `.cache` and `.logs` which contains raw results and logs of PatchGuru. 

### RQ1 & RQ3

To replicate the results of RQ1 and RQ3, please run the following command:
```
python3 -m patchguru.experiments.RQ1_3
```
This will provides the detailed results of RQ1 and RQ3 including Table 1 and Figure 4 in the paper. Please refers to [WarningAnnotation.xlsx](.cache/WarningAnnotation.xlsx) for detailed inspection results of RQ1 and information of bugs found by PatchGuru (Table 2). 

### RQ2

To replicate the results of RQ2, please run the following command:
```
python3 -m patchguru.experiments.RQ2
```
This will provides the detailed results of RQ2 including Table 3 and Figure 3 in the paper.

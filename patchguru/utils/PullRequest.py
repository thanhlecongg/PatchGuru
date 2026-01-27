# This file is developed based on the code from the [Testora](https://github.com/michaelpradel/Testora) project by Michael Pradel.
from unidiff import PatchSet
import urllib.request
from patchguru.utils.PythonCodeUtil import (
    equal_modulo_docstrings,
    extract_target_function_by_range,
    get_name_of_defined_function,
    get_locations_of_calls_by_range,
    extract_imported_modules,
    convert_import_dict_to_string,
    get_top_level_function_and_class,
    get_class_name
)
from patchguru import Config
import os
import pickle
from patchguru.utils.Tracker import append_event, Event

class PullRequest:
    def __init__(self, github_pr, github_repo, cloned_repo_manager):

        self.github_pr = github_pr
        self.cloned_repo_manager = cloned_repo_manager
        self.number = github_pr.number
        self.title = github_pr.title
        self.post_commit = github_pr.merge_commit_sha
        self.parents = github_repo.get_commit(self.post_commit).parents
        self.pre_commit = self.parents[0].sha

        # Define cache path
        cache_dir = ".cache/PullRequestData/{}".format(github_repo.full_name)
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"pr_{self.number}_{self.post_commit}.pkl")

        # Try to load from cache
        if os.path.exists(cache_file):
            append_event(Event(
                level="DEBUG", pr_nb=self.number,
                message=f"Cache hit for PR #{self.number}, loading from cache"
            ))
            with open(cache_file, "rb") as f:
                cached = pickle.load(f)
            try:
                self.patch = cached["patch"]
                self.non_test_modified_python_files = cached["non_test_modified_python_files"]
                self.non_test_modified_code_files = cached["non_test_modified_code_files"]
                self.old_file_path_to_modified_lines = cached["old_file_path_to_modified_lines"]
                self.new_file_path_to_modified_lines = cached["new_file_path_to_modified_lines"]
                self.has_non_comment_change = cached["has_non_comment_change"]
                self.prev_fut_info = cached["prev_fut_info"]
                self.prev_required_imports = cached["prev_required_imports"]
                self.post_fut_info = cached["post_fut_info"]
                self.post_required_imports = cached["post_required_imports"]
                self.changed_functions = cached["changed_functions"]
                self.added_functions = cached["added_functions"]
                self.removed_functions = cached["removed_functions"]
                self.required_imports = cached["required_imports"]
                self.import_string = cached["import_string"]
                self.changed_file_contents = cached["changed_file_contents"]
                return
            except KeyError as e:
                append_event(Event(
                    level="WARNING", pr_nb=self.number,
                    message=f"Failed to load cache for PR #{self.number}: {e}. Re-initializing from scratch."
                ))
        try:

            self._pr_url_to_patch()
            self._compute_non_test_modified_files()
            self._compute_modified_lines()

            self.has_non_comment_change = self.count_non_comment_change() > 0

            self.prev_fut_info, self.prev_required_imports = self.get_changed_function_info(version="pre_commit")
            self.post_fut_info, self.post_required_imports = self.get_changed_function_info(version="post_commit")

            self.changed_functions = set(self.prev_fut_info.keys()).union(set(self.post_fut_info.keys()))
            self.added_functions = set(self.post_fut_info.keys()).difference(set(self.prev_fut_info.keys()))
            self.removed_functions = set(self.prev_fut_info.keys()).difference(set(self.post_fut_info.keys()))
            self.required_imports = self.prev_required_imports
            for module, imports in self.post_required_imports.items():
                if module not in self.required_imports:
                    self.required_imports[module] = set()
                self.required_imports[module].update(imports)

            self.import_string = convert_import_dict_to_string(self.required_imports)
            self.changed_file_contents = self.get_changed_file_contents()

            # Save to cache
            with open(cache_file, "wb") as f:
                cached_data = {
                    "patch": self.patch,
                    "non_test_modified_python_files": self.non_test_modified_python_files,
                    "non_test_modified_code_files": self.non_test_modified_code_files,
                    "old_file_path_to_modified_lines": self.old_file_path_to_modified_lines,
                    "new_file_path_to_modified_lines": self.new_file_path_to_modified_lines,
                    "has_non_comment_change": self.has_non_comment_change,
                    "prev_fut_info": self.prev_fut_info,
                    "prev_required_imports": self.prev_required_imports,
                    "post_fut_info": self.post_fut_info,
                    "post_required_imports": self.post_required_imports,
                    "changed_functions": self.changed_functions,
                    "added_functions": self.added_functions,
                    "removed_functions": self.removed_functions,
                    "required_imports": self.required_imports,
                    "import_string": self.import_string,
                    "changed_file_contents": self.changed_file_contents,
                }
                pickle.dump(cached_data, f)
                append_event(Event(
                    level="DEBUG", pr_nb=self.number,
                    message=f"Saved PR #{self.number} data to cache: {cache_file}"
                ))
        except Exception as e:
            append_event(Event(
                level="ERROR", pr_nb=self.number,
                message=f"Failed to get changed function info for PR #{self.number}: {e}"
            ))
            with open(cache_file, "wb") as f:
                cached_data = {
                    "error": str(e)
                }
                pickle.dump(cached_data, f)
            raise e

    def _pr_url_to_patch(self):
        diff_url = self.github_pr.html_url + ".diff"
        diff = urllib.request.urlopen(diff_url)
        encoding = diff.headers.get_charsets()[0]
        self.patch = PatchSet(diff, encoding=encoding)

    def _compute_non_test_modified_files(self):
        module_name = self.cloned_repo_manager.module_name

        # Python files only
        modified_python_files = [
            f for f in self.patch.modified_files if f.path.endswith(".py") or f.path.endswith(".pyx")]
        self.non_test_modified_python_files = [
            f.path for f in modified_python_files if "test" not in f.path and (f.path.startswith(module_name) or f.path.startswith(f"src/{module_name}"))]

        # Python and other PLs
        modified_code_files = [
            f for f in self.patch.modified_files if
            f.path.endswith(".py") or
            f.path.endswith(".pyx") or
            f.path.endswith(".c") or
            f.path.endswith(".cpp") or
            f.path.endswith(".h")
        ]
        self.non_test_modified_code_files = [
            f.path for f in modified_code_files if "test" not in f.path and (f.path.startswith(module_name) or f.path.startswith(f"src/{module_name}"))]

    def get_modified_files(self):
        if Config.PL == "python":
            return self.non_test_modified_python_files
        elif Config.PL == "all":
            return self.non_test_modified_code_files

    def count_non_comment_change(self):
        if Config.PL == "all":
            return len(self.non_test_modified_code_files) > 0

        pre_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(
            self.pre_commit)
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(
            self.post_commit)

        self.files_with_non_comment_changes = []
        for modified_file in self.non_test_modified_python_files:
            with open(f"{pre_commit_cloned_repo.repo.working_dir}/{modified_file}", "r") as f:
                old_file_content = f.read()
            with open(f"{post_commit_cloned_repo.repo.working_dir}/{modified_file}", "r") as f:
                new_file_content = f.read()
            if not equal_modulo_docstrings(old_file_content, new_file_content):
                self.files_with_non_comment_changes.append(modified_file)

        self.files_with_non_comment_changes = list(dict.fromkeys(
            self.files_with_non_comment_changes))  # turn into set while preserving order
        return len(self.files_with_non_comment_changes) > 0

    def get_changed_file_contents(self):
        cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
        file_contents = {}
        for modified_file in self.non_test_modified_python_files:
            module_name = modified_file.replace("/", ".")
            if module_name.endswith(".py"):
                    module_name = module_name[:-3]
            elif module_name.endswith(".pyx"):
                module_name = module_name[:-4]
            elif module_name.startswith("src."):
                module_name = module_name[4:]
            with open(f"{cloned_repo.repo.working_dir}/{modified_file}", "r") as f:
                content = f.read()
            file_contents[module_name] = content
        return file_contents

    def _get_relevant_changed_files(self) -> list[str]:
        if Config.PL == "python":
            return self.files_with_non_comment_changes
        elif Config.PL == "all":
            return self.non_test_modified_code_files
        else:
            raise Exception(
                f"Unexpected configuration value: {Config.PL}")

    def get_filtered_diff(self):
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(
            self.post_commit)

        diff_parts = []
        for file_path in self._get_relevant_changed_files():
            raw_diff = post_commit_cloned_repo.repo.git.diff(
                self.pre_commit, self.post_commit, file_path)
            diff_parts.append(raw_diff)

        return "\n\n".join(diff_parts)

    def get_full_diff(self):
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(
            self.post_commit)

        return post_commit_cloned_repo.repo.git.diff(self.pre_commit, self.post_commit)

    def get_changed_function_info(self, version):
        result = {}
        required_imports = {}

        assert version in ["pre_commit", "post_commit"], \
            f"Unexpected version: {version}. Expected 'pre_commit' or 'post_commit'."

        if version == "pre_commit":
            cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
        else:
            cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)

        for modified_file in self.patch.modified_files:
            if modified_file.path in self._get_relevant_changed_files():
                with open(f"{cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                    new_file_content = f.read()

                top_level_function_and_class = get_top_level_function_and_class(new_file_content)
                module_name = modified_file.path.replace("/", ".")
                if module_name.endswith(".py"):
                    module_name = module_name[:-3]
                elif module_name.endswith(".pyx"):
                    module_name = module_name[:-4]
                if module_name.startswith("src."):
                    module_name = module_name[4:]

                changed_function_names = set()
                for hunk in modified_file:
                    start_line = hunk.target_start
                    end_line = hunk.target_start + hunk.target_length
                    patch_range = (start_line, end_line)
                    fct_code, fct_start_line, fct_end_line = extract_target_function_by_range(
                        new_file_content, patch_range)
                    if fct_code is not None:
                        fct_name = get_name_of_defined_function(fct_code)
                        if fct_name:
                            changed_function_names.add(fct_name)
                            context_code = None
                            class_name = None
                            for typ, name, start_line, end_line, code in top_level_function_and_class:
                                if typ == "class" and start_line <= fct_start_line <= end_line and start_line <= fct_end_line <= end_line:
                                    context_code = code
                                    class_name = get_class_name(context_code)
                                    class_name = f"### {module_name}.{class_name}#{start_line}-{end_line}"

                            result[f"{module_name}.{fct_name}"] = {
                                "file_path": modified_file.path,
                                "start_line": fct_start_line,
                                "end_line": fct_end_line,
                                "code": fct_code,
                                "context_class": class_name,
                                "context_code": context_code
                            }

                sub_modules = module_name.split(".")
                imported_modules = extract_imported_modules(new_file_content)
                imported_modules_with_full_paths = {}
                for module, imports in imported_modules.items():
                    dot_cnt = 0
                    for c in module:
                        if c == ".":
                            dot_cnt += 1
                        else:
                            break

                    if dot_cnt >= 1:
                        used_sub_modules = sub_modules[:-dot_cnt]
                        module= ".".join(used_sub_modules + [module[dot_cnt:]])
                        if module.endswith("."):
                            module = module[:-1]
                    imported_modules_with_full_paths[module] = imports

                for module, imports in imported_modules_with_full_paths.items():
                    if module not in required_imports:
                        required_imports[module] = set()
                    required_imports[module].update(imports)

                all_function_and_class_names = [name for _, name, _, _, _ in top_level_function_and_class]

                # import everything from modified file
                required_imports[module_name] = set()
                for name in all_function_and_class_names:
                    if name not in changed_function_names:
                        required_imports[module_name].add((name, None))
        return result, required_imports

    def _compute_modified_lines(self):
        self.old_file_path_to_modified_lines = {}
        self.new_file_path_to_modified_lines = {}

        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(
            self.post_commit)
        diff = post_commit_cloned_repo.repo.git.diff(
            self.pre_commit, self.post_commit)
        patch = PatchSet(diff)

        for patched_file in patch:
            self.old_file_path_to_modified_lines[patched_file.path] = set()
            self.new_file_path_to_modified_lines[patched_file.path] = set()
            for hunk in patched_file:
                for line in hunk:
                    if line.is_removed:
                        self.old_file_path_to_modified_lines[patched_file.path].add(
                            line.source_line_no)
                    elif line.is_added:
                        self.new_file_path_to_modified_lines[patched_file.path].add(
                            line.target_line_no)

    def get_relevant_docstrings(self, version="post_commit"):
        """
        Returns a list of docstrings that are relevant to the changed functions.
        """
        if version == "post_commit":
            cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)
            fut_info = self.post_fut_info
        elif version == "pre_commit":
            cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
            fut_info = self.prev_fut_info
        else:
            raise ValueError(f"Unexpected version: {version}. Expected 'pre_commit' or 'post_commit'.")

        result = ""
        for fut_name, fut_data in fut_info.items():
            file_path = fut_data["file_path"]
            start_line = fut_data["start_line"]
            end_line = fut_data["end_line"]
            f"{cloned_repo.repo.working_dir}/{file_path}"
            with open(f"{cloned_repo.repo.working_dir}/{file_path}", "r") as f:
                file_content = f.read()

            call_locations = get_locations_of_calls_by_range(
                file_content, start_line, end_line
            )


            server = cloned_repo.language_server
            docs = []
            for call_location in call_locations:
                line = call_location.start.line - 1  # LSP lines are 0-based
                column = call_location.start.column
                doc = server.get_hover_text(file_path, line, column + 1)
                if doc not in docs:
                    docs.append(doc)

            # enforce limits: max 2000 chars per docstring, max 6000 chars overall
            for doc in docs:
                result += "\n\n-------\n"
                result += doc[:2000]

        return result[:6000]  # limit to 6000 chars in total

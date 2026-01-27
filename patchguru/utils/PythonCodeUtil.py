import builtins
from dataclasses import dataclass
from typing import Dict, List, Optional, Mapping
import libcst as cst
import ast
from libcst._nodes.base import CSTNode
from libcst.metadata.base_provider import ProviderT

builtin_functions = [func for func in dir(
    builtins) if callable(getattr(builtins, func))]

@dataclass
class ParameterInfo:
    """Information about a function parameter."""

    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None
    kind: str = "regular"  # regular, *args, **kwargs


@dataclass
class FunctionInfo:
    """Information about a function."""

    name: str
    parameters: List[ParameterInfo]
    return_type: Optional[str] = None
    docstring: Optional[str] = None


class FunctionExtractor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)


    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self.nodes_and_lines = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Visit function definitions and extract information."""
        function_info = self._extract_function_info(node)
        self.functions.append(function_info)

        start_pos = self.get_metadata(cst.metadata.PositionProvider, node).start
        end_pos = self.get_metadata(cst.metadata.PositionProvider, node).end
        self.nodes_and_lines.append((node, start_pos.line, end_pos.line))

    def _extract_function_info(self, node: cst.FunctionDef) -> FunctionInfo:
        """Extract complete function information."""
        name = node.name.value
        parameters = self._extract_parameters(node.params)
        return_type = self._extract_return_type(node.returns)
        docstring = self._extract_docstring(node.body)

        return FunctionInfo(name=name, parameters=parameters, return_type=return_type, docstring=docstring)

    def _extract_parameters(self, params: cst.Parameters) -> List[ParameterInfo]:
        """Extract parameter information from function parameters."""
        param_list = []

        # Regular parameters
        for param in params.params:
            param_info = self._extract_param_info(param, "regular")
            param_list.append(param_info)

        # *args parameter
        if params.star_arg and isinstance(params.star_arg, cst.Param):
            param_info = self._extract_param_info(params.star_arg, "*args")
            param_list.append(param_info)

        # Keyword-only parameters
        for param in params.kwonly_params:
            param_info = self._extract_param_info(param, "keyword-only")
            param_list.append(param_info)

        # **kwargs parameter
        if params.star_kwarg:
            param_info = self._extract_param_info(params.star_kwarg, "**kwargs")
            param_list.append(param_info)

        return param_list

    def _extract_param_info(self, param: cst.Param, kind: str) -> ParameterInfo:
        """Extract information from a single parameter."""
        name = param.name.value
        type_annotation = None
        default_value = None

        # Extract type annotation
        if param.annotation:
            type_annotation = cst.Module([
                cst.SimpleStatementLine([cst.Expr(param.annotation.annotation)])
            ]).code.strip()

        # Extract default value
        if param.default:
            default_value = cst.Module([cst.SimpleStatementLine([cst.Expr(param.default)])]).code.strip()

        return ParameterInfo(
            name=name,
            type_annotation=type_annotation,  # This is the parameter type
            default_value=default_value,
            kind=kind,
        )

    def _extract_return_type(self, returns: Optional[cst.Annotation]) -> Optional[str]:
        """Extract return type annotation."""
        if returns:
            return cst.Module([cst.SimpleStatementLine([cst.Expr(returns.annotation)])]).code.strip()
        return None

    def _extract_docstring(self, body: cst.BaseSuite) -> Optional[str]:
        """Extract docstring from function body."""
        if isinstance(body, cst.SimpleStatementSuite):
            return None

        statements = body.body
        if statements and isinstance(statements[0], cst.SimpleStatementLine):
            first_stmt = statements[0].body[0]
            if isinstance(first_stmt, cst.Expr) and isinstance(first_stmt.value, cst.SimpleString):
                # Remove quotes and clean up the docstring
                docstring = first_stmt.value.value
                if docstring.startswith('"""') or docstring.startswith("'''"):
                    return docstring[3:-3].strip()
                elif docstring.startswith('"') or docstring.startswith("'"):
                    return docstring[1:-1].strip()
        return None


class ImportExtractor(cst.CSTVisitor):
    def __init__(self):
        self.imports = []

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self.imports.append(node)

    def visit_Import(self, node: cst.Import) -> None:
        self.imports.append(node)


def get_parameter_types(func_info: FunctionInfo) -> Dict[str, Optional[str]]:
    """
    Get a dictionary mapping parameter names to their types.

    Args:
        func_info: Function information object

    Returns:
        Dictionary of parameter name -> type annotation
    """
    return {param.name: param.type_annotation for param in func_info.parameters}


def extract_function_info(code: str) -> List[FunctionInfo]:
    """
    Extract function information from Python code.

    Args:
        code: Python source code as string

    Returns:
        List of FunctionInfo objects containing function details

    Raises:
        cst.ParserError: If the code cannot be parsed
    """
    try:
        tree = cst.parse_expression(code) if code.strip().startswith("lambda") else cst.parse_module(code)
        # Use MetadataWrapper to enable metadata access
        wrapper = cst.metadata.MetadataWrapper(tree)
        extractor = FunctionExtractor()
        wrapper.visit(extractor)
        return extractor.functions
    except Exception as e:
        raise ValueError(f"Failed to parse code: {e}")


def get_function_signature(code: str) -> str:
    """
    Get the function signature from the provided code.

    Args:
        code: Python function code as string

    Returns:
        Function signature as a string
    """

    try:
        func_info = extract_function_info(code)[0]  # Assuming the first function is the target
    except IndexError:
        raise ValueError("No function found in the provided code")

    params = []
    for param in func_info.parameters:
        param_str = param.name

        if param.type_annotation:
            param_str += f": {param.type_annotation}"

        if param.default_value:
            param_str += f" = {param.default_value}"

        if param.kind == "*args":
            param_str = f"*{param_str}"
        elif param.kind == "**kwargs":
            param_str = f"**{param_str}"

        params.append(param_str)

    signature = f"def {func_info.name}({', '.join(params)})"

    if func_info.return_type:
        signature += f" -> {func_info.return_type}"

    return signature + ":"

def get_data_provider_code(param_name: str, data_type: str) -> str:
    if data_type == "int":
        return f"""
    {param_name} = fdp.ConsumeIntInRange(1, 100)

    """
    if data_type == "dict" or data_type == "dict[str, str]":
        code = f"""
    key1 = fdp.ConsumeString(10)
    value1 = fdp.ConsumeString(10)
    key2 = fdp.ConsumeString(10)
    value2 = fdp.ConsumeString(10)
    {param_name} = {{key1: value1, key2: value2}}

        """
        return code
    if data_type == "str":
        return f"""
    {param_name} = fdp.ConsumeString(10)

    """

    if data_type == "list[dict]":
        code = f"""
    key1 = fdp.ConsumeString(10)
    value1 = fdp.ConsumeString(10)
    key2 = fdp.ConsumeString(10)
    value2 = fdp.ConsumeString(10)
    key3 = fdp.ConsumeString(10)
    value3 = fdp.ConsumeString(10)
    key4 = fdp.ConsumeString(10)
    value4 = fdp.ConsumeString(10)
    {param_name} = [{{key1: value1, key2: value2}}, {{key3: value3, key4: value4}}]

        """
        return code

    if data_type == "list[str]" or data_type == "list":
        return f"""
    {param_name} = [fdp.ConsumeString(10) for _ in range(5)]
    """

    if data_type == "dict[str, list[str]]":
        code = f"""
    key1 = fdp.ConsumeString(10)
    value1 = [fdp.ConsumeString(10) for _ in range(5)]
    key2 = fdp.ConsumeString(10)
    value2 = [fdp.ConsumeString(10) for _ in range(5)]
    {param_name} = {{key1: value1, key2: value2}}

        """
        return code
    if data_type == "list[int]":
        return f"""
    {param_name} = [fdp.ConsumeIntInRange(1, 100) for _ in range(5)]
    """

    if data_type == "float":
        return f"""
    {param_name} = fdp.ConsumeFloat()
    """

    if data_type == "list[float]":
        return f"""
    {param_name} = [fdp.ConsumeFloat() for _ in range(5)]
    """

    if data_type == "dict[str, int]":
        code = f"""
    key1 = fdp.ConsumeString(10)
    value1 = fdp.ConsumeIntInRange(1, 100)
    key2 = fdp.ConsumeString(10)
    value2 = fdp.ConsumeIntInRange(1, 100)
    {param_name} = {{key1: value1, key2: value2}}
        """
        return code

    if data_type == "dict[str, float]":
        code = f"""
    key1 = fdp.ConsumeString(10)
    value1 = fdp.ConsumeFloat()
    key2 = fdp.ConsumeString(10)
    value2 = fdp.ConsumeFloat()
    {param_name} = {{key1: value1, key2: value2}}
        """
        return code

    elif data_type == "list[dict[str, str]]":
        code = f"""
    key1 = fdp.ConsumeString(10)
    value1 = fdp.ConsumeString(10)
    key2 = fdp.ConsumeString(10)
    value2 = fdp.ConsumeString(10)
    key3 = fdp.ConsumeString(10)
    value3 = fdp.ConsumeString(10)
    key4 = fdp.ConsumeString(10)
    value4 = fdp.ConsumeString(10)
    {param_name} = [{{key1: value1, key2: value2}}, {{key3: value3, key4: value4}}]
        """

        return code

    if data_type == "bool":
        return f"""
    {param_name} = fdp.ConsumeBool()
        """

    raise ValueError(f"Unsupported data type: {data_type}")

def construct_test_driver(pre_pr_version: str, post_pr_version: str, function_name: str) -> str:
    pre_pr_version_info = extract_function_info(pre_pr_version)
    post_pr_version_info = extract_function_info(post_pr_version)
    pre_target_params = None
    for func_info in pre_pr_version_info:
        if func_info.name == "pre_" + function_name:
            pre_target_params = get_parameter_types(func_info)
            break

    post_target_params = None
    for func_info in post_pr_version_info:
        if func_info.name == "post_" + function_name:
            post_target_params = get_parameter_types(func_info)
            break

    assert pre_target_params is not None, f"Function pre_{function_name} not found in pre PR version"
    assert post_target_params is not None, f"Function post_{function_name} not found in post PR version"

    merged_params = {**pre_target_params, **post_target_params}
    print(merged_params)
    template = """
#!/usr/bin/python3

import atheris
import sys

{pre_pr_version}

{post_pr_version}

{comparision_function}

def TestOneInput(atheris_bytes_data):
    fdp = atheris.FuzzedDataProvider(atheris_bytes_data)
    {test_setup}

atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()
"""

    pre_param_str = ", ".join(pre_target_params.keys())
    post_param_str = ", ".join(post_target_params.keys())
    comparision_function = "def comparision_function(\n"
    for param_name, param_type in merged_params.items():
        if param_type:
            comparision_function += f"    {param_name}: {param_type},\n"
        else:
            comparision_function += f"    {param_name},\n"

    comparision_function += "):\n"

    comparision_function += f"    pass \n"

    test_setup = "\n"
    for param_name in merged_params.keys():
        data_type = merged_params[param_name]
        assert data_type is not None, f"Parameter {param_name} has no type information"
        test_setup += get_data_provider_code(param_name, data_type)
    test_setup += "\n    comparision_function(\n"
    for param_name in merged_params.keys():
        test_setup += f"        {param_name},\n"
    test_setup += "    )\n"



    test_driver_code = template.format(
        pre_pr_version=pre_pr_version,
        post_pr_version=post_pr_version,
        comparision_function=comparision_function,
        test_setup=test_setup
    )

    return test_driver_code.strip()

class CallLocationExtractor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self):
        self.call_site_locations = []

    def visit_Call(self, node: cst.Call) -> bool | None:
        if isinstance(node.func, cst.Attribute):
            self.call_site_locations.append(
                self.get_metadata(cst.metadata.PositionProvider, node.func.attr))
        elif isinstance(node.func, cst.Name):
            if node.func.value not in builtin_functions:
                self.call_site_locations.append(
                    self.get_metadata(cst.metadata.PositionProvider, node.func))
        else:
            print(
                f"Warning: Unknown callee type {type(node.func)} -- ignoring this call")

def get_locations_of_calls(code):
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return []
    wrapper = cst.metadata.MetadataWrapper(tree)
    call_location_extractor = CallLocationExtractor()
    wrapper.visit(call_location_extractor)
    return call_location_extractor.call_site_locations

def get_ast_without_docstrings(code):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        # Remove docstrings
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            node.body = [n for n in node.body if not (
                isinstance(n, ast.Expr) and isinstance(n.value, ast.Str))]
    return tree

def equal_modulo_docstrings(code1, code2):
    try:
        ast1 = get_ast_without_docstrings(code1)
        ast2 = get_ast_without_docstrings(code2)
    except SyntaxError:
        # cannot parse code (e.g., .pyx files) -- just compare the strings
        return code1 == code2
    return ast.dump(ast1) == ast.dump(ast2)

def get_name_of_defined_function(code: str) -> str:
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = cst.metadata.MetadataWrapper(tree)
    extractor = FunctionExtractor()
    wrapper.visit(extractor)

    function_nodes = [node for node, _, _ in extractor.nodes_and_lines]

    if len(function_nodes) != 1:
        print(
            f"Warning: {len(function_nodes)} functions found, using the first one")

    return function_nodes[0].name.value

def get_locations_of_calls_by_range(code, start_line, end_line):
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return []
    wrapper = cst.metadata.MetadataWrapper(tree)
    call_location_extractor = CallLocationExtractor()
    wrapper.visit(call_location_extractor)

    # Filter calls by the specified range
    filtered_calls = [
        loc for loc in call_location_extractor.call_site_locations
        if start_line <= loc.start.line <= end_line
    ]

    return filtered_calls

def extract_imported_modules(code):
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        raise ValueError("Cannot parse code to extract imports. Please check the syntax.")

    wrapper = cst.metadata.MetadataWrapper(tree)
    import_extractor = ImportExtractor()
    wrapper.visit(import_extractor)
    imported_modules = {}
    for import_node in import_extractor.imports:
        if isinstance(import_node, cst.ImportFrom):
            def get_full_module_name(module_node):
                if module_node is None:
                    return ""
                # Handle relative imports (e.g., from .a.b import x)
                if isinstance(module_node, cst.Name):
                    return module_node.value
                elif isinstance(module_node, cst.Attribute):
                    return get_full_module_name(module_node.value) + "." + module_node.attr.value
                elif isinstance(module_node, cst.Dot):
                    # Should not occur directly, handled by ImportFrom.relative
                    return ""
                else:
                    return ""
            module_name = get_full_module_name(import_node.module) if import_node.module else ""
            # Handle relative import dots
            if import_node.relative:
                module_name = "." * len(import_node.relative) + (module_name if module_name else "")
            if module_name not in imported_modules:
                imported_modules[module_name] = []
            if isinstance(import_node.names, cst._nodes.op.ImportStar):
                # Handle star imports, e.g., from module import *
                imported_modules[module_name].append(("*", None))
            else:
                for alias in import_node.names:
                    if isinstance(alias, cst.ImportAlias):
                        imported_name = alias.name.value
                        asname = alias.asname.name.value if alias.asname else None
                        imported_modules[module_name].append((imported_name, asname))
        elif isinstance(import_node, cst.Import):
            for alias in import_node.names:
                if isinstance(alias, cst.ImportAlias):
                    # Handle dotted module names, e.g., scipy._lib.array_api_compat.array_api_compat.numpy
                    module_name = ""
                    name_node = alias.name
                    while isinstance(name_node, cst.Attribute):
                        module_name = name_node.attr.value + (("." + module_name) if module_name else "")
                        name_node = name_node.value
                    if isinstance(name_node, cst.Name):
                        module_name = name_node.value + (("." + module_name) if module_name else "")
                    asname = alias.asname.name.value if alias.asname else None
                    if module_name not in imported_modules:
                        imported_modules[module_name] = []
                    imported_modules[module_name].append((None, asname))  # No specific imported name, just alias

    return imported_modules

def get_top_level_function_and_class(code):
    """
    Returns a list of tuples: (type, name, start_line, end_line, code) for top-level functions and classes.
    type is either "function" or "class".
    """
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return []

    wrapper = cst.metadata.MetadataWrapper(tree)
    results = []

    class TopLevelExtractor(cst.CSTVisitor):
        METADATA_DEPENDENCIES = (cst.metadata.PositionProvider, cst.metadata.ParentNodeProvider, )

        def __init__(self):
            self.items = []

        def visit_FunctionDef(self, node: cst.FunctionDef):
            # Only top-level functions (not inside classes)
            if isinstance(self.get_metadata(cst.metadata.ParentNodeProvider, node), cst.Module):
                pos = self.get_metadata(cst.metadata.PositionProvider, node)
                code_str = cst.Module(body=[node]).code
                self.items.append(("function", node.name.value, pos.start.line, pos.end.line, code_str))

        def visit_ClassDef(self, node: cst.ClassDef):
            # Only top-level classes
            if isinstance(self.get_metadata(cst.metadata.ParentNodeProvider, node), cst.Module):
                pos = self.get_metadata(cst.metadata.PositionProvider, node)
                code_str = cst.Module(body=[node]).code
                self.items.append(("class", node.name.value, pos.start.line, pos.end.line, code_str))

    # Register ParentNodeProvider for top-level detection
    wrapper = cst.metadata.MetadataWrapper(tree, unsafe_skip_copy=True)
    extractor = TopLevelExtractor()
    wrapper.visit(extractor)
    return extractor.items

def get_class_name(code):
    """
    Extract the name of the first class defined in the given code.
    Returns None if no class is found.
    """
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    for node in tree.body:
        if isinstance(node, cst.ClassDef):
            return node.name.value
    return None

def get_top_level_function_and_class_names(code):
    items = get_top_level_function_and_class(code)
    return [name for _, name, _, _, _ in items]

def convert_import_dict_to_string(imported_modules):
    result = []
    for module, imports in imported_modules.items():
        assert imports, f"Module {module} has no imports"
        for imported_name, asname in imports:
            import_str = ""
            if imported_name is not None:
                import_str += f"from {module} import {imported_name}"
            else:
                import_str += f"import {module}"
            if asname is not None:
                import_str += f" as {asname}"
            result.append(import_str)
    return "\n".join(result)

def extract_target_function_by_range(code, patch_range):
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = cst.metadata.MetadataWrapper(tree)
    extractor = FunctionExtractor()
    wrapper.visit(extractor)

    function_code = None
    function_start_line = None
    function_end_line = None
    for node, start_line, end_line in extractor.nodes_and_lines:
        target_line = int((patch_range[0] + patch_range[1]) / 2) - 1
        if start_line < target_line and target_line < end_line:
            if function_code is not None:
                return None, None, None  # Multiple functions found in the patch range
            module_with_node = cst.Module(body=[node])
            function_code = module_with_node.code
            function_start_line = start_line
            function_end_line = end_line
            break

    return function_code, function_start_line, function_end_line

def update_function_name(code: str, target_name: str, new_name: str) -> str:
    """
    Update the name of the first function in the provided code and all recursive calls to it.

    Args:
        code: Python source code as a string
        target_name: Name of the function to update
        new_name: New name for the function
    Returns:
        Updated code with the function name and its recursive calls changed
    """

    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        raise ValueError("Cannot parse code to update function name. Please check the syntax.")

    class FunctionNameTransformer(cst.CSTTransformer):
        def __init__(self, target_name: str, new_name: str):
            self.target_name = target_name
            self.new_name = new_name
            self.updated = False

        def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
            if self.target_name == original_node.name.value:
                self.updated = True
                return updated_node.with_changes(name=cst.Name(value=self.new_name))
            return updated_node

        def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
            # Only update direct calls to the function (not attribute or method calls)
            if isinstance(updated_node.func, cst.Name) and updated_node.func.value == self.target_name:
                return updated_node.with_changes(func=cst.Name(value=self.new_name))
            return updated_node

    transformer = FunctionNameTransformer(target_name, new_name)
    new_tree = tree.visit(transformer)

    if not transformer.updated:
        raise ValueError("No function found in the provided code")

    return new_tree.code

def get_docstring_of_function(code: str) -> Optional[str]:
    """
    Extract the docstring of the first function defined in the provided code.

    Args:
        code: Python source code as a string
    Returns:
        The docstring of the function, or None if no docstring is found
    """

    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        raise ValueError("Cannot parse code to extract docstring. Please check the syntax.")

    wrapper = cst.metadata.MetadataWrapper(tree)
    extractor = FunctionExtractor()
    wrapper.visit(extractor)

    if not extractor.functions:
        return None

    return extractor.functions[0].docstring

def get_code_without_docstring(code: str) -> str:
    """
    Remove the docstring from the first function defined in the provided code.

    Args:
        code: Python source code as a string
    Returns:
        The code without the function's docstring
    """

    ast_without_docstrings = get_ast_without_docstrings(code)

    # Convert back to code
    new_tree = cst.parse_module(ast.unparse(ast_without_docstrings))

    return new_tree.code

def get_modified_code_block(pre_code: str, post_code: str) -> list[str]:
    """
    Extract modified code blocks between two code versions.
    Args:
        pre_code: Pre-PR version of the code
        post_code: Post-PR version of the code
    Returns:
        List of modified code blocks as strings
    """

    # Using CST to parse both versions
    try:
        pre_tree = cst.parse_module(pre_code)
        post_tree = cst.parse_module(post_code)
    except cst.ParserSyntaxError:
        raise ValueError("Cannot parse code to extract modified code blocks. Please check the syntax.")

    # visit all nodes in tree and match them
    modified_code_blocks = []

def insert_print_statement(code, print_line: str) -> str:
    """
    Insert a print line at the start of the specified function, but after any docstring.

    Args:
        code: source code of a function as string
        print_line: line to insert (e.g., 'print("Debug info")')

    Returns:
        Updated code with the print line inserted
    """
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        raise ValueError("Cannot parse code to insert print line. Please check the syntax.")

    class PrintLineInserter(cst.CSTTransformer):
        def __init__(self, print_line: str):
            self.print_line = print_line

        def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
            print_stmt = cst.parse_statement(self.print_line)
            # Make a mutable copy of the body statements
            body_stmts = list(updated_node.body.body)

            insert_index = 0
            # If the first statement is a docstring, insert after it
            if body_stmts:
                first_stmt = body_stmts[0]
                if isinstance(first_stmt, cst.SimpleStatementLine):
                    inner = first_stmt.body[0] if first_stmt.body else None
                    if isinstance(inner, cst.Expr) and isinstance(inner.value, cst.SimpleString):
                        insert_index = 1

            new_body_stmts = body_stmts[:insert_index] + [print_stmt] + body_stmts[insert_index:]
            new_body = updated_node.body.with_changes(body=new_body_stmts)
            return updated_node.with_changes(body=new_body)

    inserter = PrintLineInserter(print_line)
    new_tree = tree.visit(inserter)

    return new_tree.code

if __name__ == "__main__":
    # Example usage of get_docstring_of_function
    pre_code = '''
def example_function(param1: int, param2: str) -> bool:
    param = param1 + param2
    if param > 10:
        return True
    else:
        return False
'''
    post_code = '''
def example_function(param1: int, param2: str) -> bool:
    """This is the docstring of the function."""
    param = param1 + param2
    if param >= 10:
        return False
    else:
        return False
'''

    new_code = insert_print_statement(post_code, "print('Function called', end=' ')")
    print(new_code)

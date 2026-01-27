from mutmut.file_mutation import create_mutations, deep_replace
import libcst

def generate_mutants(code: str):
    _, mutations = create_mutations(code)
    code_mutations = []
    for mutant in mutations:
        mutated_node = deep_replace(mutant.contained_by_top_level_function, mutant.original_node, mutant.mutated_node)
        mutated_code = libcst.Module([]).code_for_node(mutated_node)
        code_mutations.append(mutated_code.strip())
    return code_mutations

def beautify_code(code: str):
    module = libcst.parse_module(code)
    return module.code.strip()

if __name__ == "__main__":
    code = '''
def post_reconstruct_object(typ, obj, axes, dtype, name):
    """
    Reconstruct an object given its type, raw value, and possibly empty
    (None) axes.

    Parameters
    ----------
    typ : object
        A type
    obj : object
        The value to use in the type constructor
    axes : dict
        The axes to use to construct the resulting pandas object

    Returns
    -------
    ret : typ
        An object of type ``typ`` with the value `obj` and possible axes
        `axes`.
    """
    try:
        typ = typ.type
    except AttributeError:
        pass

    res_t = np.result_type(obj.dtype, dtype)

    if not isinstance(typ, partial) and issubclass(typ, PandasObject):
        if name is None:
            return typ(obj, dtype=res_t, **axes)
        return typ(obj, dtype=res_t, name=name, **axes)

    # special case for pathological things like ~True/~False
    if hasattr(res_t, "type") and typ == np.bool_ and res_t != np.bool_:
        ret_value = res_t.type(obj)
    else:
        ret_value = res_t.type(obj)
        # The condition is to distinguish 0-dim array (returned in case of
        # scalar) and 1 element array
        # e.g. np.array(0) and np.array([0])
        if (
            len(obj.shape) == 1
            and len(obj) == 1
            and not isinstance(ret_value, np.ndarray)
        ):
            ret_value = np.array([ret_value]).astype(res_t)

    return ret_value
'''
    mutants = generate_mutants(code)
    for i, mutant in enumerate(mutants):
        print("-" * 20)
        print(mutant)

from functools import wraps


def reverse_key_value_in_dict(in_dict: dict) -> dict:
    """
    reverse the key and value in dict object
    {(k:v)} -> {(v:k)}
    :param in_dict: input dict
    :return: output dict
    """

    return {v: k for k, v in in_dict.items()}


def convert_ndarray_to_list(obj):
    import numpy as np
    if isinstance(obj, np.ndarray):
        return convert_ndarray_to_list(obj.tolist())
    elif isinstance(obj, list):
        return [convert_ndarray_to_list(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_ndarray_to_list(item) for item in obj)
    elif isinstance(obj, dict):
        return {convert_ndarray_to_list(key): convert_ndarray_to_list(value) for key, value in obj.items()}
    else:
        return obj


def singleton(cls):
    """Set class to singleton class.

    :param cls: class
    :return: instance
    """
    __instances__ = {}

    @wraps(cls)
    def get_instance(*args, **kw):
        """Get class instance and save it into glob list."""
        if cls not in __instances__:
            __instances__[cls] = cls(*args, **kw)
        return __instances__[cls]

    return get_instance


@singleton
class Counter:

    def __init__(self):
        self.counts = {}

    def get_count(self, name='default'):
        if name in self.counts:
            self.counts[name] += 1
        else:
            self.counts[name] = 1
        return self.counts[name]

    def reset_count(self, name='default'):
        if name in self.counts:
            del self.counts[name]

    def reset_all_counts(self):
        self.counts = {}

    def get_all_counts(self):
        return self.counts

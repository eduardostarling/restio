from typing import List, Dict, Any
from functools import wraps
import inspect


class BaseQuery:
    __args: List = []
    __kwargs: Dict[str, Any] = {}

    def __init__(self, function=None, *args, **kwargs):
        self.__function = function
        self.__args = args or []
        self.__kwargs = kwargs or {}

    def __hash__(self):
        hash_list = [self.__function]

        signature = inspect.signature(self.__function)
        parameters = signature.bind(*self.__args, **self.__kwargs)
        hash_list.extend(parameters.arguments.items())

        return hash(tuple(hash_list))

    def __eq__(self, other):
        if other and isinstance(other, BaseQuery):
            return self.__hash__() == other.__hash__()

        return False

    def __call__(self):
        return self.__function(*self.__args, **self.__kwargs)


def Query(function=None):
    args_set = set(inspect.signature(function).parameters.keys())

    if not args_set:
        return BaseQuery(function=function)
    else:
        @wraps(function)
        def wrapper(*args, **kwargs):
            return BaseQuery(function, *args, **kwargs)

        return wrapper

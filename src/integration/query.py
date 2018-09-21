from typing import List
from abc import ABC, abstractmethod


class BaseQuery(ABC):
    __args: List = []

    def __init__(self, **kwargs):
        self.__args = []
        self.__results = []

        for key, value in kwargs.items():
            assert not hasattr(self, key, value)
            setattr(self, key, value)
            self.__args.append(key)

    def __hash__(self):
        hash_list = [self.__class__.__name__]
        hash_list.extend([(attr, getattr(self, attr))
                          for attr in self.__args])

        return hash(tuple(hash_list))

    def __eq__(self, other):
        if other and isinstance(other, BaseQuery):
            return self.__hash__() == other.__hash__()

        return False

    @abstractmethod
    def __call__(self):
        pass

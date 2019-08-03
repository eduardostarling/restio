from functools import wraps
from typing import Optional, Tuple, Type

from .model import BaseModel, ValueKey


def not_implemented_method(function):
    @wraps(function)
    def wrapper(self, obj):
        raise RuntimeError(f'Method {function.__name__} not implemented.')

    return wrapper


class BaseDAO:
    _model_type: Type[BaseModel]

    def __init__(self, model_type: Optional[Type[BaseModel]] = None) -> None:
        if model_type:
            self._model_type = model_type

    @not_implemented_method
    async def get(self, obj: Tuple[ValueKey]):
        pass

    @not_implemented_method
    async def add(self, obj: BaseModel):
        pass

    @not_implemented_method
    async def remove(self, obj: BaseModel):
        pass

    @not_implemented_method
    async def update(self, obj: BaseModel):
        pass

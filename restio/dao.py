from functools import wraps
from typing import Optional, Tuple, Type

from .model import BaseModel, ValueKey


def not_implemented_method(function):
    @wraps(function)
    def wrapper(self, obj):
        raise RuntimeError(f'Method {function.__name__} not implemented.')

    return wrapper


class BaseDAO:
    """
    Base abstract class for Data Access Objects (DAO).

    The subclasses of BaseDAO in the `restio` framework represent the
    data access layer to a particular model in a remote REST API.
    Transactions use the DAOs to perform CRUD operations on the remote
    server using the methods `get`, `add`, `update` and `remove`.

    Each DAO instance should be registered in a Transaction instance
    and associated to a model type through its constructor. The model
    type is stored internally and used by the Transaction to identify
    the DAO that is responsible for a particular model.

    Differently from a regular abstract class, the methods of its
    subclasses don't need to be overriden unless the Transaction needs
    to make use of them. In that case, not implementing the method will
    cause the transaction to fail in runtime during commit for
    not-implemented `add`, `remove` or `update`. Methods that fail
    during a transaction commit might raise an Exception, which will be
    picked up by the transaction and casted to an TransactionException.
    Models can be modified in the methods of the DAO, and the values
    will be persisted to the model's cache accordingly if the operation
    is successful (no exception thrown).

    It is recommended that each `get`, `add`, `remove` and `update`
    method is overriden in the subclass if the operation is permitted
    by the REST API. This avoids issues with commiting transactions that
    should be legal.
    """

    _model_type: Type[BaseModel]

    def __init__(self, model_type: Optional[Type[BaseModel]] = None) -> None:
        if model_type:
            self._model_type = model_type

    @not_implemented_method
    async def get(self, obj: Tuple[ValueKey]) -> BaseModel:
        """
        Retrieves a model from the remote server.

        :param obj: The ValueKey instance of the model to be retrieved.
        :return: The model retrieved from the remote server.
        """
        pass

    @not_implemented_method
    async def add(self, obj: BaseModel):
        """
        Creates a model in the remote server.

        :param obj: The model instance to be created.
        """
        pass

    @not_implemented_method
    async def remove(self, obj: BaseModel):
        """
        Removes a model from the remote server.

        :param obj: The model instance to be removed.
        """
        pass

    @not_implemented_method
    async def update(self, obj: BaseModel):
        """
        Updates a model in the remote server.

        :param obj: The model to be updated.
        """
        pass

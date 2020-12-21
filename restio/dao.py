from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import TYPE_CHECKING, Awaitable, Callable, Generic, Optional, Type, TypeVar

from restio.graph import Node
from restio.model import BaseModel

NOT_IMPLEMENTED_DAO_FUNC_ATTR = "dao_method_not_implemented"

if TYPE_CHECKING:
    from restio.session import Session


FunctionType = Callable[..., Awaitable]


def not_implemented_method(function: FunctionType) -> FunctionType:
    @wraps(function)
    def wrapper(self, obj):
        raise NotImplementedError(f"Method {function.__name__} not implemented.")

    setattr(wrapper, NOT_IMPLEMENTED_DAO_FUNC_ATTR, True)
    return wrapper


def check_dao_implemented_method(function: FunctionType):
    if hasattr(function, NOT_IMPLEMENTED_DAO_FUNC_ATTR) and getattr(
        function, NOT_IMPLEMENTED_DAO_FUNC_ATTR
    ):
        raise NotImplementedError(
            f"Function `{function.__name__}` of DAO"
            f" {function.__self__.__class__.__name__} not implemented."
        )


Model_co = TypeVar("Model_co", bound=BaseModel, covariant=True)


class BaseDAO(Generic[Model_co]):
    """
    Base abstract class for Data Access Objects (DAO).

    The subclasses of BaseDAO in the restio framework represent the core of the data
    access layer to a particular model in a remote REST API. Sessions use the DAOs
    to perform CRUD operations on the remote server using the async methods `get`,
    `add`, `update` and `remove`.

    Each DAO instance should be registered to a Session instance and associated to a
    model type through its constructor. The model type is stored internally and used by
    the Session to identify the DAO that is responsible for a particular model. When
    bound to a Session instance, the DAO instance receives a reference to the Session,
    which is always available internally.

    Differently from a regular abstract class, the methods of BaseDAO subclasses don't
    need to be overwritten unless the Session needs to make use of them. In that case,
    not implementing the method will cause the Session to fail in runtime for
    not-implemented `add`, `remove` or `update`. Methods that fail during a Session
    commit might raise an Exception, which will be picked up by the Session. Models can
    be modified in the methods of the DAO, and the values will be persisted to the
    model's cache accordingly if the operation is successful (no exception thrown).

    It is recommended that each `get`, `add`, `remove` and `update` method is
    overwritten in the subclass if the operation is permitted by the REST API.
    """

    _model_type: Type[Model_co]
    _session: Optional["Session"]

    def __init__(self, model_type: Optional[Type[Model_co]] = None) -> None:
        if model_type:
            self._model_type = model_type

    @property
    def session(self) -> "Session":
        """
        Returns the Session instance to which the DAO instance is bound.

        :raises RuntimeError: When the DAO instance is not bound to any Session
                              instance.
        :return: The Session instance.
        """
        if not self._session:
            raise RuntimeError("This instance of DAO is not bound to any Session.")
        return self._session

    @session.setter
    def session(self, session: "Session"):
        self._session = session

    @not_implemented_method
    async def get(self, **keys) -> Model_co:  # type: ignore
        """
        Retrieves a model from the remote server.

        # noqa: DAR202 return

        :param keys: The keyword arguments representing the primary keys of the model
                     to be retrieved.
        :return: The model retrieved from the remote server.
        """
        pass

    @not_implemented_method
    async def add(self, obj: Model_co):
        """
        Creates a model in the remote server.

        :param obj: The model instance to be created.
        """
        pass

    @not_implemented_method
    async def remove(self, obj: Model_co):
        """
        Removes a model from the remote server.

        :param obj: The model instance to be removed.
        """
        pass

    @not_implemented_method
    async def update(self, obj: Model_co):
        """
        Updates a model in the remote server.

        :param obj: The model to be updated.
        """
        pass


DAOTaskCallable = Callable[[Model_co], Awaitable[None]]


class DAOTask(Generic[Model_co]):
    """
    Wrapper object that, when awaited, contains a asyncio.Task ran by a a DAO method
    during a Session commit.

    When a DAOTask instance is awaited for the first time, it triggers `run_task()`
    and returns the result from the undelying task wrapping `func`. Awaiting the same
    instance multiple times will not retrigger the task, but instead will return the
    value from the first call. Alternatively, it is also possible to retrieve the
    underlying task directly through the attribute `task`.

    Running a DAOTask will also record the `start_time` and `end_time` of the first
    execution.
    """

    _task: Optional[asyncio.Task[Optional[Model_co]]]
    node: Node[Model_co]
    func: DAOTaskCallable
    start_time: float
    end_time: float

    def __init__(self, node: Node[Model_co], func: DAOTaskCallable):
        self.node = node
        self.func = func
        self.start_time = 0.0
        self.end_time = 0.0
        self._task = None

    def run_task(self) -> asyncio.Task[Optional[Model_co]]:
        """
        Creates and returns an asyncio.Task that runs `func` when called for the first
        time.

        When called multiple times, returns the existing asyncio.Task created during
        the first execution.

        :return: The asyncio.Task instance.
        """
        if self._task:
            return self._task

        self.start_time = time.time()

        task: asyncio.Task = asyncio.create_task(self.func(self.node.node_object))
        task.add_done_callback(self._task_finished)

        self._task = task
        return task

    def __await__(self):
        return (yield from self.run_task().__await__())

    @property
    def task(self) -> asyncio.Task[Optional[Model_co]]:
        """
        Contains the underlying asyncio.Task.

        :raises RuntimeError: When a Task has not yet been triggered.
        :return: The asyncio.Task instance.
        """
        if not self._task:
            raise RuntimeError("DAOTask not started.")
        return self._task

    def _task_finished(self, future):
        self.end_time = time.time()
        self.task.remove_done_callback(self._task_finished)

    @property
    def duration(self) -> float:
        """
        Returns the duration of the execution (in seconds).

        :raises RuntimeError: When the execution has not been finished.
        :return: The duration (in seconds).
        """
        if not self.start_time or not self.end_time:
            raise RuntimeError("Task not finished.")
        return self.end_time - self.start_time

    @property
    def model(self) -> Model_co:
        """
        Returns the BaseModel contained by the `node`.

        :return: The BaseModel instance.
        """
        return self.node.node_object

    def __lt__(self, value: DAOTask):
        return self.end_time < value.end_time

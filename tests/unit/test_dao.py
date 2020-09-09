import asyncio

import pytest

from restio.dao import BaseDAO, DAOTask, check_dao_implemented_method
from restio.graph import Node
from restio.model import BaseModel


class DAOEmptyMock(BaseDAO):
    pass


class ModelMock(BaseModel):
    pass


class DAOMissingAddRemoveUpdateMock(BaseDAO):
    async def get(self, keys) -> None:
        pass


class DAOMock(BaseDAO):
    async def get(self, **keys) -> None:
        pass

    async def add(self, obj: BaseModel):
        await asyncio.sleep(0.1)

    async def update(self, obj: BaseModel):
        await asyncio.sleep(0.2)

    async def remove(self, obj: BaseModel):
        await asyncio.sleep(0.3)

    async def error(self, obj: BaseModel):
        raise RuntimeError("error")


class TestDAO:
    @pytest.fixture
    def empty_dao(self):
        return DAOEmptyMock(ModelMock)

    @pytest.fixture
    def missing_funcs_dao(self):
        return DAOMissingAddRemoveUpdateMock(ModelMock)

    def test_check_empty_dao(self, empty_dao):
        funcs = [empty_dao.get, empty_dao.add, empty_dao.remove, empty_dao.update]

        for func in funcs:
            with pytest.raises(NotImplementedError, match="not implemented"):
                func("any")

    def test_check_empty_methods(self, empty_dao):
        funcs = [empty_dao.get, empty_dao.add, empty_dao.remove, empty_dao.update]

        for func in funcs:
            with pytest.raises(NotImplementedError, match="not implemented"):
                check_dao_implemented_method(func)

    def test_check_missing_methods(self, missing_funcs_dao):
        funcs = [
            missing_funcs_dao.add,
            missing_funcs_dao.remove,
            missing_funcs_dao.update,
        ]

        for func in funcs:
            with pytest.raises(
                NotImplementedError,
                match="DAOMissingAddRemoveUpdateMock not implemented",
            ):
                check_dao_implemented_method(func)

        check_dao_implemented_method(missing_funcs_dao.get)


class TestDAOTask:
    @pytest.fixture
    def model(self) -> ModelMock:
        return ModelMock()

    @pytest.fixture
    def node(self, model) -> Node:
        return Node(model)

    @pytest.fixture
    def dao(self, model) -> DAOMock:
        return DAOMock(type(model))

    @pytest.fixture
    def task_add(self, model: BaseModel, node: Node, dao: DAOMock):
        return DAOTask(node, dao.add)

    @pytest.fixture
    def task_update(self, model: BaseModel, node: Node, dao: DAOMock):
        return DAOTask(node, dao.update)

    @pytest.fixture
    def task_remove(self, model: BaseModel, node: Node, dao: DAOMock):
        return DAOTask(node, dao.remove)

    @pytest.fixture
    def task_error(self, model: BaseModel, node: Node, dao: DAOMock):
        return DAOTask(node, dao.error)  # type: ignore

    def test_instantiate(self, task_add: DAOTask, node: Node, dao: DAOMock):
        assert task_add.node == node
        assert task_add.func == dao.add  # type: ignore
        assert task_add.start_time == 0.0
        assert task_add.end_time == 0.0
        assert task_add._task is None

    @pytest.mark.asyncio
    async def test_await(self, task_add: DAOTask, model: BaseModel):
        await task_add.run_task()
        await task_add.task

    @pytest.mark.asyncio
    async def test_await_error(self, task_error: DAOTask):
        with pytest.raises(RuntimeError, match="error"):
            assert await task_error.run_task()

        with pytest.raises(RuntimeError, match="error"):
            assert await task_error.task

        with pytest.raises(RuntimeError, match="error"):
            assert await task_error

    @pytest.mark.asyncio
    async def test_run_task(self, task_add: DAOTask):
        task = task_add.run_task()
        await task

        assert task is not None
        assert task_add._task == task
        assert task_add.task == task
        assert task_add.duration > 0.0

    @pytest.mark.asyncio
    async def test_duration(self, task_add: DAOTask):
        await task_add
        assert task_add.start_time > 0.0
        assert task_add.end_time > 0.0
        assert task_add.duration > 0.0

    @pytest.mark.asyncio
    async def test_duration_not_started(self, task_add: DAOTask):
        with pytest.raises(RuntimeError, match="not finished"):
            task_add.duration

    def test_model(self, task_add: DAOTask, model: ModelMock):
        assert task_add.model == model

    @pytest.mark.asyncio
    async def test_order(
        self, task_add: DAOTask, task_update: DAOTask, task_remove: DAOTask
    ):
        tasks = [task_remove, task_update, task_add]
        await asyncio.wait(tasks)

        sorted_results = sorted(tasks)
        assert sorted_results == [task_add, task_update, task_remove]

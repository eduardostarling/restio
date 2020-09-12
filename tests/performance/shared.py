import asyncio
import contextlib
import threading
from pathlib import Path
from typing import List

import pytest
from flask.testing import FlaskClient
from pycallgraph import Config as PyCallGraphConfig
from pycallgraph import PyCallGraph
from pycallgraph.globbing_filter import GlobbingFilter
from pycallgraph.output import GraphvizOutput, Output

from tests.integration.employee.client.api import CallableMethod, ClientAPI

# The Sync2Async class and benchmark_profile fixture have been adapted from
# Marcelo Bello's (mbello) answer in
# https://github.com/ionelmc/pytest-benchmark/issues/66#issuecomment-575853801


class Sync2Async:
    def __init__(self, coro, *args, **kwargs):
        self.coro = coro
        self.args = args
        self.kwargs = kwargs
        self.custom_loop = None
        self.thread = None

    def start_background_loop(self) -> None:
        asyncio.set_event_loop(self.custom_loop)
        self.custom_loop.run_forever()

    def __call__(self):
        evloop = None
        awaitable = self.coro(*self.args, **self.kwargs)
        try:
            evloop = asyncio.get_running_loop()
        except:
            pass
        if evloop is None:
            return asyncio.run(awaitable)
        else:
            if not self.custom_loop or not self.thread or not self.thread.is_alive():
                self.custom_loop = asyncio.new_event_loop()
                self.thread = threading.Thread(
                    target=self.start_background_loop, daemon=True
                )
                self.thread.start()

            return asyncio.run_coroutine_threadsafe(
                awaitable, self.custom_loop
            ).result()


class ClientAPIWithoutDelay(ClientAPI):
    def _async(self, method: CallableMethod, *args, **kwargs) -> CallableMethod:
        return super()._async(method, *args, delay=False, **kwargs)


class Profiler:
    PROFILES_FOLDER = ".profiles"

    @classmethod
    @contextlib.contextmanager
    def run(cls, file_name: str, activate: bool = True):
        if not activate:
            yield
            return

        profiles_folder_path = Path(cls.PROFILES_FOLDER)
        if not profiles_folder_path.is_dir():
            profiles_folder_path.mkdir(exist_ok=True)

        include = ["restio.*", "uuid.*", "tests.*"]

        config = PyCallGraphConfig(threaded=False)
        config.trace_filter = GlobbingFilter(include=include)
        output = cls.output_factory(file_name, ["svg", "png"])

        with PyCallGraph(output=output, config=config):
            yield

    @classmethod
    def output_factory(cls, file_name: str, output_types: List[str]) -> List[Output]:
        outputs = []
        for output_type in output_types:
            output_file = f"{cls.PROFILES_FOLDER}/{file_name}.{output_type}"
            outputs.append(
                GraphvizOutput(output_file=output_file, output_type=output_type)
            )
        return outputs


class PerformanceTest:
    """
    Sets up a test class to run performance tests. By default, all tests will be marked
    to run 12 times, in which the number of iterations grows exponentially (base 2).
    Benchmark tests will run all possible iterations in the range, while profile tests
    will only run a single time with a fixed number of iterations of 1024. These tests
    can also run normally without any performance measurement (for validation only), in
    which case the same rule used for profile tests applies.
    """

    DEFAULT_NUM_ITERATIONS = 12
    RUN_ITERATION_WHEN_NO_BENCHMARK = 1024

    @pytest.fixture(scope="function")
    def benchmark_profile(self, benchmark, profile, request):
        file_name = request.node.name

        def _wrapper(func, *args, **kwargs):
            async def profiled_func_async():
                with Profiler.run(activate=profile, file_name=file_name):
                    await func(*args, **kwargs)

            def profiled_func_sync():
                with Profiler.run(activate=profile, file_name=file_name):
                    func(*args, **kwargs)

            if asyncio.iscoroutinefunction(func):
                bench_func = Sync2Async(profiled_func_async)
            else:
                bench_func = profiled_func_sync

            benchmark(bench_func)

        return _wrapper

    _iterations = lambda n=DEFAULT_NUM_ITERATIONS: [
        str((2 ** x) * 1).zfill(4) for x in range(0, n)
    ]

    @pytest.fixture(scope="function", params=_iterations())
    def iterations(self, request, pytestconfig):
        iteration = int(request.param)
        disabled = pytestconfig.getoption("--benchmark-disable", False)

        if disabled and iteration != self.RUN_ITERATION_WHEN_NO_BENCHMARK:
            pytest.skip()  # type: ignore

        return iteration

    @pytest.fixture(scope="function")
    def api(self, client: FlaskClient) -> ClientAPI:
        return ClientAPIWithoutDelay(client)

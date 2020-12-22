import pytest

from restio.fields.base import MODEL_TYPE_REGISTRY


def pytest_addoption(parser):
    parser.addoption(
        "--profile",
        action="store_true",
        help="Enables profiling. This will disable benchmarks.",
    )


@pytest.fixture(scope="session")
def profile(request):
    return request.config.getoption("--profile")


# This applies to all tests in the framework, to guarantee that model names will not
# conflict with each other between tests, or when model classes are declared outside
# the scope of a test
@pytest.fixture(scope="function", autouse=True)
def reset_model_aliases():
    MODEL_TYPE_REGISTRY.clear()

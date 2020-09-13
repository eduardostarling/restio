import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--profile",
        action="store_true",
        help="Enables profiling. This will disable benchmarks.",
    )


@pytest.fixture(scope="session")
def profile(request):
    return request.config.getoption("--profile")

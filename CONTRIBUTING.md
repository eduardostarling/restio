# Contributing

Thank you very much for your interest in contributing to **restio**! We are happy to receive new feature requests or review any contribution to this repository via pull requests.

**restio** is a relatively new framework, and therefore we would love to get contribution in many areas. Currently, the ones we need most attention to are:

- Automated testing
- Documentation
- New functionality and bug fixes

If you have questions, feel free to contact us directly with a GitHub Issue or [email](mailto:edmstar@gmail.com).

## Requesting a change

If you find a security vulnerability, please [contact us via email](mailto:edmstar@gmail.com) and **do not make the information public**.

If you find a bug or would like to request a feature, please [create an issue](https://github.com/eduardostarling/restio/issues/new).

## Pull Requests

We are a very small team, so contributions via pull requests (PR) are very much appreciated. We will make our best effort to get your PR reviewed and approved as quickly as possible. Some rules to be observed:

- For security reasons, you will not be able to create a branch directly on our repository, so we kindly request you to create PRs incoming from forks.
- We recommend you start a discussion first as a GitHub Issue if the change is significant. You are free to skip this step, at the risk that the PR might be rejected.
- On the description of the PR, please provide as much detail as possible as to why the changes are being introduced. If this has already happened in a GitHub Issue, please tag the issue in the PR description.
- We require at least one approval from a **restio** developer. This number might increase in the future.
- All PRs will be [automatically checked on CI](https://dev.azure.com/edmstar/restio/_build?definitionId=1). Failing builds will automatically block PRs.

## Prepare the development environment

We currently use Python 3.8 for development, but all code should be compatible with Python 3.7 or older.

The environment setup can be fully done by [pipenv](https://pipenv-fork.readthedocs.io/en/latest/basics.html#example-pipenv-workflow):

```bash
pipenv install --dev
```

### Testing

You can run all tests with

```bash
pipenv run test
```

or by directly running Pytest from the root of the repository:

```bash
pytest
```

### Performance Testing

There are two types of performance analysis available in this project: benchmarking and profiling.

For profiling, it is necessary [to also have `graphviz` installed on the environment](http://www.graphviz.org/download/).

**Running Benchmark Tests**:

```bash
pipenv run benchmark-tests
```

or

```bash
pytest -c pytest-benchmark.ini
```

The commands above will run all iterations for all tests under `tests/performance`.

**Running Profile Tests**:

```bash
pipenv run profile-tests
```

or

```bash
pytest -c pytest-profile.ini
```

The commands above will only run iterations with 1024 elements for all tests under `tests/performance`.

### Building the documentation

```bash
pipenv run docs
```

## Developing

### Style guide and linters

For Python code, we follow [PEP8](https://www.python.org/dev/peps/pep-0008/) as much as possible and enforce the formatting with a few tools: Flake8, Black, isort and Darglint. The CI pipelines will automatically complain about code that doesn't comply with the formatting rules in PRs.

We also use type hinting extensively in this framework to enhance the experience of other developers using it. We don't check for typing issues in pipelines yet, but we encourage you use some tool for checking the types locally. We currently use [Pyright](https://github.com/microsoft/pyright) for that.

In code, all public functions and classes should contain well-described docstrings.

For reStructuredText documentation (.rst), we don't have any specific guideline in place. The CI pipelines will also automatically build the documentation and raise errors if something is wrong.

### Code

**restio** is based on `asyncio` for concurrency, and therefore the source code needs to follow the `async/await` convention whenever blocks of code might hang due to I/O activity.

### Tests

To keep the framework reliable and generic, we do extensive testing of most features. All PRs should contain new tests, and the code coverage should not fall under 96%.

Feel free to contribute by adding more tests to existing scenarios, or by refactoring/extending existing tests.

import os
from pathlib import Path

import pytest

CURRENT_DIRECTORY = Path(os.path.dirname(__file__))
COVERAGE_DIR = (CURRENT_DIRECTORY / '../restio/').resolve()

pytest.main([
    str(CURRENT_DIRECTORY),
    "--cov", str(COVERAGE_DIR),
    "-n", "auto",
    "--cov-report", "xml",
    "--cov-report", "html",
    "--junitxml=test-results.xml",
    "--cov-branch"
])

import os
from coverage import Coverage
import pytest

CURRENT_DIRECTORY = os.path.dirname(__file__)

cov = Coverage(source=[os.path.join(CURRENT_DIRECTORY, '../restio/')], data_suffix=False)
cov.exclude('\.\.\.')  # noqa
cov.exclude('pass')
cov.start()

pytest.main([CURRENT_DIRECTORY])

cov.stop()
cov.html_report(directory=os.path.join(CURRENT_DIRECTORY, 'htmlcov'))

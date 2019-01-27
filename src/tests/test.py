import os
from coverage import Coverage
from unittest import TestLoader, TextTestRunner

CURRENT_DIRECTORY = os.path.dirname(__file__)

cov = Coverage(source=[os.path.join(CURRENT_DIRECTORY, '../restio/')], data_suffix=False)
cov.exclude('\.\.\.')  # noqa
cov.exclude('pass')
cov.start()

tests = TestLoader().discover(os.path.join(CURRENT_DIRECTORY, 'unit'), top_level_dir=CURRENT_DIRECTORY)
TextTestRunner().run(tests)

cov.stop()
cov.html_report(directory=os.path.join(CURRENT_DIRECTORY, 'htmlcov'))

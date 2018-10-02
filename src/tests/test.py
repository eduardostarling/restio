import os
from coverage import Coverage
from unittest import TestLoader, TextTestRunner

cov = Coverage()
cov.start()

tests = TestLoader().discover(os.path.join(os.path.dirname(__file__), 'unit'))
TextTestRunner().run(tests)

cov.stop()
cov.html_report()

from unittest import TestLoader, TextTestRunner
import os

tests = TestLoader().discover(os.path.join(os.path.dirname(__file__), 'unit'))
TextTestRunner().run(tests)

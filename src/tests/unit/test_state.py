import unittest

from integration.state import ModelState, Transition, ModelStateMachine


class TestModelStateMachine(unittest.TestCase):

    def test_get(self):
        next_state_existing = ModelStateMachine.transition(Transition.EXISTING_OBJECT, None)
        next_state_missing = ModelStateMachine.transition(Transition.EXISTING_OBJECT, ModelState.DIRTY)

        self.assertEqual(next_state_existing, ModelState.CLEAN)
        self.assertEqual(next_state_missing, ModelState.DIRTY)

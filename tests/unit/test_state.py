from restio.state import ModelState, ModelStateMachine, Transition


class TestModelStateMachine:
    def test_get(self):
        next_state_existing = ModelStateMachine.transition(
            Transition.GET_OBJECT, ModelState.UNBOUND
        )
        next_state_missing = ModelStateMachine.transition(
            Transition.GET_OBJECT, ModelState.DIRTY
        )

        assert next_state_existing == ModelState.CLEAN
        assert next_state_missing == ModelState.DIRTY

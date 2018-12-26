from typing import Dict, Tuple, Optional
from enum import Enum


class ModelState(Enum):
    CLEAN = 0
    NEW = 1
    DIRTY = 2
    DELETED = 3
    DISCARDED = 4


class Transition(Enum):
    EXISTING_OBJECT = 000
    PERSIST_OBJECT = 100
    ADD_OBJECT = 200
    UPDATE_OBJECT = 300
    REMOVE_OBJECT = 400
    ROLLBACK_OBJECT = 500
    CLEAN_OBJECT = 600


class ModelStateMachine:
    _transitions: Dict[Tuple[Transition, Optional[ModelState]], ModelState] = {
        (Transition.EXISTING_OBJECT, None): ModelState.CLEAN,
        (Transition.ADD_OBJECT, None): ModelState.NEW,
        (Transition.UPDATE_OBJECT, ModelState.CLEAN): ModelState.DIRTY,
        (Transition.UPDATE_OBJECT, ModelState.DIRTY): ModelState.DIRTY,
        (Transition.CLEAN_OBJECT, ModelState.DIRTY): ModelState.CLEAN,
        (Transition.PERSIST_OBJECT, ModelState.NEW): ModelState.CLEAN,
        (Transition.PERSIST_OBJECT, ModelState.DIRTY): ModelState.CLEAN,
        (Transition.PERSIST_OBJECT, ModelState.DELETED): ModelState.DISCARDED,
        (Transition.REMOVE_OBJECT, ModelState.CLEAN): ModelState.DELETED,
        (Transition.REMOVE_OBJECT, ModelState.DIRTY): ModelState.DELETED,
        (Transition.REMOVE_OBJECT, ModelState.NEW): ModelState.DISCARDED,
        (Transition.ROLLBACK_OBJECT, ModelState.DIRTY): ModelState.CLEAN,
        (Transition.ROLLBACK_OBJECT, ModelState.NEW): ModelState.DISCARDED,
        (Transition.ROLLBACK_OBJECT, ModelState.DELETED): ModelState.DISCARDED,
    }

    @classmethod
    def transition(cls, transition: Transition, current_state: Optional[ModelState]):
        return cls._transitions.get((transition, current_state), current_state)

from enum import IntEnum, auto
from typing import Dict, Optional, Tuple


class ModelState(IntEnum):
    CLEAN = auto()
    NEW = auto()
    DIRTY = auto()
    DELETED = auto()
    DISCARDED = auto()


class Transition(IntEnum):
    EXISTING_OBJECT = auto()
    PERSIST_OBJECT = auto()
    ADD_OBJECT = auto()
    UPDATE_OBJECT = auto()
    REMOVE_OBJECT = auto()
    ROLLBACK_OBJECT = auto()
    CLEAN_OBJECT = auto()


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

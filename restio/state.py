from enum import IntEnum, auto
from typing import Dict, Tuple


class ModelState(IntEnum):
    """
    Contains the state of each model within a Transaction scope.

    - UNBOUND indicates that the model is not bound to any Transaction.
    - CLEAN indicates that the model has been retrieved from the remote server and has
    not been modified. CLEAN models are ignored during a `commit`.
    - NEW indicates that the model has been created within the transaction scope, but
    not yet exists on the remote server. During `commit`, the model will be passed by
    the transaction to the DAO's `add` method.
    - DIRTY indicates that the model has been retrieved from the remote server but has
    been modified within the Transaction scope. During `commit`, the model will be
    passed by the transaction to the DAO's `update` method.
    - DELETED indicates that the model has been retrieved from the remote server but
    has been deleted within the Transaction scope. During `commit`, the model will be
    passed by the transaction to the DAO's `remove` method.
    - DISCARDED indicates that the model has been discarded from the internal
    Transaction cache and is ready to be cleared up.

    The state management of models is done entirely by the Transaction instance and
    stored as part of the model instance.
    """

    UNBOUND = auto()
    CLEAN = auto()
    NEW = auto()
    DIRTY = auto()
    DELETED = auto()
    DISCARDED = auto()


class Transition(IntEnum):
    """
    Contains the possible transitions of an object within the Transaction scope. It is
    used by the ModelStateMachine and Transaction to figure out the next state of an
    object.
    """

    GET_OBJECT = auto()
    PERSIST_OBJECT = auto()
    ADD_OBJECT = auto()
    UPDATE_OBJECT = auto()
    REMOVE_OBJECT = auto()
    ROLLBACK_OBJECT = auto()
    CLEAN_OBJECT = auto()


class ModelStateMachine:
    """
    Statically defines all possible resulting states of a model with current state
    ModelState going through a transition Transition.
    """

    _transitions: Dict[Tuple[Transition, ModelState], ModelState] = {
        (Transition.GET_OBJECT, ModelState.UNBOUND): ModelState.CLEAN,
        (Transition.ADD_OBJECT, ModelState.UNBOUND): ModelState.NEW,
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
    def transition(
        cls, transition: Transition, current_state: ModelState
    ) -> ModelState:
        """
        Maps the Transition `transition` from `current_state` to a new ModelState.

        :param transition: The Transition being made by the Transaction.
        :param current_state: The current ModelState of the model.
        :return: The resulting model state after the transition.
        """
        key = (transition, current_state)
        return cls._transitions.get(key, current_state)

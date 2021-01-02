from contextvars import ContextVar
from typing import TYPE_CHECKING, Dict, Optional, Type

if TYPE_CHECKING:
    from restio.session import Session

CURRENT_SESSION: ContextVar[Optional["Session"]] = ContextVar(
    "current_session", default=None
)


# Stores the names for a model class type
# this object stays here and is globaly declared so that it can be
# accessed by both BaseModelMeta and Field instances
# In case we need to do any further business with this object,
# then implement a Singleton class to handle the object in a more
# structured way
MODEL_TYPE_REGISTRY: Dict[str, Type] = {}


MODEL_INSTANTIATED_EVENT = "__init__"
MODEL_PRE_UPDATE_EVENT = "__pre_update__"
MODEL_UPDATE_EVENT = "__updated__"

from typing import Optional
from uuid import uuid4, UUID


class BaseModel:
    _internal_id: UUID

    def __init__(self, uuid: Optional[UUID] = None) -> None:
        self._internal_id = uuid if uuid else uuid4()

    def __hash__(self):
        return hash(str(self._internal_id))

    def __eq__(self, other):
        if other and isinstance(other, type(self)):
            return self.__hash__() == other.__hash__()

        return False

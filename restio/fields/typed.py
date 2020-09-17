from typing import Callable, FrozenSet, Optional, Tuple, Type, Union

from restio.fields.base import (
    MISSING,
    Field,
    FrozenType,
    IterableField,
    Model_co,
    SetterType,
    SubT,
)


class IntField(Field[int]):
    def __init__(
        self,
        *,
        pk: bool = False,
        init: bool = True,
        default: Union[Optional[int], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], int]], Type[MISSING]] = MISSING,
        allow_none: bool = False,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=int,
            pk=pk,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=False,
            frozen=frozen,
            setter=setter,
        )


class StrField(Field[str]):
    def __init__(
        self,
        *,
        pk: bool = False,
        init: bool = True,
        default: Union[Optional[str], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], str]], Type[MISSING]] = MISSING,
        allow_none: bool = False,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=str,
            pk=pk,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=False,
            frozen=frozen,
            setter=setter,
        )


class BoolField(Field[bool]):
    def __init__(
        self,
        *,
        pk: bool = False,
        init: bool = True,
        default: Union[Optional[bool], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], bool]], Type[MISSING]] = MISSING,
        allow_none: bool = False,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=bool,
            pk=pk,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=False,
            frozen=frozen,
            setter=setter,
        )


class TupleField(IterableField[Tuple[SubT, ...], SubT]):
    def __init__(
        self,
        sub_type: Type[SubT],
        *,
        init: bool = True,
        depends_on: bool = False,
        default: Union[Optional[Tuple[SubT, ...]], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], Tuple[SubT, ...]]], Type[MISSING]
        ] = MISSING,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=tuple,
            sub_type=sub_type,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=False,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
        )


class FrozenSetField(IterableField[FrozenSet[SubT], SubT]):
    def __init__(
        self,
        sub_type: Type[SubT],
        *,
        init: bool = True,
        depends_on: bool = False,
        default: Union[Optional[FrozenSet[SubT]], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], FrozenSet[SubT]]], Type[MISSING]
        ] = MISSING,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=frozenset,
            sub_type=sub_type,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=False,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
        )


class ModelField(Field[Model_co]):
    def __init__(
        self,
        model_type: Type[Model_co],
        *,
        init: bool = True,
        default: Union[Optional[Model_co], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], Model_co]], Type[MISSING]
        ] = MISSING,
        allow_none: bool = True,
        depends_on: bool = True,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=model_type,
            pk=False,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
        )


class TupleModelField(TupleField[Model_co]):
    def __init__(
        self,
        model_type: Type[Model_co],
        *,
        init: bool = True,
        default: Union[Tuple[Model_co, ...], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], Tuple[Model_co, ...]]], Type[MISSING]
        ] = MISSING,
        depends_on: bool = True,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            sub_type=model_type,
            init=init,
            default=default,
            default_factory=default_factory,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
        )


class FrozenSetModelField(FrozenSetField[Model_co]):
    def __init__(
        self,
        model_type: Type[Model_co],
        *,
        init: bool = True,
        default: Union[Optional[FrozenSet[Model_co]], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], FrozenSet[Model_co]]], Type[MISSING]
        ] = MISSING,
        depends_on: bool = True,
        frozen: FrozenType = FrozenType.NEVER,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            sub_type=model_type,
            init=init,
            default=default,
            default_factory=default_factory,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
        )

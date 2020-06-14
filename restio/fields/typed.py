from typing import Callable, FrozenSet, Optional, Tuple, Type, TypeVar, Union

from restio.fields.base import MISSING, Field, FrozenType, IterableField, SubT


class IntField(Field[int]):
    def __init__(
        self,
        *,
        pk: bool = False,
        default: Union[Optional[int], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], int]], Type[MISSING]] = MISSING,
        allow_none: bool = False,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        default_factory = (
            int
            if default is MISSING and default_factory is MISSING and not allow_none
            else default_factory
        )
        super().__init__(
            type_=int,
            pk=pk,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=False,
            frozen=frozen,
        )


class StrField(Field[str]):
    def __init__(
        self,
        *,
        pk: bool = False,
        default: Union[Optional[str], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], str]], Type[MISSING]] = MISSING,
        allow_none: bool = False,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        default_factory = (
            str
            if default is MISSING and default_factory is MISSING and not allow_none
            else default_factory
        )
        super().__init__(
            type_=str,
            pk=pk,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=False,
            frozen=frozen,
        )


class BoolField(Field[bool]):
    def __init__(
        self,
        *,
        pk: bool = False,
        default: Union[Optional[bool], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], bool]], Type[MISSING]] = MISSING,
        allow_none: bool = False,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        default_factory = (
            bool
            if default is MISSING and default_factory is MISSING and not allow_none
            else default_factory
        )
        super().__init__(
            type_=bool,
            pk=pk,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=False,
            frozen=frozen,
        )


class TupleField(IterableField[Tuple[SubT, ...]]):
    def __init__(
        self,
        sub_type: Type[SubT],
        *,
        depends_on: bool = False,
        default: Union[Optional[Tuple[SubT, ...]], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], Tuple[SubT, ...]]], Type[MISSING]
        ] = MISSING,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        default_factory = (
            tuple
            if default is MISSING and default_factory is MISSING
            else default_factory
        )
        super().__init__(
            type_=tuple,
            sub_type=sub_type,
            default=default,
            default_factory=default_factory,
            allow_none=False,
            depends_on=depends_on,
            frozen=frozen,
        )


class FrozenSetField(IterableField[FrozenSet[SubT]]):
    def __init__(
        self,
        sub_type: Type[SubT],
        *,
        depends_on: bool = False,
        default: Union[Optional[FrozenSet[SubT]], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], FrozenSet[SubT]]], Type[MISSING]
        ] = MISSING,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        default_factory = (
            frozenset
            if default is MISSING and default_factory is MISSING
            else default_factory
        )
        super().__init__(
            type_=frozenset,
            sub_type=sub_type,
            default=default,
            default_factory=default_factory,
            allow_none=False,
            depends_on=depends_on,
            frozen=frozen,
        )


ModelType = TypeVar("ModelType", covariant=True)


class ModelField(Field[ModelType]):
    def __init__(
        self,
        model_type: Type[ModelType],
        *,
        default: Union[Optional[ModelType], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], ModelType]], Type[MISSING]
        ] = MISSING,
        allow_none: bool = True,
        depends_on: bool = True,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        super().__init__(
            type_=model_type,
            pk=False,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=depends_on,
            frozen=frozen,
        )


class TupleModelField(TupleField[ModelType]):
    def __init__(
        self,
        model_type: Type[ModelType],
        *,
        default: Union[Tuple[ModelType, ...], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], Tuple[ModelType, ...]]], Type[MISSING]
        ] = MISSING,
        depends_on: bool = True,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        super().__init__(
            sub_type=model_type,
            default=default,
            default_factory=default_factory,
            depends_on=depends_on,
            frozen=frozen,
        )


class FrozenSetModelField(FrozenSetField[ModelType]):
    def __init__(
        self,
        model_type: Type[ModelType],
        *,
        default: Union[Optional[FrozenSet[ModelType]], Type[MISSING]] = MISSING,
        default_factory: Union[
            Optional[Callable[[], FrozenSet[ModelType]]], Type[MISSING]
        ] = MISSING,
        depends_on: bool = True,
        frozen: FrozenType = FrozenType.NEVER,
    ) -> None:
        super().__init__(
            sub_type=model_type,
            default=default,
            default_factory=default_factory,
            depends_on=depends_on,
            frozen=frozen,
        )

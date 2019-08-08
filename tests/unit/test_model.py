from typing import List, Optional

import pytest

from restio.model import (BaseModel, DefaultPrimaryKey, PrimaryKey, mdataclass,
                          pk)


@mdataclass
class ModelSinglePKInt(BaseModel):
    id: PrimaryKey[int] = pk(int)


@mdataclass
class ModelSinglePKStr(BaseModel):
    id: PrimaryKey[str] = pk(str)


@mdataclass
class ModelDoublePKIntStr(BaseModel):
    id: PrimaryKey[int] = pk(int)
    key: PrimaryKey[str] = pk(str)


@mdataclass
class ModelDoublePKStrInt(BaseModel):
    key: PrimaryKey[str] = pk(str)
    id: PrimaryKey[int] = pk(int)


@mdataclass
class ModelA(BaseModel):
    id: PrimaryKey[int] = pk(int)
    a: int = 0
    b: str = ''


@mdataclass
class ModelB(BaseModel):
    ref: Optional[ModelA] = None
    c: int = 0


@mdataclass
class ModelC(BaseModel):
    ref: Optional[List[ModelB]] = None
    d: str = ''


@mdataclass
class ModelD(BaseModel):
    ref: Optional['ModelE'] = None  # noqa: F821


@mdataclass
class ModelE(BaseModel):
    ref: Optional[ModelD] = None


class TestPrimaryKey:

    def test_equal(self):
        x = PrimaryKey(int, 1)
        y = PrimaryKey(str, "2")

        assert x == 1
        assert x == PrimaryKey(int, 1)
        assert y == "2"
        assert y == PrimaryKey(str, "2")

    def test_not_equal(self):
        x = PrimaryKey(int, 1)
        y = PrimaryKey(str, "2")

        assert x != 2
        assert x != PrimaryKey(int, 2)
        assert x != "1"
        assert x != PrimaryKey(str, "1")
        assert y != "1"
        assert y != PrimaryKey(str, "1")
        assert y != 2
        assert y != PrimaryKey(int, 2)

    def test_set(self):
        x = PrimaryKey(int, 0)
        type_error = "Primary key value must be of type"
        assert x.value == 0

        x.set(1)
        assert x.value == 1

        with pytest.raises(RuntimeError, match=type_error):
            x.set("1")


class TestModel:

    @pytest.fixture
    def a(self):
        return ModelA(a=1, b='a')

    @pytest.fixture
    def b(self):
        return ModelB(c='b')

    @pytest.fixture
    def c(self):
        return ModelC()

    @pytest.fixture
    def single_int(self):
        return ModelSinglePKInt()

    @pytest.fixture
    def single_str(self):
        return ModelSinglePKStr()

    @pytest.fixture
    def double_is(self):
        return ModelDoublePKIntStr()

    @pytest.fixture
    def double_si(self):
        return ModelDoublePKStrInt()

    def test_primary_key_int(self, single_int):
        single_int.id = PrimaryKey(int, 1)

        assert single_int.id == 1
        assert single_int.get_keys() == (1,)

    def test_primary_key_str(self, single_str):
        single_str.id = "1"

        assert single_str.id == "1"
        assert single_str.get_keys() == ("1",)

    def test_primary_key_double_int_str(self, double_is):
        double_is.id, double_is.key = 1, "2"

        assert double_is.id == 1
        assert double_is.key == "2"
        assert double_is.get_keys() == (1, "2")

    def test_primary_key_double_str_int(self, double_si):
        double_si.key, double_si.id = "1", 2

        assert double_si.key == "1"
        assert double_si.id == 2
        assert double_si.get_keys() == ("1", 2)

    def test_primary_key_type_error(self):
        PrimaryKey(int)
        PrimaryKey(str)

        with pytest.raises(TypeError):
            PrimaryKey(object)

    def test_primary_key_set_error(self, single_int, b):
        with pytest.raises(RuntimeError, match="value must be of type"):
            single_int.id = "1"

        single_int.id = 2
        assert single_int.id == 2
        assert single_int.get_keys() == (2,)

        single_int.id = 3
        assert single_int.id == 3
        assert single_int.get_keys() == (3,)

    def test_get_mutable(self, a, b):
        assert set(a._class_mutable) == set(['id', 'a', 'b'])
        assert set(b._class_mutable) == set(['ref', 'c'])
        assert set(a._get_mutable_fields().values()) == set([DefaultPrimaryKey, 1, 'a'])
        assert set(b._get_mutable_fields().values()) == set([DefaultPrimaryKey, 'b'])

    def test_modify_mutable(self, a):
        old_value_a, old_value_b = a.a, a.b
        new_value_a = "new value a"
        new_value_b = "new value b"
        assert not a._persistent_values
        a.a = new_value_a
        a.b = new_value_b
        assert a.a == new_value_a
        assert a._persistent_values['a'] == old_value_a
        assert a.b == new_value_b
        assert a._persistent_values['b'] == old_value_b
        a.a = old_value_a
        assert 'a' not in a._persistent_values
        assert a.a == old_value_a
        assert a.b == new_value_b
        assert a._persistent_values['b'] == old_value_b
        a.b = old_value_b
        assert a.b == old_value_b
        assert 'b' not in a._persistent_values

    def test_get_children(self):
        a = ModelA()
        b = ModelB()
        c = ModelC()

        c.ref, b.ref = [b], a

        all_children = c.get_children(True)
        assert a in all_children
        assert b in all_children

        one_child = c.get_children(False)
        assert b in one_child
        assert a not in one_child

    def test_get_children_circular(self):
        b = ModelB()
        c = ModelC()

        c.ref, b.ref = set([b]), c
        one_child = c.get_children(True)

        assert b in one_child
        assert c not in one_child

    def test_equal(self):
        a1, a2 = ModelA(), ModelA()
        a3 = ModelA()
        a3._internal_id = a1._internal_id

        assert a1 != a2
        assert a1 == a3

        a3.id = 1
        assert a1 == a3

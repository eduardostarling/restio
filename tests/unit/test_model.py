from typing import List, Optional

import pytest

from restio.model import BaseModel, PrimaryKey, mdataclass, pk


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
        assert set(a._mutable) == set(['id', 'a', 'b'])
        assert set(b._mutable) == set(['ref', 'c'])
        assert set(a._get_mutable_fields().values()) == set([None, 1, 'a'])
        assert set(b._get_mutable_fields().values()) == set([None, 'b'])

    def test_copy(self, a, b, c):
        a.id = 1
        a.a, a.b = 2, "3"

        b.ref, b.c = a, 4
        c.ref, c.d = [b], "5"

        c_c = c.copy()
        c_b = c_c.ref[0]
        c_a = c_b.ref

        assert c_a.id == 1
        assert c_a.a == 2
        assert c_a.b == "3"
        assert c_b.c == 4
        assert c_c.d == "5"

    def test_copy_circular(self):
        d = ModelD()
        e = ModelE()

        e.ref, d.ref = d, e
        c_d = d.copy()

        assert c_d.ref._internal_id == e._internal_id

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
        a3 = a1.copy()

        assert a1 != a2
        assert a1 == a3

        a3.id = 1
        assert a1 == a3

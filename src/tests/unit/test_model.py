from typing import List, Optional
from .base import TestBase

from restio.model import mdataclass, BaseModel, PrimaryKey, pk


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


class TestPrimaryKey(TestBase):

    def test_equal(self):
        x = PrimaryKey(int, 1)
        y = PrimaryKey(str, "2")

        self.assertEqual(x, 1)
        self.assertEqual(x, PrimaryKey(int, 1))
        self.assertEqual(y, "2")
        self.assertEqual(y, PrimaryKey(str, "2"))

    def test_not_equal(self):
        x = PrimaryKey(int, 1)
        y = PrimaryKey(str, "2")

        self.assertNotEqual(x, 2)
        self.assertNotEqual(x, PrimaryKey(int, 2))
        self.assertNotEqual(x, "1")
        self.assertNotEqual(x, PrimaryKey(str, "1"))
        self.assertNotEqual(y, "1")
        self.assertNotEqual(y, PrimaryKey(str, "1"))
        self.assertNotEqual(y, 2)
        self.assertNotEqual(y, PrimaryKey(int, 2))

    def test_set(self):
        x = PrimaryKey(int, 0)
        type_error = "Primary key value must be of type"
        self.assertEqual(x.value, 0)

        x.set(1)
        self.assertEqual(x.value, 1)

        with self.assertRaises(RuntimeError) as ex:
            x.set("1")
        self.assertIn(type_error, str(ex.exception))


class TestModel(TestBase):

    def test_primary_key_int(self):
        x = ModelSinglePKInt()
        x.set_keys(PrimaryKey(int, 1))

        self.assertEqual(x.id.value, 1)
        self.assertEqual(x.get_keys(), (1,))

    def test_primary_key_str(self):
        x = ModelSinglePKStr()
        x.set_keys(("1"))

        self.assertEqual(x.id.value, "1")
        self.assertEqual(x.get_keys(), ("1",))

    def test_primary_key_double_int_str(self):
        x = ModelDoublePKIntStr()
        x.set_keys((1, "2"))

        self.assertEqual(x.id.value, 1)
        self.assertEqual(x.key.value, "2")
        self.assertEqual(x.get_keys(), (1, "2"))

    def test_primary_key_double_str_int(self):
        x = ModelDoublePKStrInt()
        x.set_keys(("1", 2))

        self.assertEqual(x.key.value, "1")
        self.assertEqual(x.id.value, 2)
        self.assertEqual(x.get_keys(), ("1", 2))

    def test_primary_key_type_error(self):
        PrimaryKey(int)
        PrimaryKey(str)

        with self.assertRaises(TypeError):
            PrimaryKey(object)

    def test_primary_key_set_error(self):
        x = ModelSinglePKInt()
        b = ModelB()

        with self.assertRaises(RuntimeError) as ex:
            x.set_keys(("1"))

        self.assertIn("Type str on position 0 incompatible",
                      str(ex.exception))

        x.set_keys((2,))
        self.assertEqual(x.id.value, 2)
        self.assertEqual(x.get_keys(), (2,))

        x.set_keys([3])
        self.assertEqual(x.id.value, 3)
        self.assertEqual(x.get_keys(), (3,))

        with self.assertRaises(RuntimeError) as ex:
            b.set_keys((1))

        self.assertIn("This object does not contain primary keys.",
                      str(ex.exception))

        with self.assertRaises(RuntimeError) as ex:
            x.set_keys((1, 2))

        self.assertIn("The number of primary keys provided is incompatible.",
                      str(ex.exception))

    def test_get_mutable(self):
        x = ModelA()
        y = ModelB()

        self.assertSetEqual(set(x._get_mutable_fields().keys()), set(['id', 'a', 'b']))
        self.assertSetEqual(set(y._get_mutable_fields().keys()), set(['ref', 'c']))

    def test_copy(self):
        a = ModelA()
        b = ModelB()
        c = ModelC()

        a.set_keys(1)
        a.a = 2
        a.b = "3"

        b.ref = a
        b.c = 4

        c.ref = [b]
        c.d = "5"

        c_c = c.copy()
        c_b = c_c.ref[0]
        c_a = c_b.ref

        self.assertEqual(c_a.id, 1)
        self.assertEqual(c_a.a, 2)
        self.assertEqual(c_a.b, "3")
        self.assertEqual(c_b.c, 4)
        self.assertEqual(c_c.d, "5")

    def test_copy_circular(self):
        d = ModelD()
        e = ModelE()

        e.ref = d
        d.ref = e

        c_d = d.copy()
        self.assertEqual(c_d.ref._internal_id, e._internal_id)

    def test_get_children(self):
        a = ModelA()
        b = ModelB()
        c = ModelC()

        c.ref = [b]
        b.ref = a

        all_children = c.get_children(True)
        self.assertIn(a, all_children)
        self.assertIn(b, all_children)

        one_child = c.get_children(False)
        self.assertIn(b, one_child)
        self.assertNotIn(a, one_child)

    def test_get_children_circular(self):
        b = ModelB()
        c = ModelC()

        c.ref = set([b])
        b.ref = c

        one_child = c.get_children(True)
        self.assertIn(b, one_child)
        self.assertNotIn(c, one_child)

    def test_equal(self):
        a1 = ModelA()
        a2 = ModelA()
        a3 = a1.copy()

        self.assertNotEqual(a1, a2)
        self.assertEqual(a1, a3)

        a3.set_keys(1)
        self.assertEqual(a1, a3)

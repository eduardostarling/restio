import unittest

from integration.model import BaseModel, PrimaryKey


class ModelSinglePKInt(BaseModel):
    id: PrimaryKey[int]


class ModelSinglePKStr(BaseModel):
    id: PrimaryKey[str]


class ModelDoublePKIntStr(BaseModel):
    id: PrimaryKey[int]
    key: PrimaryKey[str]


class ModelDoublePKStrInt(BaseModel):
    key: PrimaryKey[str]
    id: PrimaryKey[int]


class ModelA(BaseModel):
    id: PrimaryKey[int]
    a: int
    b: str


class ModelB(BaseModel):
    ref: ModelA
    c: int


class ModelC(BaseModel):
    ref: ModelB
    d: str


class ModelD(BaseModel):
    ref: 'ModelE'  # noqa: F821


class ModelE(BaseModel):
    ref: ModelD


class TestPrimaryKey(unittest.TestCase):

    def test_equal(self):
        x = PrimaryKey(1)
        y = PrimaryKey("2")

        self.assertEqual(x, 1)
        self.assertEqual(x, PrimaryKey(1))
        self.assertEqual(y, "2")
        self.assertEqual(y, PrimaryKey("2"))

    def test_not_equal(self):
        x = PrimaryKey(1)
        y = PrimaryKey("2")

        self.assertNotEqual(x, 2)
        self.assertNotEqual(x, PrimaryKey(2))
        self.assertNotEqual(x, "1")
        self.assertNotEqual(x, PrimaryKey("1"))
        self.assertNotEqual(y, "1")
        self.assertNotEqual(y, PrimaryKey("1"))
        self.assertNotEqual(y, 2)
        self.assertNotEqual(y, PrimaryKey(2))

    def test_set(self):
        x = PrimaryKey(0)
        type_error = "Primary key value must be of type"
        self.assertEqual(x.value, 0)

        x.set(1)
        self.assertEqual(x.value, 1)

        with self.assertRaises(RuntimeError) as ex:
            x.set("1")
        self.assertIn(type_error, str(ex.exception))


class TestModel(unittest.TestCase):

    def test_primary_key_int(self):
        x = ModelSinglePKInt()
        x.set_keys((1))

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

    def test_primary_key_set_error(self):
        x = ModelSinglePKInt()
        b = ModelB()

        with self.assertRaises(RuntimeError) as ex:
            x.set_keys(("1"))

        self.assertIn("Type str on position 0 incompatible",
                      str(ex.exception))

        x.set_keys((2))
        self.assertEqual(x.id.value, 2)
        self.assertEqual(x.get_keys(), (2,))

        with self.assertRaises(RuntimeError) as ex:
            b.set_keys((1))

        self.assertIn("This object does not contain primary keys.",
                      str(ex.exception))

        with self.assertRaises(RuntimeError) as ex:
            x.set_keys((1, 2))

        self.assertIn("The number of primary keys provided is incompatible.",
                      str(ex.exception))

        with self.assertRaises(RuntimeError) as ex:
            ModelC(primary_keys=(1))

        self.assertIn("This model does not contain primary keys.",
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

        c.ref = b
        c.d = "5"

        c_c = c.copy()
        c_b = c_c.ref
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
        self.assertEqual(c_d.ref, e)

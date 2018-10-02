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

        with self.assertRaises(RuntimeError) as ex:
            x.set_keys(("1"))

        self.assertIn("Type str on position 0 incompatible",
                      str(ex.exception))

        x.set_keys((2))
        self.assertEqual(x.id.value, 2)
        self.assertEqual(x.get_keys(), (2,))

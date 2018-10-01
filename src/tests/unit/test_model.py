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
    id: PrimaryKey[int]
    key: PrimaryKey[str]

    def __init__(self):
        self._default_primary_key = 'key'


class TestModel(unittest.TestCase):

    def test_primary_key_int(self):
        x = ModelSinglePKInt()

        self.assertEqual(x._default_primary_key, 'id')
        self.assertEqual(x._get_key_attribute(), 'id')

        x.set_key(1)
        self.assertEqual(x.id.value, 1)
        self.assertEqual(x.get_key(), 1)

    def test_primary_key_str(self):
        x = ModelSinglePKStr()

        self.assertEqual(x._default_primary_key, 'id')
        self.assertEqual(x._get_key_attribute(), 'id')

        x.set_key("1")
        self.assertEqual(x.id.value, "1")
        self.assertEqual(x.get_key(), "1")

    def test_primary_key_double_int_str(self):
        x = ModelDoublePKIntStr()

        self.assertEqual(x._default_primary_key, 'id')
        self.assertEqual(x._get_key_attribute(), 'id')

        self.assertEqual(x._get_key_attribute(int), 'id')
        self.assertEqual(x._get_key_attribute(str), 'key')

        x.set_key(1)
        self.assertEqual(x.id.value, 1)
        self.assertEqual(x.get_key(), 1)

        x.set_key("2", str)
        self.assertEqual(x.key.value, "2")
        self.assertEqual(x.get_key(str), "2")

    def test_primary_key_double_str_int(self):
        x = ModelDoublePKStrInt()

        self.assertEqual(x._default_primary_key, 'key')
        self.assertEqual(x._get_key_attribute(), 'key')

        self.assertEqual(x._get_key_attribute(int), 'id')
        self.assertEqual(x._get_key_attribute(str), 'key')

        x.set_key("1")
        self.assertEqual(x.key.value, "1")
        self.assertEqual(x.get_key(), "1")

        x.set_key(2, int)
        self.assertEqual(x.id.value, 2)
        self.assertEqual(x.get_key(int), 2)

    def test_primary_key_set_error(self):
        x = ModelSinglePKInt()

        with self.assertRaises(RuntimeError) as ex:
            x.set_key("1")

        self.assertIn("Primary key value must be of type int", str(ex.exception))

        with self.assertRaises(RuntimeError) as ex:
            x.set_key("1", str)

        self.assertIn("No PrimaryKey with type str", str(ex.exception))

        x.set_key(2)
        self.assertEqual(x.id.value, 2)
        self.assertEqual(x.get_key(), 2)

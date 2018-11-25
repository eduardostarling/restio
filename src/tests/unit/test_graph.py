from typing import List, Optional
import unittest

from integration.model import BaseModel, mdataclass
from integration.graph import Node, Tree, DependencyGraph


"""
A   B       G
|   |       |
C   D       H
|\ /
E F
"""


@mdataclass
class ModelMock(BaseModel):
    name: str = ""
    first_child: Optional[BaseModel] = None
    second_child: Optional[BaseModel] = None


class TestNode(unittest.TestCase):
    pass


class TestTree(unittest.TestCase):
    pass


class TestGraph(unittest.TestCase):
    def get_models(self):
        model_e = ModelMock(name="E")
        model_f = ModelMock(name="F")
        model_h = ModelMock(name="H")
        model_c = ModelMock(name="C", first_child=model_e, second_child=model_f)
        model_d = ModelMock(name="D", first_child=model_f)
        model_a = ModelMock(name="A", first_child=model_c)
        model_b = ModelMock(name="B", first_child=model_d)
        model_g = ModelMock(name="G", first_child=model_h)

        return [model_a, model_b, model_c, model_d, model_e, model_f, model_g, model_h]

    def test_get_graph(self):
        models = self.get_models()
        graph = DependencyGraph.generate_from_objects(models)

        first_tree = graph.trees[0]
        second_tree = graph.trees[1]

        model_a, model_b = models[0:2]
        model_g = models[6]

        # first_tree_elements, second_tree_elements = models[0:6], models[6:8]

        self.assertEqual(len(graph.trees), 2)
        self.assertEqual(len(first_tree.roots), 2)
        self.assertEqual(len(second_tree.roots), 1)
        self.assertSetEqual(set(map(lambda x: x.node_object, first_tree.roots)), set([model_a, model_b]))
        self.assertSetEqual(set(map(lambda x: x.node_object, second_tree.roots)), set([model_g]))

from typing import Optional
from random import randint
from collections import deque
from .base import TestBase
import asyncio
import itertools

from restio.model import BaseModel, mdataclass
from restio.graph import Node, Tree, DependencyGraph, NavigationDirection


def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


@mdataclass
class ModelMock(BaseModel):
    name: str = ""
    first_child: Optional[BaseModel] = None
    second_child: Optional[BaseModel] = None


def generate_models():
    """
    A   B       G
    |   |       |
    C   D       H
    |\ /
    E F
    """
    model_e = ModelMock(name="E")
    model_f = ModelMock(name="F")
    model_h = ModelMock(name="H")
    model_c = ModelMock(name="C", first_child=model_e, second_child=model_f)
    model_d = ModelMock(name="D", first_child=model_f)
    model_a = ModelMock(name="A", first_child=model_c)
    model_b = ModelMock(name="B", first_child=model_d)
    model_g = ModelMock(name="G", first_child=model_h)

    return [model_a, model_b, model_c, model_d, model_e, model_f, model_g, model_h]


def generate_models_complex():
    """
      A
     /|
    B C I
      |/
      D
     /|
    E |
    |\|
    H F
      |
      G
    """
    model_g = ModelMock(name="G")
    model_h = ModelMock(name="H")
    model_b = ModelMock(name="B")
    model_f = ModelMock(name="F", first_child=model_g)
    model_e = ModelMock(name="E", first_child=model_f, second_child=model_h)
    model_d = ModelMock(name="D", first_child=model_e, second_child=model_f)
    model_c = ModelMock(name="C", first_child=model_d)
    model_i = ModelMock(name="I", first_child=model_d)
    model_a = ModelMock(name="A", first_child=model_b, second_child=model_c)

    return [model_a, model_b, model_c, model_d, model_e, model_f, model_g, model_h, model_i]


def generate_nodes(models):
    model_a, model_b, model_c, model_d, model_e, \
        model_f, model_g, model_h = models

    node_a = Node(model_a)
    node_b = Node(model_b)
    node_c = Node(model_c)
    node_d = Node(model_d)
    node_e = Node(model_e)
    node_f = Node(model_f)
    node_g = Node(model_g)
    node_h = Node(model_h)

    node_a.children.add(node_c)
    node_c.parents.add(node_a)
    node_c.children.add(node_e)
    node_e.parents.add(node_c)
    node_c.children.add(node_f)
    node_f.parents.add(node_c)
    node_b.children.add(node_d)
    node_d.parents.add(node_b)
    node_d.children.add(node_e)
    node_e.parents.add(node_d)
    node_g.children.add(node_h)
    node_h.parents.add(node_g)

    return [node_a, node_b, node_c, node_d, node_e, node_f, node_g, node_h]


def generate_nodes_complex(models):
    model_a, model_b, model_c, model_d, model_e, \
        model_f, model_g, model_h, model_i = models

    node_a = Node(model_a)
    node_b = Node(model_b)
    node_c = Node(model_c)
    node_d = Node(model_d)
    node_e = Node(model_e)
    node_f = Node(model_f)
    node_g = Node(model_g)
    node_h = Node(model_h)
    node_i = Node(model_i)

    node_a.children.add(node_b)
    node_b.parents.add(node_a)
    node_a.children.add(node_c)
    node_c.parents.add(node_a)

    node_c.children.add(node_d)
    node_d.parents.add(node_c)

    node_i.children.add(node_d)
    node_d.parents.add(node_i)

    node_d.children.add(node_e)
    node_e.parents.add(node_d)
    node_d.children.add(node_f)
    node_f.parents.add(node_d)

    node_e.children.add(node_h)
    node_h.parents.add(node_e)
    node_e.children.add(node_f)
    node_f.parents.add(node_e)

    node_f.children.add(node_g)
    node_g.parents.add(node_f)

    return [node_a, node_b, node_c, node_d, node_e, node_f, node_g, node_h, node_i]


def generate_trees(nodes):
    node_a, node_b, node_c, node_d, node_e, \
        node_f, node_g, node_h = nodes

    tree_ab = Tree([node_a, node_b, node_c, node_d, node_e, node_f])
    tree_g = Tree([node_g, node_h])

    return [tree_ab, tree_g]


def generate_trees_complex(nodes):
    node_a, node_b, node_c, node_d, node_e, \
        node_f, node_g, node_h, node_i = nodes

    tree_ai = Tree(nodes)

    return [tree_ai]


class TestNode(TestBase):
    def get_nodes(self):
        models = generate_models()
        return models, generate_nodes(models)

    def test_get_children(self):
        models, nodes = self.get_nodes()
        node_a = nodes[0]
        node_c = nodes[2]
        node_e = nodes[4]
        node_f = nodes[5]

        children = node_a.get_children(recursive=False)
        all_children = node_a.get_children(recursive=True)

        self.assertSetEqual(set(children), set([node_c]))
        self.assertSetEqual(set(all_children), set([node_c, node_e, node_f]))

    def test_equal(self):
        models, nodes = self.get_nodes()
        node_a = nodes[0]
        node_c = nodes[2]

        self.assertEqual(node_a, Node(node_a.node_object))
        self.assertEqual(node_a.children.pop(), node_c)
        self.assertEqual(node_c.parents.pop(), node_a)

        self.assertNotEqual(node_a, node_c)
        self.assertNotEqual(node_a, "")
        self.assertNotEqual(node_a, None)
        self.assertNotEqual(node_a, Node(None))


class TestTree(TestBase):
    def get_trees(self):
        models = generate_models()
        nodes = generate_nodes(models)
        return models, nodes, generate_trees(nodes)

    def get_trees_complex(self):
        models = generate_models_complex()
        nodes = generate_nodes_complex(models)
        return models, nodes, generate_trees_complex(nodes)

    async def validate_process(self, get_function):
        models, nodes, trees = get_function()

        processed_nodes = []
        directions = (NavigationDirection.LEAFS_TO_ROOTS, NavigationDirection.ROOTS_TO_LEAFS)

        for direction in directions:
            from_direction, to_direction = direction.value
            for tree in trees:
                def consume(node):
                    async def consume_function():
                        await asyncio.sleep(randint(1, 100) / 10000)
                        processed_nodes.append(node)
                        return node, node
                    return consume_function

                # generate (node, coroutine) tuples
                nodes_coroutines = set(map(lambda n: (n, consume(n)), tree.get_nodes()))
                # results come in queue format, therefore
                # we need to iterate in reverse order
                processed_nodes = list(reversed(await tree.process(nodes_coroutines, direction)))

                for index, node in enumerate(processed_nodes):
                    relatives = to_direction(node)
                    for relative in relatives:
                        self.assertGreater(processed_nodes.index(relative), index)

    @async_test
    async def test_process(self):
        await self.validate_process(self.get_trees)

    @async_test
    async def test_process_complex(self):
        await self.validate_process(self.get_trees_complex)

    def validate_navigate(self, get_function):
        models, nodes, trees = get_function()

        for tree in trees:
            for direction in NavigationDirection:
                processed_nodes = deque()
                # if all nodes are processed right away,
                # then the generator should not return None's
                for node in tree.navigate(tree.get_nodes(), direction, processed_nodes):
                    self.assertIsNotNone(node)
                    processed_nodes.append(node)

                self.assertEqual(len(processed_nodes), 0)

                # if no node is processed, then eventually
                # the generator will return None (after processing
                # the periferal nodes). This is not valid if the tree
                # has a single element
                for node in tree.navigate(tree.get_nodes(), direction, set()):
                    processed_nodes.append(node)
                    if node is None:
                        break

                self.assertGreater(len(processed_nodes), 0)

                if len(processed_nodes) > 1:
                    self.assertIn(None, processed_nodes)
                else:
                    self.assertNotIn(None, processed_nodes)

        return trees

    def test_navigation(self):
        self.validate_navigate(self.get_trees)

    def test_navigation_complex(self):
        self.validate_navigate(self.get_trees_complex)

    def test_navigation_invalid_node(self):
        models, nodes, trees = self.get_trees()
        first_tree, second_tree = trees

        gen = first_tree.navigate(first_tree.get_nodes(), NavigationDirection.LEAFS_TO_ROOTS,
                                  deque(second_tree.get_nodes()))

        next(gen)
        with self.assertRaises(StopIteration) as value:
            next(gen)

        self.assertFalse(value.exception.value)


class TestGraph(TestBase):
    def get_models(self):
        return generate_models()

    def test_get_graph(self):
        models = self.get_models()
        graph = DependencyGraph.generate_from_objects(models)

        trees = sorted(graph.trees, key=lambda tree: len(tree.get_roots()))
        first_tree = trees[0]
        first_tree_roots = first_tree.get_roots()
        second_tree = trees[1]
        second_tree_roots = second_tree.get_roots()

        model_a, model_b = models[0:2]
        model_g = models[6]

        # first_tree_elements, second_tree_elements = models[0:6], models[6:8]
        self.assertEqual(len(trees), 2)
        self.assertEqual(len(first_tree_roots), 1)
        self.assertEqual(len(second_tree_roots), 2)
        self.assertSetEqual(set(map(lambda x: x.node_object, first_tree_roots)), set([model_g]))
        self.assertSetEqual(set(map(lambda x: x.node_object, second_tree_roots)), set([model_a, model_b]))

    def test_circular_dependency(self):
        # slow test ahead
        models = self.get_models()
        model_f = models[5]

        models_for_circular = models[0:4]  # A, B, C, D
        models_for_circular.append(model_f)

        # will generate any permutation of (A, B, C, D, F)
        permutations = itertools.permutations(models_for_circular, len(models_for_circular))
        for models_to_check in permutations:
            models_to_check = list(models_to_check)
            for model in models_for_circular:
                model_f.first_child = model
                with self.assertRaises(RuntimeError) as ex:
                    DependencyGraph.generate_from_objects(models_to_check)
                self.assertIn("Circular dependency", str(ex.exception))

import asyncio
import itertools
from collections import deque
from random import randint
from typing import Optional

import pytest

from restio.graph import DependencyGraph, NavigationDirection, Node, Tree
from restio.model import BaseModel, mdataclass


@mdataclass
class ModelMock(BaseModel):
    name: str = ""
    first_child: Optional[BaseModel] = None
    second_child: Optional[BaseModel] = None


class ModelsFixture:
    @pytest.fixture
    def models(self):
        r"""
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

    @pytest.fixture
    def models_complex(self):
        r"""
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

    @pytest.fixture
    def nodes(self, models):
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

    @pytest.fixture
    def nodes_complex(self, models_complex):
        model_a, model_b, model_c, model_d, model_e, \
            model_f, model_g, model_h, model_i = models_complex

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

    @pytest.fixture
    def trees(self, nodes):
        node_a, node_b, node_c, node_d, node_e, \
            node_f, node_g, node_h = nodes

        tree_ab = Tree([node_a, node_b, node_c, node_d, node_e, node_f])
        tree_g = Tree([node_g, node_h])

        return [tree_ab, tree_g]

    @pytest.fixture
    def trees_complex(self, nodes_complex):
        node_a, node_b, node_c, node_d, node_e, \
            node_f, node_g, node_h, node_i = nodes_complex

        tree_ai = Tree(nodes_complex)

        return [tree_ai]


class TestNode(ModelsFixture):

    def test_get_children(self, models, nodes):
        node_a = nodes[0]
        node_c = nodes[2]
        node_e = nodes[4]
        node_f = nodes[5]

        children = node_a.get_children(recursive=False)
        all_children = node_a.get_children(recursive=True)

        assert set(children) == set([node_c])
        assert set(all_children) == set([node_c, node_e, node_f])

    def test_equal(self, models, nodes):
        node_a = nodes[0]
        node_c = nodes[2]

        assert node_a == Node(node_a.node_object)
        assert node_a.children.pop() == node_c
        assert node_c.parents.pop() == node_a

        assert node_a != node_c
        assert node_a != ""
        assert node_a is not None
        assert node_a != Node(None)


class TestTree(ModelsFixture):
    async def validate_process(self, models, nodes, trees):
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
                        assert processed_nodes.index(relative) > index

    def validate_navigate(self, models, nodes, trees):
        for tree in trees:
            for direction in NavigationDirection:
                processed_nodes = deque()
                # if all nodes are processed right away,
                # then the generator should not return None's
                for node in tree.navigate(tree.get_nodes(), direction, processed_nodes):
                    assert node is not None
                    processed_nodes.append(node)

                assert len(processed_nodes) == 0

                # if no node is processed, then eventually
                # the generator will return None (after processing
                # the periferal nodes). This is not valid if the tree
                # has a single element
                for node in tree.navigate(tree.get_nodes(), direction, set()):
                    processed_nodes.append(node)
                    if node is None:
                        break

                assert len(processed_nodes) > 0

                if len(processed_nodes) > 1:
                    assert None in processed_nodes
                else:
                    assert None not in processed_nodes

        return trees

    @pytest.mark.asyncio
    async def test_process(self, models, nodes, trees):
        await self.validate_process(models, nodes, trees)

    @pytest.mark.asyncio
    async def test_process_complex(self, models_complex, nodes_complex, trees_complex):
        await self.validate_process(models_complex, nodes_complex, trees_complex)

    def test_navigation(self, models, nodes, trees):
        self.validate_navigate(models, nodes, trees)

    def test_navigation_complex(self, models_complex, nodes_complex, trees_complex):
        self.validate_navigate(models_complex, nodes_complex, trees_complex)

    def test_navigation_invalid_node(self, models, nodes, trees):
        first_tree, second_tree = trees

        gen = first_tree.navigate(first_tree.get_nodes(), NavigationDirection.LEAFS_TO_ROOTS,
                                  deque(second_tree.get_nodes()))

        next(gen)
        with pytest.raises(StopIteration):
            next(gen)


class TestGraph(ModelsFixture):

    def test_get_graph(self, models):
        graph = DependencyGraph.generate_from_objects(models)

        trees = sorted(graph.trees, key=lambda tree: len(tree.get_roots()))
        first_tree = trees[0]
        first_tree_roots = first_tree.get_roots()
        second_tree = trees[1]
        second_tree_roots = second_tree.get_roots()

        model_a, model_b = models[0:2]
        model_g = models[6]

        # first_tree_elements, second_tree_elements = models[0:6], models[6:8]
        assert len(trees) == 2
        assert len(first_tree_roots) == 1
        assert len(second_tree_roots) == 2
        assert set(map(lambda x: x.node_object, first_tree_roots)) == set([model_g])
        assert set(map(lambda x: x.node_object, second_tree_roots)) == set([model_a, model_b])

    def test_circular_dependency(self, models):
        # slow test ahead
        model_f = models[5]

        models_for_circular = models[0:4]  # A, B, C, D
        models_for_circular.append(model_f)

        # will generate any permutation of (A, B, C, D, F)
        permutations = itertools.permutations(models_for_circular, len(models_for_circular))
        for models_to_check in permutations:
            models_to_check = list(models_to_check)
            for model in models_for_circular:
                model_f.first_child = model
                with pytest.raises(RuntimeError, match="Circular dependency"):
                    DependencyGraph.generate_from_objects(models_to_check)
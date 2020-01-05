from __future__ import annotations

import asyncio
from collections import deque
from enum import Enum
from typing import (Any, AsyncGenerator, Callable, Deque, Dict, List, Optional,
                    Set, Tuple, Union, cast)

# As a design decision, the classes in this file are bound to BaseModel
# to facilitate the navigation across different objects by utilizing
# the already built-in functionality get_children() and to allow monitoring
# of model states. If future implementation depends on drawing dependency
# graphs, then this file should be modified to decouple from BaseModel
# implementation. The node objects in this case will have to be Hashable.
from .model import BaseModel


class Node:
    """
    Represents a Node in a Tree of a DependencyGraph.

    Each Node instance stores a BaseModel object that represents a model in
    the dependency Tree. `parents` and `children` store references to the
    nodes immediately above and after in the dependency Tree.
    """
    node_object: BaseModel
    parents: Set[Node]
    children: Set[Node]

    def __init__(
        self, node_object: BaseModel, parents: Optional[Set[Node]] = None, children: Optional[Set[Node]] = None
    ):
        self.node_object = node_object
        self.parents = parents if parents else set()
        self.children = children if children else set()

    def _get_nodes(self, nodes_attribute: str, recursive: bool = False,
                   nodes: Optional[Set[Node]] = None) -> Set[Node]:
        dependent_nodes = getattr(self, nodes_attribute, [])

        if not recursive:
            return dependent_nodes.copy()

        if not nodes:
            nodes = set()

        for node in dependent_nodes:
            if node not in nodes:
                nodes.add(node)
                nodes = nodes.union(node._get_nodes(nodes_attribute, recursive, nodes))

        return nodes

    def get_children(self, recursive: bool = False, children: Optional[Set[Node]] = None) -> Set[Node]:
        """
        Returns the child nodes of the current Node.

        :param recursive: Indicates whether all child nodes should be
                          returned. Defaults to False.
        :param children: Contains the nodes that have already been inspected
                         and should be ignored. Used for recursion only.
        :return: Returns all children nodes, including children of children,
                 if `recursive` is True. The operation stops when all child
                 leaves are reached. Returns only the first degree children
                 if False.
        """
        return self._get_nodes('children', recursive=recursive, nodes=children)

    def get_parents(self, recursive: bool = False, parents: Optional[Set[Node]] = None) -> Set[Node]:
        """
        Returns the parent nodes of the current Node.

        :param recursive: Indicates whether all parent nodes should be
                          returned. Defaults to False.
        :param parents: Contains the nodes that have already been inspected
                         and should be ignored. Used for recursion only.
        :return: Returns all parent nodes, including parents of parents, if
                 `recursive` is True. The operation stops when parent roots are
                 reached. Returns only the first degree parents if False.
        """
        return self._get_nodes('parents', recursive=recursive, nodes=parents)

    def __hash__(self):
        return self.node_object.__hash__()

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False

        if not self.node_object or not other.node_object:
            return False

        return self.node_object.__hash__() == other.node_object.__hash__()


GetRelativesCallable = Callable[[Node, bool, Optional[Set[Node]]], Set[Node]]


class NavigationDirection(Enum):
    ROOTS_TO_LEAVES: Tuple[GetRelativesCallable, GetRelativesCallable] = (Node.get_parents, Node.get_children)
    LEAVES_TO_ROOTS: Tuple[GetRelativesCallable, GetRelativesCallable] = (Node.get_children, Node.get_parents)


class Tree:
    """
    Represents a Tree in a DependencyGraph.

    Each Tree stores a set of Nodes that have at least one degree of relationship
    with each other. The Tree and can be traversed with callback based tasks using
    the method `process`.
    """
    nodes: Set[Node]
    _canceled: bool
    _processing: bool

    def __init__(self, nodes: Set[Node]):
        self.nodes = nodes
        self._canceled = False
        self._processing = False

    @staticmethod
    def _get_tree_roots(tree_nodes: Set[Node]) -> Set[Node]:
        return set(filter(lambda x: not x.parents, tree_nodes))

    @staticmethod
    def _get_tree_leafs(tree_nodes: Set[Node]) -> Set[Node]:
        return set(filter(lambda x: not x.children, tree_nodes))

    def get_roots(self) -> Set[Node]:
        """
        Returns all roots of the Tree.

        :return: Set containing Node instances.
        """
        return self._get_tree_roots(self.nodes)

    def get_leafs(self) -> Set[Node]:
        """
        Returns all leaves of the Tree.

        :return: Set containing Node instances.
        """
        return self._get_tree_leafs(self.nodes)

    def get_nodes(self) -> Set[Node]:
        """
        Returns a copy of all nodes in the Tree.

        :return: Set with Node instances.
        """
        return self.nodes.copy()

    async def navigate(self, nodes: Set[Node], direction: NavigationDirection,
                       processed_nodes: asyncio.Queue[Node]) -> AsyncGenerator[Node, bool]:
        """
        Traverses the dependency Tree based on already processed nodes. The caller should
        maintain the queue `processed_nodes` with the nodes that have been processed on the
        past iteration. This generator will yield a Node instance when possible, otherwise it will
        hang until extra nodes processed.
        The Tree traversal order will depend on the `direction` specified (either from roots to
        leaves or leaves to roots) and the order in which nodes are processed by the caller.

        :param nodes: The set of Node instances to be processed.
        :param direction: The direction of navigation, either from LEAVES_TO_ROOTS (navigates
                          upwards in the tree) or ROOTS_TO_LEAVES (navigates downwards in the
                          tree).
        :param processed_nodes: The queue containing the nodes that have just been processed
                                by the caller.
        :raises TypeError: If the direction is invalid.
        """

        if direction == NavigationDirection.LEAVES_TO_ROOTS:
            entrypoint = self.get_leafs()
        elif direction == NavigationDirection.ROOTS_TO_LEAVES:
            entrypoint = self.get_roots()
        else:
            raise TypeError("The provided argument `direction` is invalid.")

        from_direction, to_direction = direction.value
        next_nodes = deque(n for n in entrypoint if n in nodes)

        processed: Optional[Node] = None

        while nodes or next_nodes:
            if next_nodes:
                yield next_nodes.pop()
                continue

            processed = await processed_nodes.get()

            if isinstance(processed, Node) and processed not in nodes:
                return

            nodes.remove(processed)

            nodes_to_direction = to_direction(processed) if processed else set()
            for node_to in nodes_to_direction:
                nodes_from_direction = from_direction(node_to)
                if not nodes_from_direction.intersection(nodes):
                    next_nodes.appendleft(node_to)

    def cancel(self):
        """
        Cancels the processing when `process` is active. Currently running tasks
        will be finalized normally, and new tasks will not be scheduled.
        """
        if self._processing:
            self._canceled = True


class DependencyGraph:
    """
    Represents dependency graph made of a combination of Tree instances.

    The DependencyGraph stores a list of Tree instances that contain all the
    Nodes in the graph. This module is also responsible to instantiate all Trees
    and Nodes given a set of objects of type BaseModel.
    """
    trees: List[Tree] = []

    def __init__(self, trees: List[Tree]):
        self.trees = trees

    @staticmethod
    def _get_connected_nodes(objects: Set[BaseModel]) -> Set[Node]:
        nodes: Dict[str, Node] = {}

        # creates nodes
        for node_object in objects:
            add_node = Node(node_object)
            nodes[str(node_object.__hash__())] = add_node

        # connects nodes
        for node in nodes.values():
            for child in node.node_object.get_children(recursive=False):
                child_node = nodes.get(str(child.__hash__()), None)
                if not child_node:
                    continue

                node.children.add(child_node)
                child_node.parents.add(node)

        # check for circular dependency
        for node in nodes.values():
            all_children = node.get_children(recursive=True)
            if all_children.intersection(node.get_parents(recursive=False)):
                raise RuntimeError("Circular dependency detected")

        return cast(Set[Node], nodes.values())

    @classmethod
    def generate_from_objects(cls, objects: Set[BaseModel]) -> DependencyGraph:
        """
        Generates a DependencyGraph instance based on the set of BaseModel instances
        `objects`.

        :param objects: The set of BaseModel instances.
        :return: The DependencyGraph instance.
        """
        nodes: Set[Node] = cls._get_connected_nodes(objects)
        return cls.generate_from_nodes(nodes)

    @classmethod
    def generate_from_nodes(cls, nodes: Set[Node]) -> DependencyGraph:
        """
        Generates a DependencyGraph instance based on the set of Node instances `nodes`.

        :param nodes: The set of Node instances
        :return: The DependencyGraph instance.
        """
        roots: Set[Node] = Tree._get_tree_roots(nodes)
        roots_children: Dict[Node, Set[Node]] = \
            {root: root.get_children(True) for root in roots}

        trees: List[Tree] = []

        # generates trees with intersections
        while roots:
            root = roots.pop()
            intersecting_items = set([root]).union(roots_children[root])
            intersecting_roots = set([root])
            for next_root in roots:
                next_root_children = set([next_root]).union(roots_children[next_root])
                if intersecting_items.intersection(next_root_children):
                    intersecting_items = intersecting_items.union(next_root_children)
                    intersecting_roots.add(next_root)

            trees.append(Tree(intersecting_items))
            roots = roots - intersecting_roots

        return cls(trees)

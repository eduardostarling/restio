from __future__ import annotations
from typing import List, Set, Dict, Optional
import itertools

from .model import BaseModel


class Node:
    node_object: BaseModel
    parents: Set['Node']
    children: Set['Node']

    def __init__(self, node_object: BaseModel, parents: Optional[Set['Node']] = None,
                 children: Optional[Set['Node']] = None):
        self.node_object = node_object
        self.parents = parents if parents else set()
        self.children = children if children else set()

    def get_children(self, recursive: bool = False):
        if not recursive:
            return self.children.copy()

        children: Set[Node] = self.children.copy()
        for child in self.children:
            children = children.union(child.get_children(recursive))

        return children

    def __hash__(self):
        return hash(self.node_object._internal_id)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False

        if not self.node_object or not other.node_object:
            return False

        return self.node_object._internal_id == other.node_object._internal_id


class Tree:
    roots: Set[Node]

    def __init__(self, roots: Set[Node]):
        self.roots = roots

    def get_independent_nodes(self):
        pass


class DependencyGraph:
    trees: List[Tree]

    def __init__(self, trees: List[Tree]):
        self.trees = trees

    @classmethod
    def generate_from_objects(cls, objects: List[BaseModel]) -> 'DependencyGraph':
        nodes: Dict[int, Node] = {}
        roots: Dict[Node, Set[Node]] = {}
        trees: List[Tree] = []

        # creates nodes
        for node_object in objects:  # type: BaseModel
            add_node = Node(node_object)
            nodes[node_object._internal_id] = add_node

        # connects nodes
        for node in nodes.values():  # type: Node
            for child in node.node_object.get_children(recursive=False):
                child_node = nodes.get(child._internal_id, None)
                if not child_node:
                    continue

                node.children.add(child_node)
                child_node.parents.add(node)

        # finds all trees' roots (nodes with no parents)
        for node in nodes.values():
            if not node.parents:
                roots[node] = node.get_children(True)

        # finds intersections
        tree_set = set()
        roots_set = set(roots.keys())

        while roots_set:
            node = roots_set.pop()
            intersecting_items = set([node])

            for next_root in roots_set:
                next_root_children = roots[next_root]
                for root_node in intersecting_items:
                    compare_children = roots[root_node]
                    if compare_children.intersection(next_root_children):
                        intersecting_items.add(next_root)
                        break

            tree_set.add(tuple(intersecting_items))
            roots_set = roots_set - intersecting_items

        for tree_roots in tree_set:
            tree = Tree(set(tree_roots))
            trees.append(tree)

        return cls(trees)

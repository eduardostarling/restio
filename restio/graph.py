from __future__ import annotations
from typing import List, Set, Dict, Tuple, Deque, Optional, Generator, \
    Coroutine, Callable, Union, Any, cast
from enum import Enum
from collections import deque
import asyncio

# As a design decision, the classes in this file are bound to BaseModel
# to facilitate the navigation across different objects by utilizing
# the already built-in functionality get_children() and to allow monitoring
# of model states. If future implementation depends on drawing dependency
# graphs, then this file should be modified to decouple from BaseModel
# implementation. The node objects in this case will have to be Hashable.
from .model import BaseModel


class Node:
    node_object: BaseModel
    parents: Set['Node']
    children: Set['Node']

    def __init__(
        self, node_object: BaseModel, parents: Optional[Set['Node']] = None, children: Optional[Set['Node']] = None
    ):
        self.node_object = node_object
        self.parents = parents if parents else set()
        self.children = children if children else set()

    def _get_nodes(self, nodes_attribute: str, recursive: bool = False,
                   nodes: Optional[Set['Node']] = None) -> Set['Node']:
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

    def get_children(self, recursive: bool = False, children: Optional[Set['Node']] = None) -> Set['Node']:
        return self._get_nodes('children', recursive=recursive, nodes=children)

    def get_parents(self, recursive: bool = False, parents: Optional[Set['Node']] = None) -> Set['Node']:
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
CallbackCoroutineCallable = Callable[[], Coroutine[Any, Any, Tuple[Node, Any]]]


class NavigationDirection(Enum):
    ROOTS_TO_LEAFS: Tuple[GetRelativesCallable, GetRelativesCallable] = (Node.get_parents, Node.get_children)
    LEAFS_TO_ROOTS: Tuple[GetRelativesCallable, GetRelativesCallable] = (Node.get_children, Node.get_parents)


class NodeProcessException(Exception):
    def __init__(self, error: Exception, node: Node):
        super().__init__(error)
        self.error = error
        self.node = node


class TreeProcessException(Exception):
    def __init__(self, processed_values: Deque[Union[Any, NodeProcessException]]):
        super().__init__()
        self.processed_values = processed_values


class Tree:
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

    def get_roots(self):
        return self._get_tree_roots(self.nodes)

    def get_leafs(self):
        return self._get_tree_leafs(self.nodes)

    async def process(
        self,
        nodes_tasks: Set[Tuple[Node, Optional[CallbackCoroutineCallable]]],
        direction: NavigationDirection,
        cancel_on_error: bool = True
    ) -> Deque[Any]:

        self._processing = True
        self._canceled = False

        task_map = {node: task for node, task in nodes_tasks}
        nodes = set(task_map.keys())
        triggered_tasks = set()
        processed_nodes: Deque[Node] = deque()
        returned_values: Deque[Union[Any, NodeProcessException]] = deque()
        error_flag: bool = False

        loop = asyncio.get_event_loop()

        for node in self.navigate(nodes, direction, processed_nodes):
            # new node is available to be processed, so
            # add it to the task set
            if isinstance(node, Node):
                coroutine = task_map.get(node, None)
                # if cancellation has been flagged, then
                # don't schedule any extra task
                if coroutine and not self._canceled:
                    triggered_tasks.add(loop.create_task(coroutine()))

            # no more node processes to be scheduled, so
            # wait for current running tasks and process
            # the next completed one
            elif triggered_tasks:
                done, pending = await asyncio.wait(triggered_tasks, return_when=asyncio.FIRST_COMPLETED)
                for completed_task in done:
                    triggered_tasks.remove(completed_task)  # type: ignore
                    processed_node: Optional[Node] = None
                    try:
                        processed_node, coroutine_value = await completed_task
                    except NodeProcessException as ex:
                        error_flag = True
                        coroutine_value = ex

                        # when the error occurs, then we queue the exception
                        # instead of the regular return value from the task,
                        # if cancellation is not in place, to keep the tree
                        # going - we set the cancel state otherwise, so no
                        # further dependent nodes get scheduled
                        if cancel_on_error:
                            self.cancel()
                        else:
                            processed_node = ex.node
                    finally:
                        if processed_node:
                            processed_nodes.appendleft(processed_node)
                        returned_values.appendleft(coroutine_value)
            elif not processed_nodes:
                break

        self._canceled = False
        self._processing = False

        if error_flag:
            raise TreeProcessException(returned_values)

        return returned_values

    def get_nodes(self):
        return self.nodes.copy()

    def navigate(self, nodes: Set[Node], direction: NavigationDirection,
                 processed_nodes: Deque[Node]) -> Generator[Optional[Node], Node, bool]:

        if direction == NavigationDirection.LEAFS_TO_ROOTS:
            entrypoint = self.get_leafs()
        elif direction == NavigationDirection.ROOTS_TO_LEAFS:
            entrypoint = self.get_roots()
        else:
            raise TypeError("The provided argument `direction` is invalid.")

        from_direction, to_direction = direction.value
        next_nodes = deque(set(filter(lambda n: n in nodes, entrypoint)))

        while nodes or next_nodes:
            yield next_nodes.pop() if next_nodes else None
            processed = processed_nodes.pop() if processed_nodes else None

            if isinstance(processed, Node):
                if processed not in nodes:
                    return False
                nodes.remove(processed)

                nodes_to_direction = to_direction(processed) if processed else set()
                for node_to in nodes_to_direction:
                    nodes_from_direction = from_direction(node_to)
                    if not nodes_from_direction.intersection(nodes):
                        next_nodes.appendleft(node_to)
        return True

    def cancel(self):
        if self._processing:
            self._canceled = True


class DependencyGraph:
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
    def generate_from_objects(cls, objects: Set[BaseModel]) -> 'DependencyGraph':
        nodes: Set[Node] = cls._get_connected_nodes(objects)
        return cls.generate_from_nodes(nodes)

    @classmethod
    def generate_from_nodes(cls, nodes: Set[Node]) -> 'DependencyGraph':
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

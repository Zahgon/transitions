
from functools import partial
import itertools
from six import iteritems

from ..core import Machine, Transition

from .nesting import HierarchicalMachine, NestedEvent, NestedTransition
from .locking import LockedMachine
from .diagrams import GraphMachine, NestedGraphTransition, HierarchicalGraphMachine

try:
    from transitions.extensions.asyncio import AsyncMachine, AsyncTransition
    from transitions.extensions.asyncio import HierarchicalAsyncMachine, NestedAsyncTransition
except (ImportError, SyntaxError):  # pragma: no cover
    class AsyncMachine(Machine):  # type: ignore
        pass

    class AsyncTransition(Transition):  # type: ignore
        pass

    class HierarchicalAsyncMachine(HierarchicalMachine):  # type: ignore
        pass

    class NestedAsyncTransition(NestedTransition):  # type: ignore
        pass


class MachineFactory(object):

    @staticmethod
    def get_predefined(graph=False, nested=False, locked=False, asyncio=False):
        pass


class LockedHierarchicalMachine(LockedMachine, HierarchicalMachine):

    event_cls = NestedEvent

    def _get_qualified_state_name(self, state):
        return self.get_global_name(state.name)


class LockedGraphMachine(GraphMachine, LockedMachine):

    @staticmethod
    def format_references(func):
        if isinstance(func, partial) and func.func.__name__.startswith('_locked_method'):
            return "%s(%s)" % (
                func.args[0].__name__,
                ", ".join(itertools.chain(
                    (str(_) for _ in func.args[1:]),
                    ("%s=%s" % (key, value)
                     for key, value in iteritems(func.keywords if func.keywords else {})))))
        return GraphMachine.format_references(func)


class LockedHierarchicalGraphMachine(GraphMachine, LockedHierarchicalMachine):

    transition_cls = NestedGraphTransition
    event_cls = NestedEvent

    @staticmethod
    def format_references(func):
        return LockedGraphMachine.format_references(func)


class AsyncGraphMachine(GraphMachine, AsyncMachine):

    transition_cls = AsyncTransition


class HierarchicalAsyncGraphMachine(GraphMachine, HierarchicalAsyncMachine):

    transition_cls = NestedAsyncTransition


_CLASS_MAP = {
    (False, False, False, False): Machine,
    (False, False, True, False): LockedMachine,
    (False, True, False, False): HierarchicalMachine,
    (False, True, True, False): LockedHierarchicalMachine,
    (True, False, False, False): GraphMachine,
    (True, False, True, False): LockedGraphMachine,
    (True, True, False, False): HierarchicalGraphMachine,
    (True, True, True, False): LockedHierarchicalGraphMachine,
    (False, False, False, True): AsyncMachine,
    (True, False, False, True): AsyncGraphMachine,
    (False, True, False, True): HierarchicalAsyncMachine,
    (True, True, False, True): HierarchicalAsyncGraphMachine
}

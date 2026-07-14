
import logging
import warnings
from functools import partial

from transitions import Transition

from ..core import listify
from .markup import MarkupMachine, HierarchicalMarkupMachine
from .nesting import NestedTransition


_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


class TransitionGraphSupport(Transition):

    def __init__(self, *args, **kwargs):
        label = kwargs.pop("label", None)
        super(TransitionGraphSupport, self).__init__(*args, **kwargs)
        if label:
            self.label = label

    def _change_state(self, event_data):
        pass


class GraphMachine(MarkupMachine):

    _pickle_blacklist = ["model_graphs"]
    transition_cls = TransitionGraphSupport

    machine_attributes = {
        "directed": "true",
        "strict": "false",
        "rankdir": "LR",
    }

    style_attributes = {
        "node": {
            "default": {
                "style": "rounded,filled",
                "shape": "rectangle",
                "fillcolor": "white",
                "color": "black",
                "peripheries": "1",
            },
            "inactive": {"fillcolor": "white", "color": "black", "peripheries": "1"},
            "parallel": {
                "shape": "rectangle",
                "color": "black",
                "fillcolor": "white",
                "style": "dashed, rounded, filled",
                "peripheries": "1",
            },
            "active": {"color": "red", "fillcolor": "darksalmon", "peripheries": "2"},
            "previous": {"color": "blue", "fillcolor": "azure", "peripheries": "1"},
        },
        "edge": {"default": {"color": "black"}, "previous": {"color": "blue"}},
        "graph": {
            "default": {"color": "black", "fillcolor": "white", "style": "solid"},
            "previous": {"color": "blue", "fillcolor": "azure", "style": "filled"},
            "active": {"color": "red", "fillcolor": "darksalmon", "style": "filled"},
            "parallel": {"color": "black", "fillcolor": "white", "style": "dotted"},
        },
    }

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k not in self._pickle_blacklist}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.model_graphs = {}  # reinitialize new model_graphs
        for model in self.models:
            try:
                _ = self._get_graph(model)
            except AttributeError as err:
                _LOGGER.warning("Graph for model could not be initialized after pickling: %s", err)

    def __init__(self, model=MarkupMachine.self_literal, states=None, initial='initial', transitions=None,
                 send_event=False, auto_transitions=True,
                 ordered_transitions=False, ignore_invalid_triggers=None,
                 before_state_change=None, after_state_change=None, name=None,
                 queued=False, prepare_event=None, finalize_event=None, model_attribute='state', model_override=False,
                 on_exception=None, on_final=None, title="State Machine", show_conditions=False,
                 show_state_attributes=False, show_auto_transitions=False,
                 use_pygraphviz=True, graph_engine="pygraphviz", **kwargs):
        self.title = title
        self.show_conditions = show_conditions
        self.show_state_attributes = show_state_attributes
        kwargs["auto_transitions_markup"] = show_auto_transitions
        self.model_graphs = {}
        if use_pygraphviz is False:
            warnings.warn("Please replace 'use_pygraphviz=True' with graph_engine='graphviz'.",
                          category=DeprecationWarning)
            graph_engine = 'graphviz'
        self.graph_cls = self._init_graphviz_engine(graph_engine)

        _LOGGER.debug("Using graph engine %s", self.graph_cls)
        super(GraphMachine, self).__init__(
            model=model, states=states, initial=initial, transitions=transitions,
            send_event=send_event, auto_transitions=auto_transitions,
            ordered_transitions=ordered_transitions, ignore_invalid_triggers=ignore_invalid_triggers,
            before_state_change=before_state_change, after_state_change=after_state_change, name=name,
            queued=queued, prepare_event=prepare_event, finalize_event=finalize_event,
            model_attribute=model_attribute, model_override=model_override,
            on_exception=on_exception, on_final=on_final, **kwargs
        )

        if not hasattr(self, "get_graph"):
            setattr(self, "get_graph", self.get_combined_graph)

    def _init_graphviz_engine(self, graph_engine):
        pass

    def _get_graph(self, model, title=None, force_new=False, show_roi=False):
        pass

    def get_combined_graph(self, title=None, force_new=False, show_roi=False):
        pass

    def add_model(self, model, initial=None):
        models = listify(model)
        super(GraphMachine, self).add_model(models, initial)
        for mod in models:
            mod = self if mod is self.self_literal else mod
            if hasattr(mod, "get_graph"):
                raise AttributeError(
                    "Model already has a get_graph attribute. Graph retrieval cannot be bound."
                )
            setattr(mod, "get_graph", partial(self._get_graph, mod))
            _ = mod.get_graph(title=self.title, force_new=True)  # initialises graph

    def add_states(
        self, states, on_enter=None, on_exit=None, ignore_invalid_triggers=None, **kwargs
    ):
        pass

    def add_transition(self, trigger, source, dest, conditions=None, unless=None, before=None, after=None,
                       prepare=None, **kwargs):
        """Calls the base method and regenerates all models's graphs."""
        super(GraphMachine, self).add_transition(trigger, source, dest, conditions=conditions, unless=unless,
                                                 before=before, after=after, prepare=prepare, **kwargs)
        for model in self.models:
            model.get_graph(force_new=True)

    def remove_transition(self, trigger, source="*", dest="*"):
        pass


class NestedGraphTransition(TransitionGraphSupport, NestedTransition):
    pass


class HierarchicalGraphMachine(GraphMachine, HierarchicalMarkupMachine):

    transition_cls = NestedGraphTransition

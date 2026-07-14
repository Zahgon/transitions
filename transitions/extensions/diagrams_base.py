
import copy
import abc
import logging
import six

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


@six.add_metaclass(abc.ABCMeta)
class BaseGraph(object):

    def __init__(self, machine):
        self.machine = machine
        self.fsm_graph = None
        self.generate()

    @abc.abstractmethod
    def generate(self):
        """Triggers the generation of a graph."""

    @abc.abstractmethod
    def set_previous_transition(self, src, dst):
        """Sets the styling of an edge to 'previous'
        Args:
            src (str): Name of the source state
            dst (str): Name of the destination
        """

    @abc.abstractmethod
    def reset_styling(self):
        """Resets the styling of the currently generated graph."""

    @abc.abstractmethod
    def set_node_style(self, state, style):
        """Sets the style of nodes associated with a model state
        Args:
            state (str, Enum or list): Name of the state(s) or Enum(s)
            style (str): Name of the style
        """

    @abc.abstractmethod
    def get_graph(self, title=None, roi_state=None):
        """Returns a graph object.
        Args:
            title (str): Title of the generated graph
            roi_state (State): If not None, the returned graph will only contain edges and states connected to it.
        Returns:
             A graph instance with a `draw` that allows to render the graph.
        """

    def _convert_state_attributes(self, state):
        label = state.get("label", state["name"])
        if self.machine.show_state_attributes:
            if "tags" in state:
                label += " [" + ", ".join(state["tags"]) + "]"
            if "on_enter" in state:
                label += r"\l- enter:\l  + " + r"\l  + ".join(state["on_enter"])
            if "on_exit" in state:
                label += r"\l- exit:\l  + " + r"\l  + ".join(state["on_exit"])
            if "timeout" in state:
                label += r'\l- timeout(' + state['timeout'] + 's) -> (' + ', '.join(state['on_timeout']) + ')'
        return label + r"\l"

    def _get_state_names(self, state):
        pass

    def _transition_label(self, tran):
        edge_label = tran.get("label", tran["trigger"])
        if "dest" not in tran:
            edge_label += " [internal]"
        if self.machine.show_conditions and any(prop in tran for prop in ["conditions", "unless"]):
            edge_label = "{edge_label} [{conditions}]".format(
                edge_label=edge_label,
                conditions=" & ".join(
                    tran.get("conditions", []) + ["!" + u for u in tran.get("unless", [])]
                ),
            )
        return edge_label

    def _get_global_name(self, path):
        pass

    def _flatten(self, *lists):
        return (e for a in lists for e in
                (self._flatten(*a)
                 if isinstance(a, (tuple, list))
                 else (a.name if hasattr(a, 'name') else a,)))

    def _get_elements(self):
        states = []
        transitions = []
        try:
            markup = self.machine.get_markup_config()
            queue = [([], markup)]

            while queue:
                prefix, scope = queue.pop(0)
                for transition in scope.get("transitions", []):
                    if prefix:
                        tran = copy.copy(transition)
                        tran["source"] = self.machine.state_cls.separator.join(
                            prefix + [tran["source"]]
                        )
                        if "dest" in tran:  # don't do this for internal transitions
                            tran["dest"] = self.machine.state_cls.separator.join(
                                prefix + [tran["dest"]]
                            )
                    else:
                        tran = transition
                    transitions.append(tran)
                for state in scope.get("children", []) + scope.get("states", []):
                    if not prefix:
                        states.append(state)

                    ini = state.get("initial", [])
                    if not isinstance(ini, list):
                        ini = ini.name if hasattr(ini, "name") else ini
                        tran = dict(
                            trigger="",
                            source=self.machine.state_cls.separator.join(prefix + [state["name"]]),
                            dest=self.machine.state_cls.separator.join(
                                prefix + [state["name"], ini]
                            ),
                        )
                        transitions.append(tran)
                    if state.get("children", []):
                        queue.append((prefix + [state["name"]], state))
        except KeyError:
            _LOGGER.error("Graph creation incomplete!")
        return states, transitions

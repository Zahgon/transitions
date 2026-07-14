import copy
import logging
from functools import partial
from collections import defaultdict
from os.path import splitext

try:
    import graphviz as pgv
except ImportError:
    pgv = None

from .diagrams_base import BaseGraph

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


class Graph(BaseGraph):

    def __init__(self, machine):
        self.custom_styles = {}
        self.reset_styling()
        super(Graph, self).__init__(machine)

    def set_previous_transition(self, src, dst):
        pass

    def set_node_style(self, state, style):
        pass

    def reset_styling(self):
        pass

    def _add_nodes(self, states, container):
        for state in states:
            style = self.custom_styles["node"][state["name"]]
            container.node(
                state["name"],
                label=self._convert_state_attributes(state),
                **self.machine.style_attributes.get("node", {}).get(style, {})
            )

    def _add_edges(self, transitions, container):
        edge_labels = defaultdict(lambda: defaultdict(list))
        for transition in transitions:
            try:
                dst = transition["dest"]
            except KeyError:
                dst = transition["source"]
            edge_labels[transition["source"]][dst].append(self._transition_label(transition))
        for src, dests in edge_labels.items():
            for dst, labels in dests.items():
                style = self.custom_styles["edge"][src][dst]
                container.edge(
                    src,
                    dst,
                    label=" | ".join(labels),
                    **self.machine.style_attributes.get("edge", {}).get(style, {})
                )

    def generate(self):
        pass

    def get_graph(self, title=None, roi_state=None):
        title = title if title else self.machine.title

        fsm_graph = pgv.Digraph(
            name=title,
            node_attr=self.machine.style_attributes.get("node", {}).get("default", {}),
            edge_attr=self.machine.style_attributes.get("edge", {}).get("default", {}),
            graph_attr=self.machine.style_attributes.get("graph", {}).get("default", {}),
        )
        fsm_graph.graph_attr.update(**self.machine.machine_attributes)
        fsm_graph.graph_attr["label"] = title
        states, transitions = self._get_elements()
        if roi_state:
            active_states = set()
            sep = getattr(self.machine.state_cls, "separator", None)
            for state in self._flatten(roi_state):
                active_states.add(state)
                if sep:
                    state = sep.join(state.split(sep)[:-1])
                    while state:
                        active_states.add(state)
                        state = sep.join(state.split(sep)[:-1])
            transitions = [
                t
                for t in transitions
                if t["source"] in active_states or self.custom_styles["edge"][t["source"]][t["dest"]]
            ]
            active_states = active_states.union({
                t
                for trans in transitions
                for t in [trans["source"], trans.get("dest", trans["source"])]
            })
            active_states = active_states.union({k for k, style in self.custom_styles["node"].items() if style})
            states = filter_states(copy.deepcopy(states), active_states, self.machine.state_cls)
        self._add_nodes(states, fsm_graph)
        self._add_edges(transitions, fsm_graph)
        setattr(fsm_graph, "draw", partial(self.draw, fsm_graph))
        return fsm_graph

    def draw(self, graph, filename, format=None, prog="dot", args=""):
        pass


class NestedGraph(Graph):

    def __init__(self, *args, **kwargs):
        self._cluster_states = []
        super(NestedGraph, self).__init__(*args, **kwargs)

    def set_node_style(self, state, style):
        pass

    def set_previous_transition(self, src, dst):
        pass

    def _add_nodes(self, states, container):
        self._add_nested_nodes(states, container, prefix="", default_style="default")

    def _add_nested_nodes(self, states, container, prefix, default_style):
        for state in states:
            name = prefix + state["name"]
            label = self._convert_state_attributes(state)
            if state.get("children", None) is not None:
                cluster_name = "cluster_" + name
                attr = {"label": label, "rank": "source"}
                attr.update(
                    **self.machine.style_attributes.get("graph", {}).get(
                        self.custom_styles["node"][name] or default_style, {}
                    )
                )
                with container.subgraph(name=cluster_name, graph_attr=attr) as sub:
                    self._cluster_states.append(name)
                    is_parallel = isinstance(state.get("initial", ""), list)
                    with sub.subgraph(
                        name=cluster_name + "_root",
                        graph_attr={"label": "", "color": "None", "rank": "min"},
                    ) as root:
                        root.node(
                            name,
                            shape="point",
                            fillcolor="black",
                            width="0.0" if is_parallel else "0.1",
                        )
                    self._add_nested_nodes(
                        state["children"],
                        sub,
                        default_style="parallel" if is_parallel else "default",
                        prefix=prefix + state["name"] + self.machine.state_cls.separator,
                    )
            else:
                style = self.machine.style_attributes.get("node", {}).get(default_style, {}).copy()
                style.update(
                    self.machine.style_attributes.get("node", {}).get(
                        self.custom_styles["node"][name] or default_style, {}
                    )
                )
                container.node(name, label=label, **style)

    def _add_edges(self, transitions, container):
        edges_attr = defaultdict(lambda: defaultdict(dict))

        for transition in transitions:
            src = transition["source"]
            try:
                dst = transition["dest"]
            except KeyError:
                dst = src
            if edges_attr[src][dst]:
                attr = edges_attr[src][dst]
                attr[attr["label_pos"]] = " | ".join(
                    [edges_attr[src][dst][attr["label_pos"]], self._transition_label(transition)]
                )
            else:
                edges_attr[src][dst] = self._create_edge_attr(src, dst, transition)

        for custom_src, dests in self.custom_styles["edge"].items():
            for custom_dst, style in dests.items():
                if style and (
                    custom_src not in edges_attr or custom_dst not in edges_attr[custom_src]
                ):
                    edges_attr[custom_src][custom_dst] = self._create_edge_attr(
                        custom_src, custom_dst, {"trigger": "", "dest": ""}
                    )

        for src, dests in edges_attr.items():
            for dst, attr in dests.items():
                del attr["label_pos"]
                style = self.custom_styles["edge"][src][dst]
                attr.update(**self.machine.style_attributes.get("edge", {}).get(style, {}))
                container.edge(attr.pop("source"), attr.pop("dest"), **attr)

    def _create_edge_attr(self, src, dst, transition):
        label_pos = "label"
        attr = {}
        if src in self._cluster_states:
            attr["ltail"] = "cluster_" + src
            label_pos = "headlabel"
        src_name = src

        if dst in self._cluster_states:
            if not src.startswith(dst):
                attr["lhead"] = "cluster_" + dst
                label_pos = "taillabel" if label_pos.startswith("l") else "label"
        dst_name = dst

        if "ltail" in attr and dst_name.startswith(attr["ltail"][8:]):
            del attr["ltail"]

        attr[label_pos] = self._transition_label(transition)
        attr["label_pos"] = label_pos
        attr["source"] = src_name
        attr["dest"] = dst_name
        return attr


def filter_states(states, state_names, state_cls, prefix=None):
    prefix = prefix or []
    result = []
    for state in states:
        pref = prefix + [state["name"]]
        included = getattr(state_cls, "separator", "_").join(pref) in state_names
        if "children" in state:
            state["children"] = filter_states(
                state["children"], state_names, state_cls, prefix=pref
            )
            if state["children"] or included:
                result.append(state)
        elif included:
            result.append(state)
    return result

# -*- coding: utf-8 -*-

from collections import OrderedDict
import copy
from functools import partial, reduce
import inspect
import logging

try:
    from enum import Enum, EnumMeta
except ImportError:  # pragma: no cover
    class Enum:  # type: ignore
        pass

    class EnumMeta:  # type: ignore
        pass

from six import string_types

from ..core import State, Machine, Transition, Event, listify, MachineError, EventData

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


def _build_state_list(state_tree, separator, prefix=None):
    prefix = prefix or []
    res = []
    for key, value in state_tree.items():
        if value:
            res.append(_build_state_list(value, separator, prefix=prefix + [key]))
        else:
            res.append(separator.join(prefix + [key]))
    return res if len(res) > 1 else res[0]


def resolve_order(state_tree):
    pass


class FunctionWrapper(object):
    def __init__(self, func):
        """
        Args:
            func: Function to be called at the end of the path.
            path: If path is an empty string, assign function
        """
        self._func = func

    def add(self, func, path):
        """Assigns a `FunctionWrapper` as an attribute named like the next segment of the substates
            path.
        Args:
            func (callable): Function to be called at the end of the path.
            path (list of strings): Remaining segment of the substate path.
        """
        if not path:
            self._func = func
        else:
            name = path[0]
            if name[0].isdigit():
                name = 's' + name
            if hasattr(self, name):
                getattr(self, name).add(func, path[1:])
            else:
                assert not path[1:], "nested path should be empty"
                setattr(self, name, FunctionWrapper(func))

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)


class NestedEvent(Event):

    def trigger(self, model, *args, **kwargs):
        raise RuntimeError("NestedEvent.trigger must not be called directly. Call Machine.trigger_event instead.")

    def trigger_nested(self, event_data):
        pass

    def _process(self, event_data):
        pass


class NestedEventData(EventData):

    def __init__(self, state, event, machine, model, args, kwargs):
        super(NestedEventData, self).__init__(state, event, machine, model, args, kwargs)
        self.source_path = None
        self.source_name = None


class NestedState(State):

    separator = '_'
    u""" Separator between the names of parent and child states. In case '_' is required for
        naming state, this value can be set to other values such as '.' or even unicode characters
        such as '↦' (limited to Python 3 though).
    """

    dynamic_methods = State.dynamic_methods + ["on_final"]

    def __init__(self, name, on_enter=None, on_exit=None, ignore_invalid_triggers=None, final=False, initial=None,
                 on_final=None):
        super(NestedState, self).__init__(name=name, on_enter=on_enter, on_exit=on_exit,
                                          ignore_invalid_triggers=ignore_invalid_triggers, final=final)
        self.initial = initial
        self.events = {}
        self.states = OrderedDict()
        self.on_final = listify(on_final)
        self._scope = []

    def add_substate(self, state):
        pass

    def add_substates(self, states):
        pass

    def scoped_enter(self, event_data, scope=None):
        pass

    def scoped_exit(self, event_data, scope=None):
        pass

    @property
    def name(self):
        pass


class NestedTransition(Transition):

    def _resolve_transition(self, event_data):
        pass

    def _change_state(self, event_data):
        pass

    def _final_check(self, event_data, state_tree, enter_partials):
        pass

    def _final_check_nested(self, state, event_data, state_tree, enter_partials):
        pass

    def _enter_nested(self, root, dest, prefix_path, event_data):
        pass

    @staticmethod
    def _update_model(event_data, tree):
        pass

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for key, value in self.__dict__.items():
            if key in cls.dynamic_methods or key == "conditions":
                setattr(result, key, copy.copy(value))
            else:
                setattr(result, key, copy.deepcopy(value, memo))
        return result


class HierarchicalMachine(Machine):

    state_cls = NestedState
    transition_cls = NestedTransition
    event_cls = NestedEvent

    def __init__(self, model=Machine.self_literal, states=None, initial='initial', transitions=None,
                 send_event=False, auto_transitions=True,
                 ordered_transitions=False, ignore_invalid_triggers=None,
                 before_state_change=None, after_state_change=None, name=None,
                 queued=False, prepare_event=None, finalize_event=None, model_attribute='state',
                 model_override=False, on_exception=None, on_final=None, **kwargs):
        assert issubclass(self.state_cls, NestedState)
        assert issubclass(self.event_cls, NestedEvent)
        assert issubclass(self.transition_cls, NestedTransition)
        self._stack = []
        self.prefix_path = []
        self.scoped = self
        self._next_scope = None
        super(HierarchicalMachine, self).__init__(
            model=model, states=states, initial=initial, transitions=transitions,
            send_event=send_event, auto_transitions=auto_transitions,
            ordered_transitions=ordered_transitions, ignore_invalid_triggers=ignore_invalid_triggers,
            before_state_change=before_state_change, after_state_change=after_state_change, name=name,
            queued=queued, prepare_event=prepare_event, finalize_event=finalize_event, model_attribute=model_attribute,
            model_override=model_override, on_exception=on_exception, on_final=on_final, **kwargs
        )

    def __call__(self, to_scope=None):
        if isinstance(to_scope, Enum):
            state = self.states[to_scope.name]
            to_scope = (state, state.states, state.events, self.prefix_path + [to_scope.name])
        elif isinstance(to_scope, string_types):
            state_name = to_scope.split(self.state_cls.separator)[0]
            state = self.states[state_name]
            to_scope = (state, state.states, state.events, self.prefix_path + [state_name])
        elif to_scope is None:
            if self._stack:
                to_scope = self._stack[0]
            else:
                to_scope = (self, self.states, self.events, [])
        self._next_scope = to_scope

        return self

    def __enter__(self):
        self._stack.append((self.scoped, self.states, self.events, self.prefix_path))
        self.scoped, self.states, self.events, self.prefix_path = self._next_scope
        self._next_scope = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.scoped, self.states, self.events, self.prefix_path = self._stack.pop()

    def add_model(self, model, initial=None):
        """Extends transitions.core.Machine.add_model by applying a custom 'to' function to
            the added model.
        """
        models = [self if mod is self.self_literal else mod for mod in listify(model)]
        super(HierarchicalMachine, self).add_model(models, initial=initial)
        initial_name = getattr(models[0], self.model_attribute)
        if hasattr(initial_name, 'name'):
            initial_name = initial_name.name
        if isinstance(initial_name, string_types):
            initial_states = self._resolve_initial(models, initial_name.split(self.state_cls.separator))
        else:
            initial_states = initial_name
        for mod in models:
            self.set_state(initial_states, mod)
            if hasattr(mod, 'to'):
                _LOGGER.warning("%sModel already has a 'to'-method. It will NOT "
                                "be overwritten by NestedMachine", self.name)
            else:
                to_func = partial(self.to_state, mod)
                setattr(mod, 'to', to_func)

    @property
    def initial(self):
        pass

    @initial.setter
    def initial(self, value):
        pass

    def add_ordered_transitions(self, states=None, trigger='next_state',
                                loop=True, loop_includes_initial=True,
                                conditions=None, unless=None, before=None,
                                after=None, prepare=None, **kwargs):
        pass

    def add_states(self, states, on_enter=None, on_exit=None, ignore_invalid_triggers=None, **kwargs):
        pass

    def add_transition(self, trigger, source, dest, conditions=None,
                       unless=None, before=None, after=None, prepare=None, **kwargs):
        if source == self.wildcard_all and dest == self.wildcard_same:
            source = self.get_nested_state_names()
        else:
            if source != self.wildcard_all:
                source = [self.state_cls.separator.join(self._get_enum_path(s)) if isinstance(s, Enum) else s
                          for s in listify(source)]
            if dest != self.wildcard_same:
                dest = self.state_cls.separator.join(self._get_enum_path(dest)) if isinstance(dest, Enum) else dest
        super(HierarchicalMachine, self).add_transition(trigger, source, dest, conditions,
                                                        unless, before, after, prepare, **kwargs)

    def get_global_name(self, state=None, join=True):
        """Returns the name of the passed state in context of the current prefix/scope.
        Args:
            state (str, Enum or NestedState): The state to be analyzed.
            join (bool): Whether this method should join the path elements or not
        Returns:
            str or list(str) of the global state name
        """
        domains = copy.copy(self.prefix_path)
        if state:
            state_name = state.name if hasattr(state, 'name') else state
            if state_name in self.states:
                domains.append(state_name)
            else:
                raise ValueError("State '{0}' not found in local states.".format(state))
        return self.state_cls.separator.join(domains) if join else domains

    def get_nested_state_names(self):
        """Returns a list of global names of all states of a machine.
        Returns:
            list(str) of global state names.
        """
        ordered_states = []
        for state in self.states.values():
            ordered_states.append(self.get_global_name(state))
            with self(state.name):
                ordered_states.extend(self.get_nested_state_names())
        return ordered_states

    def get_nested_transitions(self, trigger="", src_path=None, dest_path=None):
        pass

    def get_nested_triggers(self, src_path=None):
        pass

    def get_state(self, state, hint=None):
        """Return the State instance with the passed name.
        Args:
            state (str, Enum or list(str)): A state name, enum or state path
            hint (list(str)): A state path to check for the state in question
        Returns:
            NestedState that belongs to the passed str (list) or Enum.
        """
        if isinstance(state, Enum):
            state = self._get_enum_path(state)
        elif isinstance(state, string_types):
            state = state.split(self.state_cls.separator)
        if not hint:
            state = copy.copy(state)
            hint = copy.copy(state)
        if len(state) > 1:
            child = state.pop(0)
            try:
                with self(child):
                    return self.get_state(state, hint)
            except (KeyError, ValueError):
                try:
                    with self():
                        state = self
                        for elem in hint:
                            state = state.states[elem]
                        return state
                except KeyError:
                    raise ValueError(
                        "State '%s' is not a registered state." % self.state_cls.separator.join(hint)
                    )  # from KeyError
        elif state[0] not in self.states:
            raise ValueError("State '%s' is not a registered state." % state)
        return self.states[state[0]]

    def get_states(self, states):
        pass

    def get_transitions(self, trigger="", source="*", dest="*", delegate=False):
        pass

    def _remove_nested_transitions(self, trigger, src_path, dest_path):
        pass

    def remove_transition(self, trigger, source="*", dest="*"):
        pass

    def _can_trigger(self, model, trigger, *args, **kwargs):
        pass

    def _can_trigger_nested(self, model, trigger, path, *args, **kwargs):
        pass

    def get_triggers(self, *args):
        pass

    def has_trigger(self, trigger, state=None):
        pass

    def is_state(self, state, model, allow_substates=False):
        pass

    def on_enter(self, state_name, callback):
        pass

    def on_exit(self, state_name, callback):
        pass

    def set_state(self, state, model=None):
        """Set the current state.
        Args:
            state (list of str or Enum or State): value of state(s) to be set
            model (optional[object]): targeted model; if not set, all models will be set to 'state'
        """
        values = [self._set_state(value) for value in listify(state)]
        models = self.models if model is None else listify(model)
        for mod in models:
            setattr(mod, self.model_attribute, values if len(values) > 1 else values[0])

    def to_state(self, model, state_name, *args, **kwargs):
        pass

    def trigger_event(self, model, trigger, *args, **kwargs):
        pass

    def _trigger_event(self, event_data, trigger):
        pass

    def _add_model_to_state(self, state, model):
        name = self.get_global_name(state)
        if self.state_cls.separator == '_':
            value = state.value if isinstance(state.value, Enum) else name
            self._checked_assignment(model, 'is_%s' % name, partial(self.is_state, value, model))
            for callback in self.state_cls.dynamic_methods:
                method = "{0}_{1}".format(callback, name)
                if hasattr(model, method) and inspect.ismethod(getattr(model, method)) and \
                        method not in getattr(state, callback):
                    state.add_callback(callback[3:], method)
        else:
            path = name.split(self.state_cls.separator)
            value = state.value if isinstance(state.value, Enum) else name
            trig_func = partial(self.is_state, value, model)
            if hasattr(model, 'is_' + path[0]):
                getattr(model, 'is_' + path[0]).add(trig_func, path[1:])
            elif len(path) == 1:
                self._checked_assignment(model, 'is_' + path[0], FunctionWrapper(trig_func))
        with self(state.name):
            for event in self.events.values():
                self._add_trigger_to_model(event.name, model)
            for a_state in self.states.values():
                self._add_model_to_state(a_state, model)

    def _add_dict_state(self, state, ignore_invalid_triggers, remap, **kwargs):
        pass

    def _add_enum_state(self, state, on_enter, on_exit, ignore_invalid_triggers, remap, **kwargs):
        pass

    def _add_machine_states(self, state, remap):
        pass

    def _add_string_state(self, state, on_enter, on_exit, ignore_invalid_triggers, remap, **kwargs):
        pass

    def _add_trigger_to_model(self, trigger, model):
        trig_func = partial(self.trigger_event, model, trigger)
        self._add_may_transition_func_for_trigger(trigger, model)
        if trigger.startswith('to_') and self.state_cls.separator != '_':
            path = trigger[3:].split(self.state_cls.separator)
            if hasattr(model, 'to_' + path[0]):
                getattr(model, 'to_' + path[0]).add(trig_func, path[1:])
            else:
                self._checked_assignment(model, 'to_' + path[0], FunctionWrapper(trig_func))
        else:
            self._checked_assignment(model, trigger, trig_func)

    def build_state_tree(self, model_states, separator, tree=None):
        pass

    def _get_enum_path(self, enum_state, prefix=None):
        prefix = prefix or []
        if enum_state.name in self.states and self.states[enum_state.name].value == enum_state:
            return prefix + [enum_state.name]
        for name in self.states:
            with self(name):
                res = self._get_enum_path(enum_state, prefix=prefix + [name])
                if res:
                    return res
        if not prefix:
            raise ValueError("Could not find path of {0}.".format(enum_state))
        return None

    def _get_state_path(self, state, prefix=None):
        pass

    def _check_event_result(self, res, model, trigger):
        pass

    def _get_trigger(self, model, trigger_name, *args, **kwargs):
        pass

    def _has_state(self, state, raise_error=False):
        """This function
        Args:
            state (NestedState): state to be tested
            raise_error (bool): whether ValueError should be raised when the state
                                is not registered
       Returns:
            bool: Whether state is registered in the machine
        Raises:
            ValueError: When raise_error is True and state is not registered
        """
        found = super(HierarchicalMachine, self)._has_state(state)
        if not found:
            for a_state in self.states:
                with self(a_state):
                    if self._has_state(state):
                        return True
        if not found and raise_error:
            msg = 'State %s has not been added to the machine' % (state.name if hasattr(state, 'name') else state)
            raise ValueError(msg)
        return found

    def _init_state(self, state):
        pass

    def _recursive_initial(self, value):
        pass

    def _remap_state(self, state, remap):
        pass

    def _resolve_initial(self, models, state_name_path, prefix=None):
        prefix = prefix or []
        if state_name_path:
            state_name = state_name_path.pop(0)
            with self(state_name):
                return self._resolve_initial(models, state_name_path, prefix=prefix + [state_name])
        if self.scoped.initial:
            entered_states = []
            for initial_state_name in listify(self.scoped.initial):
                with self(initial_state_name):
                    entered_states.append(self._resolve_initial(models, [], prefix=prefix + [self.scoped.name]))
            return entered_states if len(entered_states) > 1 else entered_states[0]
        return self.state_cls.separator.join(prefix)

    def _set_state(self, state_name):
        if isinstance(state_name, list):
            return [self._set_state(value) for value in state_name]
        a_state = self.get_state(state_name)
        return a_state.value if isinstance(a_state.value, Enum) else state_name

    def _trigger_event_nested(self, event_data, trigger, _state_tree):
        pass

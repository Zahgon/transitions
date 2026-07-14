
from functools import partial
import importlib
import itertools
import numbers

from six import string_types, iteritems

try:
    from enum import Enum, EnumMeta
except ImportError:  # pragma: no cover
    class Enum:  # type:ignore
        pass

    class EnumMeta:  # type:ignore
        pass

from ..core import Machine
from .nesting import HierarchicalMachine


class MarkupMachine(Machine):

    state_attributes = ['on_exit', 'on_enter', 'ignore_invalid_triggers', 'timeout', 'on_timeout', 'tags', 'label',
                        'final']
    transition_attributes = ['source', 'dest', 'prepare', 'before', 'after', 'label']

    def __init__(self, model=Machine.self_literal, states=None, initial='initial', transitions=None,
                 send_event=False, auto_transitions=True,
                 ordered_transitions=False, ignore_invalid_triggers=None,
                 before_state_change=None, after_state_change=None, name=None,
                 queued=False, prepare_event=None, finalize_event=None, model_attribute='state',
                 model_override=False, on_exception=None, on_final=None, markup=None, auto_transitions_markup=False,
                 **kwargs):
        self._markup = markup or {}
        self._auto_transitions_markup = auto_transitions_markup
        self._needs_update = True

        if self._markup:
            models = self._markup.pop('models', [])
            super(MarkupMachine, self).__init__(model=None, **self._markup)
            for mod in models:
                self._add_markup_model(mod)
        else:
            super(MarkupMachine, self).__init__(
                model=model, states=states, initial=initial, transitions=transitions,
                send_event=send_event, auto_transitions=auto_transitions,
                ordered_transitions=ordered_transitions, ignore_invalid_triggers=ignore_invalid_triggers,
                before_state_change=before_state_change, after_state_change=after_state_change, name=name,
                queued=queued, prepare_event=prepare_event, finalize_event=finalize_event,
                model_attribute=model_attribute, model_override=model_override,
                on_exception=on_exception, on_final=on_final, **kwargs
            )
            self._markup['before_state_change'] = [x for x in (rep(f) for f in self.before_state_change) if x]
            self._markup['after_state_change'] = [x for x in (rep(f) for f in self.before_state_change) if x]
            self._markup['prepare_event'] = [x for x in (rep(f) for f in self.prepare_event) if x]
            self._markup['finalize_event'] = [x for x in (rep(f) for f in self.finalize_event) if x]
            self._markup['on_exception'] = [x for x in (rep(f) for f in self.on_exception) if x]
            self._markup['on_final'] = [x for x in (rep(f) for f in self.on_final) if x]
            self._markup['send_event'] = self.send_event
            self._markup['auto_transitions'] = self.auto_transitions
            self._markup['model_attribute'] = self.model_attribute
            self._markup['model_override'] = self.model_override
            self._markup['ignore_invalid_triggers'] = self.ignore_invalid_triggers
            self._markup['queued'] = self.has_queue

    @property
    def auto_transitions_markup(self):
        pass

    @auto_transitions_markup.setter
    def auto_transitions_markup(self, value):
        pass

    @property
    def markup(self):
        pass

    def get_markup_config(self):
        """Generates and returns all machine markup parameters except models.
        Returns:
            dict of machine configuration parameters.
        """
        if self._needs_update:
            self._convert_states_and_transitions(self._markup)
            self._needs_update = False
        return self._markup

    def add_transition(self, trigger, source, dest, conditions=None,
                       unless=None, before=None, after=None, prepare=None, **kwargs):
        super(MarkupMachine, self).add_transition(trigger, source, dest, conditions=conditions, unless=unless,
                                                  before=before, after=after, prepare=prepare, **kwargs)
        self._needs_update = True

    def remove_transition(self, trigger, source="*", dest="*"):
        pass

    def add_states(self, states, on_enter=None, on_exit=None, ignore_invalid_triggers=None, **kwargs):
        pass

    @staticmethod
    def format_references(func):
        """Creates a string representation of referenced callbacks.
        Returns:
            str that represents a callback reference.
        """
        try:
            return func.__name__
        except AttributeError:
            pass
        if isinstance(func, partial):
            return "%s(%s)" % (
                func.func.__name__,
                ", ".join(itertools.chain(
                    (str(_) for _ in func.args),
                    ("%s=%s" % (key, value)
                     for key, value in iteritems(func.keywords if func.keywords else {})))))
        return str(func)

    def _convert_states_and_transitions(self, root):
        state = getattr(self, 'scoped', self)
        if state.initial:
            root['initial'] = state.initial
        if state == self and state.name:
            root['name'] = self.name[:-2]
        self._convert_transitions(root)
        self._convert_states(root)

    def _convert_states(self, root):
        key = 'states' if getattr(self, 'scoped', self) == self else 'children'
        root[key] = []
        for state_name, state in self.states.items():
            s_def = _convert(state, self.state_attributes, self.format_references)
            if isinstance(state_name, Enum):
                s_def['name'] = state_name.name
            else:
                s_def['name'] = state_name
            if getattr(state, 'states', []):
                with self(state_name):
                    self._convert_states_and_transitions(s_def)
            root[key].append(s_def)

    def _convert_transitions(self, root):
        root['transitions'] = []
        for event in self.events.values():
            if self._omit_auto_transitions(event):
                continue

            for transitions in event.transitions.items():
                for trans in transitions[1]:
                    t_def = _convert(trans, self.transition_attributes, self.format_references)
                    t_def['trigger'] = event.name
                    con = [x for x in (rep(f.func, self.format_references) for f in trans.conditions
                                       if f.target) if x]
                    unl = [x for x in (rep(f.func, self.format_references) for f in trans.conditions
                                       if not f.target) if x]
                    if con:
                        t_def['conditions'] = con
                    if unl:
                        t_def['unless'] = unl
                    root['transitions'].append(t_def)

    def _add_markup_model(self, markup):
        pass

    def _convert_models(self):
        pass

    def _omit_auto_transitions(self, event):
        return self.auto_transitions_markup is False and self._is_auto_transition(event)

    def _is_auto_transition(self, event):
        if event.name.startswith('to_') and len(event.transitions) == len(self.states):
            state_name = event.name[len('to_'):]
            try:
                _ = self.get_state(state_name)
                return True
            except ValueError:
                pass
        return False

    def _identify_callback(self, name):
        pass


class HierarchicalMarkupMachine(MarkupMachine, HierarchicalMachine):
    pass


def rep(func, format_references=None):
    """Return a string representation for `func`."""
    if isinstance(func, string_types):
        return func
    if isinstance(func, numbers.Number):
        return str(func)
    return format_references(func) if format_references is not None else None


def _convert(obj, attributes, format_references):
    definition = {}
    for key in attributes:
        val = getattr(obj, key, False)
        if not val:
            continue
        if isinstance(val, string_types):
            definition[key] = val
        elif val is True:
            definition[key] = True
        else:
            try:
                definition[key] = [rep(v, format_references) for v in iter(val)]
            except TypeError:
                definition[key] = rep(val, format_references)
    return definition

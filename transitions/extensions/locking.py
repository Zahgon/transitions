
from collections import defaultdict
from functools import partial
from threading import Lock
import inspect
import warnings
import logging

from transitions.core import Machine, Event, listify

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


try:
    from contextlib import nested  # Python 2
    from thread import get_ident  # pragma: no cover
    warnings.simplefilter('ignore', DeprecationWarning)  # pragma: no cover

except ImportError:
    from contextlib import ExitStack, contextmanager
    from threading import get_ident

    @contextmanager
    def nested(*contexts):
        pass


class PicklableLock:

    def __init__(self):
        self.lock = Lock()

    def __getstate__(self):
        return ''

    def __setstate__(self, value):
        return self.__init__()

    def __enter__(self):
        self.lock.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.__exit__(exc_type, exc_val, exc_tb)


class IdentManager:

    def __init__(self):
        self.current = 0

    def __enter__(self):
        self.current = get_ident()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.current = 0


class LockedEvent(Event):

    def trigger(self, model, *args, **kwargs):
        pass


class LockedMachine(Machine):

    event_cls = LockedEvent

    def __init__(self, model=Machine.self_literal, states=None, initial='initial', transitions=None,
                 send_event=False, auto_transitions=True,
                 ordered_transitions=False, ignore_invalid_triggers=None,
                 before_state_change=None, after_state_change=None, name=None,
                 queued=False, prepare_event=None, finalize_event=None, model_attribute='state',
                 model_override=False, on_exception=None, on_final=None,
                 machine_context=None, **kwargs):

        self._ident = IdentManager()
        self.machine_context = listify(machine_context) or [PicklableLock()]
        self.machine_context.append(self._ident)
        self.model_context_map = defaultdict(list)

        super(LockedMachine, self).__init__(
            model=model, states=states, initial=initial, transitions=transitions,
            send_event=send_event, auto_transitions=auto_transitions,
            ordered_transitions=ordered_transitions, ignore_invalid_triggers=ignore_invalid_triggers,
            before_state_change=before_state_change, after_state_change=after_state_change, name=name,
            queued=queued, prepare_event=prepare_event, finalize_event=finalize_event,
            model_attribute=model_attribute, model_override=model_override, on_exception=on_exception,
            on_final=on_final, **kwargs
        )

    def __getstate__(self):
        state = {k: v for k, v in self.__dict__.items()}
        del state['model_context_map']
        state['_model_context_map_store'] = {mod: self.model_context_map[id(mod)] for mod in self.models}
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.model_context_map = defaultdict(list)
        for model in self.models:
            self.model_context_map[id(model)] = self._model_context_map_store[model]
        del self._model_context_map_store

    def add_model(self, model, initial=None, model_context=None):
        """Extends `transitions.core.Machine.add_model` by `model_context` keyword.
        Args:
            model (list or object): A model (list) to be managed by the machine.
            initial (str, Enum or State): The initial state of the passed model[s].
            model_context (list or object): If passed, assign the context (list) to the machines
                model specific context map.
        """
        models = listify(model)
        model_context = listify(model_context) if model_context is not None else []
        super(LockedMachine, self).add_model(models, initial)

        for mod in models:
            mod = self if mod is self.self_literal else mod
            self.model_context_map[id(mod)].extend(self.machine_context)
            self.model_context_map[id(mod)].extend(model_context)

    def remove_model(self, model):
        pass

    def __getattribute__(self, item):
        get_attr = super(LockedMachine, self).__getattribute__
        tmp = get_attr(item)
        if not item.startswith('_') and inspect.ismethod(tmp):
            return partial(get_attr('_locked_method'), tmp)
        return tmp

    def __getattr__(self, item):
        try:
            return super(LockedMachine, self).__getattribute__(item)
        except AttributeError:
            return super(LockedMachine, self).__getattr__(item)

    def _add_model_to_state(self, state, model):
        super(LockedMachine, self)._add_model_to_state(state, model)  # pylint: disable=protected-access
        for prefix in self.state_cls.dynamic_methods:
            callback = "{0}_{1}".format(prefix, self._get_qualified_state_name(state))
            func = getattr(model, callback, None)
            if isinstance(func, partial) and func.func != state.add_callback:
                state.add_callback(prefix[3:], callback)

    def _get_qualified_state_name(self, state):
        return state.name

    def _locked_method(self, func, *args, **kwargs):
        pass



import logging
import asyncio
import contextvars
import inspect
import sys
import warnings
from collections import deque
from functools import partial, reduce
import copy

from ..core import State, Condition, Transition, EventData, listify
from ..core import Event, MachineError, Machine
from .nesting import HierarchicalMachine, NestedState, NestedEvent, NestedTransition, resolve_order


_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


CANCELLED_MSG = "_transition"
"""A message passed to a cancelled task to indicate that the cancellation was caused by transitions."""


class AsyncState(State):

    async def enter(self, event_data):
        pass

    async def exit(self, event_data):
        pass


class NestedAsyncState(NestedState, AsyncState):

    async def scoped_enter(self, event_data, scope=None):
        pass

    async def scoped_exit(self, event_data, scope=None):
        pass


class AsyncCondition(Condition):

    async def check(self, event_data):
        pass


class AsyncTransition(Transition):

    condition_cls = AsyncCondition

    async def _eval_conditions(self, event_data):
        pass

    async def execute(self, event_data):
        pass

    async def _change_state(self, event_data):
        pass


class NestedAsyncTransition(AsyncTransition, NestedTransition):
    async def _change_state(self, event_data):
        pass


class AsyncEventData(EventData):
    pass


class AsyncEvent(Event):

    async def trigger(self, model, *args, **kwargs):
        pass

    async def _trigger(self, event_data):
        pass

    async def _process(self, event_data):
        pass


class NestedAsyncEvent(NestedEvent):

    async def trigger_nested(self, event_data):
        pass

    async def _process(self, event_data):
        pass


class AsyncMachine(Machine):

    state_cls = AsyncState
    transition_cls = AsyncTransition
    event_cls = AsyncEvent
    async_tasks = {}
    protected_tasks = []
    current_context = contextvars.ContextVar('current_context', default=None)

    def __init__(self, model=Machine.self_literal, states=None, initial='initial', transitions=None,
                 send_event=False, auto_transitions=True,
                 ordered_transitions=False, ignore_invalid_triggers=None,
                 before_state_change=None, after_state_change=None, name=None,
                 queued=False, prepare_event=None, finalize_event=None, model_attribute='state',
                 model_override=False, on_exception=None, on_final=None, **kwargs):

        super().__init__(model=None, states=states, initial=initial, transitions=transitions,
                         send_event=send_event, auto_transitions=auto_transitions,
                         ordered_transitions=ordered_transitions, ignore_invalid_triggers=ignore_invalid_triggers,
                         before_state_change=before_state_change, after_state_change=after_state_change, name=name,
                         queued=bool(queued), prepare_event=prepare_event, finalize_event=finalize_event,
                         model_attribute=model_attribute, model_override=model_override,
                         on_exception=on_exception, on_final=on_final, **kwargs)

        self._transition_queue_dict = _DictionaryMock(self._transition_queue) if queued is True else {}
        self._queued = queued
        for model in listify(model):
            self.add_model(model)

    def add_model(self, model, initial=None):
        super().add_model(model, initial)
        if self.has_queue == 'model':
            for mod in listify(model):
                self._transition_queue_dict[id(self) if mod is self.self_literal else id(mod)] = deque()

    async def dispatch(self, trigger, *args, **kwargs):
        pass

    async def callbacks(self, funcs, event_data):
        pass

    async def callback(self, func, event_data):
        pass

    @staticmethod
    async def await_all(callables):
        pass

    async def switch_model_context(self, model):
        pass

    async def cancel_running_transitions(self, model, msg=None):
        pass

    async def process_context(self, func, model):
        pass

    def remove_model(self, model):
        pass

    async def _can_trigger(self, model, trigger, *args, **kwargs):
        pass

    def _process(self, trigger):
        raise RuntimeError("AsyncMachine should not call `Machine._process`. Use `Machine._process_async` instead.")

    async def _process_async(self, trigger, model):
        pass


class HierarchicalAsyncMachine(HierarchicalMachine, AsyncMachine):

    state_cls = NestedAsyncState
    transition_cls = NestedAsyncTransition
    event_cls = NestedAsyncEvent

    async def trigger_event(self, model, trigger, *args, **kwargs):
        pass

    async def _trigger_event(self, event_data, trigger):
        pass

    async def _trigger_event_nested(self, event_data, _trigger, _state_tree):
        pass

    async def _can_trigger(self, model, trigger, *args, **kwargs):
        pass

    async def _can_trigger_nested(self, model, trigger, path, *args, **kwargs):
        pass


class AsyncTimeout(AsyncState):

    dynamic_methods = ["on_timeout"]

    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contain 'timeout', assign the float value to
                self.timeout. If timeout is set, 'on_timeout' needs to be
                passed with kwargs as well or an AttributeError will be thrown
                if timeout is not passed or equal 0.
        """
        self.timeout = kwargs.pop("timeout", 0)
        self._on_timeout = None
        if self.timeout > 0:
            try:
                self.on_timeout = kwargs.pop("on_timeout")
            except KeyError:
                raise AttributeError("Timeout state requires 'on_timeout' when timeout is set.") from None
        else:
            self.on_timeout = kwargs.pop("on_timeout", None)
        self.runner = {}
        super().__init__(*args, **kwargs)

    async def enter(self, event_data):
        pass

    async def exit(self, event_data):
        pass

    def create_timer(self, event_data):
        pass

    async def _process_timeout(self, event_data):
        pass

    @property
    def on_timeout(self):
        pass

    @on_timeout.setter
    def on_timeout(self, value):
        pass


class _DictionaryMock(dict):

    def __init__(self, item):
        super().__init__()
        self._value = item

    def __setitem__(self, key, item):
        self._value = item

    def __getitem__(self, key):
        return self._value

    def __repr__(self):
        return repr("{{'*': {0}}}".format(self._value))

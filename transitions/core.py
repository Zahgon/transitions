

try:
    from builtins import object
except ImportError:  # pragma: no cover
    pass

try:
    from enum import Enum, EnumMeta
except ImportError:  # pragma: no cover
    class Enum:  # type:ignore
        pass

    class EnumMeta:  # type:ignore
        pass

import inspect
import itertools
import logging
import warnings

from collections import OrderedDict, defaultdict, deque
from functools import partial
from six import string_types

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())

warnings.filterwarnings(action='default', message=r".*transitions version.*", category=DeprecationWarning)


def listify(obj):
    """Wraps a passed object into a list in case it has not been a list, tuple before.
    Returns an empty list in case ``obj`` is None.
    Args:
        obj: instance to be converted into a list.
    Returns:
        list: May also return a tuple in case ``obj`` has been a tuple before.
    """
    if obj is None:
        return []

    try:
        return obj if isinstance(obj, (list, tuple, EnumMeta)) else [obj]
    except ReferenceError:
        return [obj]


def _prep_ordered_arg(desired_length, arguments=None):
    """Ensure list of arguments passed to add_ordered_transitions has the proper length.
    Expands the given arguments and apply same condition, callback
    to all transitions if only one has been given.

    Args:
        desired_length (int): The size of the resulting list
        arguments (optional[str, reference or list]): Parameters to be expanded.
    Returns:
        list: Parameter sets with the desired length.
    """
    arguments = listify(arguments) if arguments is not None else [None]
    if len(arguments) != desired_length and len(arguments) != 1:
        raise ValueError("Argument length must be either 1 or the same length as "
                         "the number of transitions.")
    if len(arguments) == 1:
        return arguments * desired_length
    return arguments


class State(object):

    dynamic_methods = ['on_enter', 'on_exit']

    def __init__(self, name, on_enter=None, on_exit=None,
                 ignore_invalid_triggers=None, final=False):
        """
        Args:
            name (str or Enum): The name of the state
            on_enter (str or list): Optional callable(s) to trigger when a
                state is entered. Can be either a string providing the name of
                a callable, or a list of strings.
            on_exit (str or list): Optional callable(s) to trigger when a
                state is exited. Can be either a string providing the name of a
                callable, or a list of strings.
            ignore_invalid_triggers (Boolean): Optional flag to indicate if
                unhandled/invalid triggers should raise an exception

        """
        self._name = name
        self.final = final
        self.ignore_invalid_triggers = ignore_invalid_triggers
        self.on_enter = listify(on_enter) if on_enter else []
        self.on_exit = listify(on_exit) if on_exit else []

    @property
    def name(self):
        pass

    @property
    def value(self):
        pass

    def enter(self, event_data):
        pass

    def exit(self, event_data):
        pass

    def add_callback(self, trigger, func):
        """Add a new enter or exit callback.
        Args:
            trigger (str): The type of triggering event. Must be one of
                'enter' or 'exit'.
            func (str): The name of the callback function.
        """
        callback_list = getattr(self, 'on_' + trigger)
        callback_list.append(func)

    def __repr__(self):
        return "<%s('%s')@%s>" % (type(self).__name__, self.name, id(self))


class Condition(object):

    def __init__(self, func, target=True):
        """
        Args:
            func (str or callable): Name of the condition-checking callable
            target (bool): Indicates the target state--i.e., when True,
                the condition-checking callback should return True to pass,
                and when False, the callback should return False to pass.
        Notes:
            This class should not be initialized or called from outside a
            Transition instance, and exists at module level (rather than
            nesting under the transition class) only because of a bug in
            dill that prevents serialization under Python 2.7.
        """
        self.func = func
        self.target = target

    def check(self, event_data):
        pass

    def __repr__(self):
        return "<%s(%s)@%s>" % (type(self).__name__, self.func, id(self))


class Transition(object):

    dynamic_methods = ['before', 'after', 'prepare']
    """ A list of dynamic methods which can be resolved by a ``Machine`` instance for convenience functions. """
    condition_cls = Condition
    """ The class used to wrap condition checks. Can be replaced to alter condition resolution behaviour
        (e.g. OR instead of AND for 'conditions' or AND instead of OR for 'unless') """

    def __init__(self, source, dest, conditions=None, unless=None, before=None,
                 after=None, prepare=None):
        """
        Args:
            source (str): The name of the source State.
            dest (str): The name of the destination State.
            conditions (optional[str, callable or list]): Condition(s) that must pass in order for
                the transition to take place. Either a string providing the
                name of a callable, or a list of callables. For the transition
                to occur, ALL callables must return True.
            unless (optional[str, callable or list]): Condition(s) that must return False in order
                for the transition to occur. Behaves just like conditions arg
                otherwise.
            before (optional[str, callable or list]): callbacks to trigger before the
                transition.
            after (optional[str, callable or list]): callbacks to trigger after the transition.
            prepare (optional[str, callable or list]): callbacks to trigger before conditions are checked
        """
        self.source = source
        self.dest = dest
        self.prepare = [] if prepare is None else listify(prepare)
        self.before = [] if before is None else listify(before)
        self.after = [] if after is None else listify(after)

        self.conditions = []
        if conditions is not None:
            for cond in listify(conditions):
                self.conditions.append(self.condition_cls(cond))
        if unless is not None:
            for cond in listify(unless):
                self.conditions.append(self.condition_cls(cond, target=False))

    def _eval_conditions(self, event_data):
        pass

    def execute(self, event_data):
        pass

    def _change_state(self, event_data):
        pass

    def add_callback(self, trigger, func):
        """Add a new before, after, or prepare callback.
        Args:
            trigger (str): The type of triggering event. Must be one of
                'before', 'after' or 'prepare'.
            func (str or callable): The name of the callback function or a callable.
        """
        callback_list = getattr(self, trigger)
        callback_list.append(func)

    def __repr__(self):
        return "<%s('%s', '%s')@%s>" % (type(self).__name__,
                                        self.source, self.dest, id(self))


class EventData(object):

    def __init__(self, state, event, machine, model, args, kwargs):
        """
        Args:
            state (State): The State from which the Event was triggered.
            event (Event): The triggering Event.
            machine (Machine): The current Machine instance.
            model (object): The model/object the machine is bound to.
            args (tuple): Optional positional arguments from trigger method
                to store internally for possible later use.
            kwargs (dict): Optional keyword arguments from trigger method
                to store internally for possible later use.
        """
        self.state = state
        self.event = event
        self.machine = machine
        self.model = model
        self.args = args
        self.kwargs = kwargs
        self.transition = None
        self.error = None
        self.result = False

    def update(self, state):
        """Updates the EventData object with the passed state.

        Attributes:
            state (State, str or Enum): The state object, enum member or string to assign to EventData.
        """

        if not isinstance(state, State):
            self.state = self.machine.get_state(state)

    def __repr__(self):
        return "<%s(%s, %s, %s)@%s>" % (type(self).__name__, self.event, self.state,
                                        getattr(self, 'transition'), id(self))


class Event(object):

    def __init__(self, name, machine):
        """
        Args:
            name (str): The name of the event, which is also the name of the
                triggering callable (e.g., 'advance' implies an advance()
                method).
            machine (Machine): The current Machine instance.
        """
        self.name = name
        self.machine = machine
        self.transitions = defaultdict(list)

    def add_transition(self, transition):
        """Add a transition to the list of potential transitions.
        Args:
            transition (Transition): The Transition instance to add to the
                list.
        """
        self.transitions[transition.source].append(transition)

    def trigger(self, model, *args, **kwargs):
        pass

    def _trigger(self, event_data):
        pass

    def _process(self, event_data):
        pass

    def _is_valid_source(self, state):
        pass

    def __repr__(self):
        return "<%s('%s')@%s>" % (type(self).__name__, self.name, id(self))

    def add_callback(self, trigger, func):
        """Add a new before or after callback to all available transitions.
        Args:
            trigger (str): The type of triggering event. Must be one of
                'before', 'after' or 'prepare'.
            func (str): The name of the callback function.
        """
        for trans in itertools.chain(*self.transitions.values()):
            trans.add_callback(trigger, func)


class Machine(object):

    separator = '_'  # separates callback type from state/transition name
    wildcard_all = '*'  # will be expanded to ALL states
    wildcard_same = '='  # will be expanded to source state
    state_cls = State
    transition_cls = Transition
    event_cls = Event
    self_literal = 'self'

    def __init__(self, model=self_literal, states=None, initial='initial', transitions=None,
                 send_event=False, auto_transitions=True,
                 ordered_transitions=False, ignore_invalid_triggers=None,
                 before_state_change=None, after_state_change=None, name=None,
                 queued=False, prepare_event=None, finalize_event=None, model_attribute='state', model_override=False,
                 on_exception=None, on_final=None, **kwargs):
        """
        Args:
            model (object or list): The object(s) whose states we want to manage. If set to `Machine.self_literal`
                (default value), the current Machine instance will be used as the model (i.e., all
                triggering events will be attached to the Machine itself). Note that an empty list
                is treated like no model.
            states (list or Enum): A list or enumeration of valid states. Each list element can be either a
                string, an enum member or a State instance. If string or enum member, a new generic State
                instance will be created that is named according to the string or enum member's name.
            initial (str, Enum or State): The initial state of the passed model[s].
            transitions (list): An optional list of transitions. Each element
                is a dictionary of named arguments to be passed onto the
                Transition initializer.
            send_event (boolean): When True, any arguments passed to trigger
                methods will be wrapped in an EventData object, allowing
                indirect and encapsulated access to data. When False, all
                positional and keyword arguments will be passed directly to all
                callback methods.
            auto_transitions (boolean): When True (default), every state will
                automatically have an associated to_{state}() convenience
                trigger in the base model.
            ordered_transitions (boolean): Convenience argument that calls
                add_ordered_transitions() at the end of initialization if set
                to True.
            ignore_invalid_triggers: when True, any calls to trigger methods
                that are not valid for the present state (e.g., calling an
                a_to_b() trigger when the current state is c) will be silently
                ignored rather than raising an invalid transition exception.
            before_state_change: A callable called on every change state before
                the transition happened. It receives the very same args as normal
                callbacks.
            after_state_change: A callable called on every change state after
                the transition happened. It receives the very same args as normal
                callbacks.
            name: If a name is set, it will be used as a prefix for logger output
            queued (boolean): When True, processes transitions sequentially. A trigger
                executed in a state callback function will be queued and executed later.
                Due to the nature of the queued processing, all transitions will
                _always_ return True since conditional checks cannot be conducted at queueing time.
            prepare_event: A callable called on for before possible transitions will be processed.
                It receives the very same args as normal callbacks.
            finalize_event: A callable called on for each triggered event after transitions have been processed.
                This is also called when a transition raises an exception.
            on_exception: A callable called when an event raises an exception. If not set,
                the exception will be raised instead.

            **kwargs additional arguments passed to next class in MRO. This can be ignored in most cases.
        """

        try:
            super(Machine, self).__init__(**kwargs)
        except TypeError as err:
            raise ValueError('Passing arguments {0} caused an inheritance error: {1}'.format(kwargs.keys(), err))

        self._queued = queued
        self._transition_queue = deque()
        self._before_state_change = []
        self._after_state_change = []
        self._prepare_event = []
        self._finalize_event = []
        self._on_exception = []
        self._on_final = []
        self._initial = None

        self.states = OrderedDict()
        self.events = OrderedDict()
        self.send_event = send_event
        self.auto_transitions = auto_transitions
        self.ignore_invalid_triggers = ignore_invalid_triggers
        self.prepare_event = prepare_event
        self.before_state_change = before_state_change
        self.after_state_change = after_state_change
        self.finalize_event = finalize_event
        self.on_exception = on_exception
        self.on_final = on_final
        self.name = name + ": " if name is not None else ""
        self.model_attribute = model_attribute
        self.model_override = model_override

        self.models = []

        if states is not None:
            self.add_states(states)

        if initial is not None:
            self.initial = initial

        if transitions is not None:
            self.add_transitions(transitions)

        if ordered_transitions:
            self.add_ordered_transitions()

        if model:
            self.add_model(model)

    def add_model(self, model, initial=None):
        """Register a model with the state machine, initializing triggers and callbacks."""
        models = listify(model)

        if initial is None:
            if self.initial is None:
                raise ValueError("No initial state configured for machine, must specify when adding model.")
            initial = self.initial

        for mod in models:
            mod = self if mod is self.self_literal else mod
            if mod not in self.models:
                self._checked_assignment(mod, 'trigger', partial(self._get_trigger, mod))
                self._checked_assignment(mod, 'may_trigger', partial(self._can_trigger, mod))

                for trigger in self.events:
                    self._add_trigger_to_model(trigger, mod)

                for state in self.states.values():
                    self._add_model_to_state(state, mod)

                self.set_state(initial, model=mod)
                self.models.append(mod)

    def remove_model(self, model):
        pass

    @classmethod
    def _create_transition(cls, *args, **kwargs):
        return cls.transition_cls(*args, **kwargs)

    @classmethod
    def _create_event(cls, *args, **kwargs):
        return cls.event_cls(*args, **kwargs)

    @classmethod
    def _create_state(cls, *args, **kwargs):
        pass

    @property
    def initial(self):
        pass

    @initial.setter
    def initial(self, value):
        pass

    @property
    def has_queue(self):
        pass

    @property
    def model(self):
        pass

    @property
    def before_state_change(self):
        pass

    @before_state_change.setter
    def before_state_change(self, value):
        pass

    @property
    def after_state_change(self):
        pass

    @after_state_change.setter
    def after_state_change(self, value):
        pass

    @property
    def prepare_event(self):
        pass

    @prepare_event.setter
    def prepare_event(self, value):
        pass

    @property
    def finalize_event(self):
        pass

    @finalize_event.setter
    def finalize_event(self, value):
        pass

    @property
    def on_exception(self):
        pass

    @on_exception.setter
    def on_exception(self, value):
        pass

    @property
    def on_final(self):
        pass

    @on_final.setter
    def on_final(self, value):
        pass

    def get_state(self, state):
        """Return the State instance with the passed name."""
        if isinstance(state, Enum):
            state = state.name
        if state not in self.states:
            raise ValueError("State '%s' is not a registered state." % state)
        return self.states[state]

    def is_state(self, state, model):
        pass

    def get_model_state(self, model):
        pass

    def set_state(self, state, model=None):
        """
            Set the current state.
        Args:
            state (str or Enum or State): value of state to be set
            model (optional[object]): targeted model; if not set, all models will be set to 'state'
        """
        if not isinstance(state, State):
            state = self.get_state(state)
        models = self.models if model is None else listify(model)

        for mod in models:
            setattr(mod, self.model_attribute, state.value)

    def add_state(self, states, on_enter=None, on_exit=None, ignore_invalid_triggers=None, **kwargs):
        pass

    def add_states(self, states, on_enter=None, on_exit=None,
                   ignore_invalid_triggers=None, **kwargs):
        pass

    def _add_model_to_state(self, state, model):

        func = partial(self.is_state, state.value, model)
        if self.model_attribute == 'state':
            method_name = 'is_%s' % state.name
        else:
            method_name = 'is_%s_%s' % (self.model_attribute, state.name)
        self._checked_assignment(model, method_name, func)

        for callback in self.state_cls.dynamic_methods:
            method = "{0}_{1}".format(callback, state.name)
            if hasattr(model, method) and inspect.ismethod(getattr(model, method)) and \
                    method not in getattr(state, callback):
                state.add_callback(callback[3:], method)

    def _checked_assignment(self, model, name, func):
        bound_func = getattr(model, name, None)
        if (bound_func is None) ^ self.model_override:
            setattr(model, name, func)
        else:
            _LOGGER.warning("%sSkip binding of '%s' to model due to model override policy.", self.name, name)

    def _can_trigger(self, model, trigger, *args, **kwargs):
        pass

    def _add_may_transition_func_for_trigger(self, trigger, model):
        self._checked_assignment(model, "may_%s" % trigger, partial(self._can_trigger, model, trigger))

    def _add_trigger_to_model(self, trigger, model):
        self._checked_assignment(model, trigger, partial(self.events[trigger].trigger, model))
        self._add_may_transition_func_for_trigger(trigger, model)

    def _get_trigger(self, model, trigger_name, *args, **kwargs):
        pass

    def get_triggers(self, *args):
        pass

    def add_transition(self, trigger, source, dest, conditions=None,
                       unless=None, before=None, after=None, prepare=None, **kwargs):
        """Create a new Transition instance and add it to the internal list.
        Args:
            trigger (str): The name of the method that will trigger the
                transition. This will be attached to the currently specified
                model (e.g., passing trigger='advance' will create a new
                advance() method in the model that triggers the transition.)
            source(str, Enum or list): The name of the source state--i.e., the state we
                are transitioning away from. This can be a single state, a
                list of states or an asterisk for all states.
            dest (str or Enum): The name of the destination State--i.e., the state
                we are transitioning into. This can be a single state or an
                equal sign to specify that the transition should be reflexive
                so that the destination will be the same as the source for
                every given source. If dest is None, this transition will be
                an internal transition (exit/enter callbacks won't be processed).
            conditions (str or list): Condition(s) that must pass in order
                for the transition to take place. Either a list providing the
                name of a callable, or a list of callables. For the transition
                to occur, ALL callables must return True.
            unless (str or list): Condition(s) that must return False in order
                for the transition to occur. Behaves just like conditions arg
                otherwise.
            before (str or list): Callables to call before the transition.
            after (str or list): Callables to call after the transition.
            prepare (str or list): Callables to call when the trigger is activated
            **kwargs: Additional arguments which can be passed to the created transition.
                This is useful if you plan to extend Machine.Transition and require more parameters.
        """
        if trigger == self.model_attribute:
            raise ValueError("Trigger name cannot be same as model attribute name.")
        if trigger not in self.events:
            self.events[trigger] = self._create_event(trigger, self)
            for model in self.models:
                self._add_trigger_to_model(trigger, model)

        if source == self.wildcard_all:
            source = list(self.states.keys())
        else:
            source = [s.name if isinstance(s, State) and self._has_state(s, raise_error=True) or hasattr(s, 'name') else
                      s for s in listify(source)]

        for state in source:
            if dest == self.wildcard_same:
                _dest = state
            elif dest is not None:
                if isinstance(dest, State):
                    _ = self._has_state(dest, raise_error=True)
                _dest = dest.name if hasattr(dest, 'name') else dest
            else:
                _dest = None
            _trans = self._create_transition(state, _dest, conditions, unless, before,
                                             after, prepare, **kwargs)
            self.events[trigger].add_transition(_trans)

    def add_transitions(self, transitions):
        """Add several transitions.

        Args:
            transitions (list): A list of transitions.

        """
        for trans in listify(transitions):
            if isinstance(trans, list):
                self.add_transition(*trans)
            else:
                self.add_transition(**trans)

    def add_ordered_transitions(self, states=None, trigger='next_state',
                                loop=True, loop_includes_initial=True,
                                conditions=None, unless=None, before=None,
                                after=None, prepare=None, **kwargs):
        pass

    def get_transitions(self, trigger="", source="*", dest="*"):
        pass

    def remove_transition(self, trigger, source="*", dest="*"):
        pass

    def dispatch(self, trigger, *args, **kwargs):
        pass

    def callbacks(self, funcs, event_data):
        pass

    def callback(self, func, event_data):
        pass

    @staticmethod
    def resolve_callable(func, event_data):
        pass

    def _has_state(self, state, raise_error=False):
        found = state in self.states.values()
        if not found and raise_error:
            msg = 'State %s has not been added to the machine' % (state.name if hasattr(state, 'name') else state)
            raise ValueError(msg)
        return found

    def _process(self, trigger):
        pass

    def _identify_callback(self, name):
        pass

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError("'{}' does not exist on <Machine@{}>"
                                 .format(name, id(self)))

        callback_type, target = self._identify_callback(name)

        if callback_type is not None:
            if callback_type in self.transition_cls.dynamic_methods:
                if target not in self.events:
                    raise AttributeError("event '{}' is not registered on <Machine@{}>"
                                         .format(target, id(self)))
                return partial(self.events[target].add_callback, callback_type)

            if callback_type in self.state_cls.dynamic_methods:
                state = self.get_state(target)
                return partial(state.add_callback, callback_type[3:])

        try:
            return self.__getattribute__(name)
        except AttributeError:
            raise AttributeError("'{}' does not exist on <Machine@{}>".format(name, id(self)))


class MachineError(Exception):

    def __init__(self, value):
        super(MachineError, self).__init__(value)
        self.value = value

    def __str__(self):
        return repr(self.value)

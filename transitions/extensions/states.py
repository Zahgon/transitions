
from collections import Counter
from threading import Timer
import logging
import inspect

from ..core import MachineError, listify, State

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())


class Tags(State):
    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contains `tags`, assign them to the attribute.
        """
        self.tags = kwargs.pop('tags', [])
        super(Tags, self).__init__(*args, **kwargs)

    def __getattr__(self, item):
        if item.startswith('is_'):
            return item[3:] in self.tags
        return super(Tags, self).__getattribute__(item)


class Error(Tags):

    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contains the keyword `accepted` add the 'accepted' tag to a tag list
                which will be forwarded to the Tags constructor.
        """
        tags = kwargs.get('tags', [])
        accepted = kwargs.pop('accepted', False)
        if accepted:
            tags.append('accepted')
            kwargs['tags'] = tags
        super(Error, self).__init__(*args, **kwargs)

    def enter(self, event_data):
        pass


class Timeout(State):

    dynamic_methods = ['on_timeout']

    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contain 'timeout', assign the float value to self.timeout. If timeout
                is set, 'on_timeout' needs to be passed with kwargs as well or an AttributeError will
                be thrown. If timeout is not passed or equal 0.
        """
        self.timeout = kwargs.pop('timeout', 0)
        self._on_timeout = None
        if self.timeout > 0:
            try:
                self.on_timeout = kwargs.pop('on_timeout')
            except KeyError:
                raise AttributeError("Timeout state requires 'on_timeout' when timeout is set.")  # from KeyError
        else:
            self._on_timeout = kwargs.pop('on_timeout', [])
        self.runner = {}
        super(Timeout, self).__init__(*args, **kwargs)

    def enter(self, event_data):
        pass

    def exit(self, event_data):
        pass

    def _process_timeout(self, event_data):
        pass

    @property
    def on_timeout(self):
        pass

    @on_timeout.setter
    def on_timeout(self, value):
        pass


class Volatile(State):

    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contains `volatile`, always create an instance of the passed class
                whenever the state is entered. The instance is assigned to a model attribute which
                can be passed with the kwargs keyword `hook`. If hook is not passed, the instance will
                be assigned to the 'attribute' scope. If `volatile` is not passed, an empty object will
                be assigned to the model's hook.
        """
        self.volatile_cls = kwargs.pop('volatile', VolatileObject)
        self.volatile_hook = kwargs.pop('hook', 'scope')
        super(Volatile, self).__init__(*args, **kwargs)
        self.initialized = True

    def enter(self, event_data):
        pass

    def exit(self, event_data):
        pass


class Retry(State):
    def __init__(self, *args, **kwargs):
        """
        Args:
            **kwargs: If kwargs contains `retries`, then limit the number of times
                the state may be re-entered from itself. The argument `on_failure`,
                which is the function to invoke on the model when the retry limit
                is exceeded, must also be provided.
        """
        self.retries = kwargs.pop('retries', 0)
        self.on_failure = kwargs.pop('on_failure', None)
        self.retry_counts = Counter()
        if self.retries > 0 and self.on_failure is None:
            raise AttributeError("Retry state requires 'on_failure' when "
                                 "'retries' is set.")
        super(Retry, self).__init__(*args, **kwargs)

    def enter(self, event_data):
        pass


def add_state_features(*args):
    """State feature decorator. Should be used in conjunction with a custom Machine class."""
    def _class_decorator(cls):
        pass
    return _class_decorator


class VolatileObject(object):
    pass

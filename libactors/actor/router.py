import inspect
import typing

from ..message import Message


def _func(self, context, message):
    pass  # pragma: no cover


MESSAGE_HANDLER_SIGNATURE = inspect.signature(_func)


class Router:
    """Router object that is used to map message to its handler.
    """
    def __init__(self):
        self._handlers = dict()
        self._handled_messages_names = dict()

    def match(self, message: Message) -> typing.Optional[typing.Callable]:
        """Finds the handler of the `message` class if any.

        Args:
            message (libactors.Message): The message to find its handler.

        Returns:
            typing.Optional[typing.Callable]: The handler if exists, otherwise, None.
        """
        return self._handlers.get(type(message))

    def get_message_cls(self, message_name: str) -> typing.Type[Message]:
        """Returns message class corresponding to `message_name`.

        Args:
            message_name (str): message class name

        Raises:
            KeyError: If no such message is registered.

        Returns:
            typing.Type[libactors.Message]: The class of the `message_name`.
        """
        if message_name not in self._handled_messages_names:
            raise KeyError(f'no handler for message: `{message_name}`')
        return self._handled_messages_names[message_name]

    def add(self, message_cls: typing.Type[Message], func: typing.Callable):
        """Add `func` as the handler of `message_cls` messages.

        Args:
            message_cls (typing.Type[libactors.Message]): Message class to assign `func` as a handler to.
            func (typing.Callable): Handler function.

        Raises:
            RuntimeError: If `message_cls` is not `libactors.Message`.
            RuntimeError: If `func` signature mismatch.
            RuntimeError: If `func` is not a coroutine.
            RuntimeError: If `message_cls` was already registered.
        """
        if not issubclass(message_cls, Message):
            raise RuntimeError(f'message class {message_cls} must inherit from Message {Message}')
        signature = inspect.signature(func)
        if signature._parameters.keys() != MESSAGE_HANDLER_SIGNATURE._parameters.keys():
            raise RuntimeError(
                f'signature for func: `{func}` must be: `{MESSAGE_HANDLER_SIGNATURE}`, not: `{signature}`'
            )
        if not inspect.iscoroutinefunction(func):
            raise RuntimeError(f'function: `{func}` must be async')
        if message_cls.__name__ in self._handled_messages_names:
            raise RuntimeError(f'handler for {message_cls} already exists')

        # Add class name to the mapping (for proxy syntactic sugar).
        self._handled_messages_names[message_cls.__name__] = message_cls
        # Add handler to the handlers mapping.
        self._handlers[message_cls] = func

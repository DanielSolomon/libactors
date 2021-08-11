import typing
import uuid

from ..context import Context
from ..message import (
    Message,
    Envelope,
)

from .actor import (
    Actor,
    EnvelopeTracker,
)

__pdoc__ = {
    'ActorProxy.__getattr__': True,
}


class ActorProxy:
    """Proxy object that is the interface for communicating with an underlying actor object.
    """
    def __init__(self, actor: Actor, actor_id: str):
        self._actor = actor
        self._actor_id = actor_id
        self._cache: typing.Dict[str, typing.Any] = {}

    def __repr__(self):
        return f'''{self.__class__.__name__}(
    actor_id    = {self._actor_id!r},
    actor       = {self._actor},
)'''

    @property
    def actor_id(self):
        return self._actor_id

    @property
    def actor_type(self):
        return type(self._actor)

    async def wait_until_initialized(self) -> None:
        """Awaits until the actor is initialized.
        If actor initialization has failed (raises), the exception will be raised in the callee context.
        """
        await self._actor.wait_until_initialized()

    async def wait_until_shutdown(self) -> None:
        """Awaits until the actor has shutdown.
        """
        await self._actor.wait_until_shutdown()

    def __getitem__(self, key: str):
        """Get cached value of key
        """
        return self._cache.__getitem__(key)

    def __setitem__(self, key: str, value: typing.Any):
        """Cache a key with value for messages.
        if a cached key appears as a message field, its value will be assigned automatically.

        Args:
            key (str): Key to cache.
            value (typing.Any): Value to cache.
        """
        return self._cache.__setitem__(key, value)

    def __delitem__(self, key: str):
        """Delete a cached key.
        """
        return self._cache.__delitem__(key)

    @property
    def initialized(self) -> bool:
        """Whether or not the internal actor is initialized

        Returns:
            bool: Initialized status.
        """
        return self._actor._initialize_event.is_set()

    # NOTE: Although current tell implementation does not require async, we keep it so we can change the undelying implementation in the future.
    async def tell(
        self,
        context: Context,
        message: Message,
        reply_to: typing.Optional[str] = None
    ) -> EnvelopeTracker:
        """Posts message to the internal actor queue.

        Args:
            context (libactors.Context): Context object.
            message (libactors.Message): Message to post.
            reply_to (str): Context identity, can be used to send reply to actor beside sender

        Returns:
            EnvelopeTracker: Envelope tracker to track message progress and its result.
        """
        envelope = Envelope(
            id=str(uuid.uuid4()),
            sender=context.identity,
            receiver=self._actor_id,
            reply_to=reply_to,
            message=message,
        )
        return self._actor.post(envelope)

    async def ask(self, context: Context, message: Message) -> typing.Any:
        """Posts a message to the internal actor and returns the response (sync message handling).

        Args:
            context (Context): Context object.
            message (Message): Message to post.

        Raises:
            RuntimeError: If message was not handled by the internal actor.

        Returns:
            typing.Any: Message handled result.
        """
        context.debug(f'{context.identity} asking actor {self._actor_id}, message: {message}')
        tracker = await self.tell(
            context=context,
            message=message,
        )
        context.debug(f'{context.identity} awaiting on tracker: {tracker}')
        result = await tracker
        if not tracker.is_handled:
            raise RuntimeError(
                f'actor: {self._actor_id} of type {type(self._actor)} did not handle message {type(message)}'
            )
        return result

    def __getattr__(self, func: str) -> typing.Callable:
        """Automagically send messages as function calls.
        instead of creating messages and send them using ask/tell, this allows the callee to send message by invoking functions:

        >>> await proxy.do_something(context, a=1, b='2') # is equivelant to:
        >>> await proxy.tell(context, DoSomething(a=1, b='2')) # DoSomething is a handled message by the internal actor

        Args:
            func (str): message to send, words separated by '_'.

        Returns:
            typing.Callable: A function that builds a message and send it (ask/tell).
        """
        message = ''.join(s.capitalize() for s in func.split('_'))
        message_cls = self._actor._router.get_message_cls(message)

        async def message_sender(context: Context, sync: bool = False, **kwargs):
            for key in message_cls.__dataclass_fields__.keys():
                if key not in kwargs and key in self._cache:
                    kwargs[key] = self._cache[key]
            message = message_cls(**kwargs)
            if sync:
                return await self.ask(context, message)
            else:
                return await self.tell(context, message)

        # Caching message sender.
        message_sender.__name__ = f'_proxy_auto_generated_{func}'
        self.__setattr__(func, message_sender)
        return message_sender

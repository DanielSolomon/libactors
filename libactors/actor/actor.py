import asyncio
import copy
import sentinels
import typing
import uuid


from .. import aio
from ..context import Context
from ..message import (
    Envelope,
    Message,
)

from .messages import (
    ShutdownMessage,
    TimerConfiguration,
    TimerDoneMessage,
    ActletDoneMessage,
)
from .router import Router

UNHANDLED = sentinels.Sentinel('unhandled')


class EnvelopeTracker:
    """Envelope tracker to track message processing progress.

    >>> envelope_tracker = proxy.tell(Message)
    >>> await envelope_tracker
    >>> # If we got here the actor has processed our message.
    """
    def __init__(self, envelope):
        self._envelope = envelope
        self._fut = asyncio.get_event_loop().create_future()

    def __repr__(self):
        return f'{self.__class__.__name__}(envelope={self._envelope})'

    def __await__(self):
        return self._fut.__await__()

    @property
    def is_handled(self):
        """Returns if the message was handled.
        Notice, a processed message that has no appropriate handler is considered as NOT handled.

        Returns:
            bool: Whether or not the message was handled.
        """
        return self._fut.result() is not UNHANDLED


class ActorMetaclass(type):
    """Actor metaclass for @register_handler decorator.
    """
    def __new__(cls, name, bases, dct):
        # First create the actor class.
        new_cls = super().__new__(cls, name, bases, dct)

        # Assign new actor object to the class.
        new_cls._router = Router()

        # Iterate all new created class methods, if a method has hidden '_handler' attribute add it to the router.
        for method in dct.values():
            if hasattr(method, '_handle'):
                new_cls._router.add(method._handle, method)
        # Iterate all base classes, if the base class has hidden '_router' field, any handled messages that are not handled here should be copied.
        for base in bases:
            if hasattr(base, '_router'):
                for message_cls, handler in base._router._handlers.items():
                    if message_cls not in new_cls._router._handlers:
                        new_cls._router.add(message_cls, handler)
        return new_cls


def register_handler(message_cls: typing.Type[Message]):
    """@register_handler decorator, it just marks the function with the hidden _handle attribute.
    Upon creation the actor collects it and register it in the router.

    Args:
        message_cls (typing.Type[Message]): The message class to register the decorated function as a handler to.
    """
    def decorator(func):
        func._handle = message_cls
        return func

    return decorator


class Actor(aio.service.Service, metaclass=ActorMetaclass):
    """The Actor.
    Worker that handles messages one at a time.
    """
    def __init_subclass__(cls, **kwargs):
        """Registering `cls` in the actors repository.
        """
        # Avoiding circular logs by lazy import.
        from ..core import ACTOR_REPOSITORY
        super().__init_subclass__(**kwargs)
        ACTOR_REPOSITORY.add(cls)

    def __init__(self, context: Context, actor_id: str):
        super().__init__()
        self._actor_id = actor_id
        self._context = context

        # Queue for handling incoming messages.
        self._queue = asyncio.Queue()

        # Event to signal that the actor is initialized
        self._initialize_event = asyncio.Event()
        self._initialize_exception = None

        # Event to signal that the actor has shutdown.
        self._shutdown_event = asyncio.Event()

        # Actor sub-actlets
        self._actlets = {}

    def __repr__(self):
        return f'{self.__class__.__name__}(context={self.context.__class__.__name__}, actor_id={self.actor_id})'

    @property
    def actor_id(self):
        return self._actor_id

    @property
    def context(self):
        return self._context

    async def initialize(self, context):
        """async __init__ function, should overriden by derived classes.
        """
        pass

    def post(self, envelope: Envelope) -> EnvelopeTracker:
        """Posts an envelope to this actor message queue.

        Args:
            envelope (libactors.Envelope): Envelope to post.

        Returns:
            EnvelopeTracker: Envelope tracker to track message progress and obtain the result.
        """
        # NOTE: envelope is deep copied since it might include references to internal state structures of actors.
        # After copying the message, the receiver actor may either access or modify any property safely.
        envelope = copy.deepcopy(envelope)
        tracker = EnvelopeTracker(envelope)
        self._queue.put_nowait((envelope, tracker))
        return tracker

    def tell_me(self, message: Message) -> EnvelopeTracker:
        """Posts message to self.

        Args:
            message (libactors.Message): Message to post.

        Returns:
            EnvelopeTracker: Envelope tracker to track message progress and obtain the result.
        """
        envelope = Envelope(
            id=str(uuid.uuid4()),
            sender=self.context.identity,
            receiver=self.context.identity,
            message=message,
        )
        return self.post(envelope)

    async def stop(self, context):
        context.info(f'stopping {self}')
        super().stop()

    @register_handler(ShutdownMessage)
    async def handle_shutdown(self, context, message):
        """Shutdown actor by stopping the service and canceling all active actlets.
        """
        await asyncio.gather(
            *[actlet.cancel() for actlet in self._actlets.values()],
            return_exceptions=True,
        )
        await self.stop(context)

    @register_handler(ActletDoneMessage)
    async def handle_actlet_done(self, context, message: ActletDoneMessage):
        context.debug(f'Actlet {context.sender} is done')
        if isinstance(message.result, Message):
            self.tell_me(message.result)
        del self._actlets[context.sender]

    @register_handler(TimerDoneMessage)
    async def handle_timer_done(self, context, message):
        """TimerDoneMessage handler, should be overridden by derived classes if relevant.
        """
        context.debug(f'Timer {context.sender} is done')

    async def wait_until_initialized(self) -> None:
        """Awaits until the actor is initialized.
        If actor initialization has failed (raises), the exception will be raised in the callee context.
        """
        await self._initialize_event.wait()
        if self._initialize_exception is not None:
            raise self._initialize_exception

    async def wait_until_shutdown(self) -> None:
        """Awaits until the actor has shutdown.
        """
        await self._shutdown_event.wait()

    def is_shutdown(self):
        return self._shutdown_event.is_set()

    async def serve(self):
        """Actor's infinite serving loop.

        * Initialize actor:
            o set as initialized.
        * Fetch messages from queue:
            o handle message if handler exists.
        """
        assert self.context is not None
        try:
            try:
                # Initialize actor.
                await self.initialize(self.context)
                # Finished initialization, setting event so all listeners would get notified.
                self._initialize_event.set()
            except Exception as e:
                self.context.exception(f'caught exception while initialized {self.actor_id}')
                # Finished initialization, setting event so all listeners would get notified.
                self._initialize_event.set()
                # Putting exception so anyone who gets notified will get it.
                self._initialize_exception = e
                raise

            waiter: aio.multiwaiter.MultiWaiter
            async with aio.multiwaiter.in_multi_waiter() as waiter:
                # Service stop event.
                waiter.add(self, lambda obj: obj.wait_stop())
                # Envelope event.
                waiter.add(self._queue, lambda obj: obj.get())

                while True:
                    self.context.debug('waiting for work')
                    await waiter.wait_first()

                    # Service is done
                    if waiter.done(self):
                        self.context.info('service was stopped')
                        break

                    # If we got here, we have an event in our queue.
                    envelope, tracker = waiter.result(self._queue)
                    self.context.debug(f'received envelope: {type(envelope.message)}')
                    # Fetching handler of message `envelope.message`.
                    handler = self._router.match(envelope.message)
                    if handler is None:
                        # If no handler we just mark the envelope tracker as unhandled.
                        self.context.warning(f'no handler for message: {type(envelope.message)}')
                        tracker._fut.set_result(UNHANDLED)
                        self._queue.task_done()
                        continue

                    try:
                        # Trying to handle the message.
                        self.context.debug(
                            f'handling envelope using handler {handler.__qualname__}'
                        )
                        result = await handler(
                            self, self.context(envelope=envelope), envelope.message
                        )
                        tracker._fut.set_result(result)
                    except Exception as e:
                        self.context.exception(
                            f'got an exception while handling envelope: {envelope}. exc: {e}'
                        )
                        tracker._fut.set_exception(e)
                    self._queue.task_done()
        finally:
            # cleanup
            self._shutdown_event.set()
            await self.context.core.remove_actor(self._actor_id)

    # NOTE: This async for future-proofing.
    async def create_actlet(
        self, context: Context, name: str, function: typing.Callable, configuration: Message
    ):
        """creates sub-actlet which runs the function in parallel to this actor's work.
        when done, the result is posted as a message to the actor

        Args:
            context (Context): Context object.
            name (str): Actlet's name.
            function (typing.Callable): Actlet's entrypoint function.
            configuration (Message): Actlet's configuration.

        Raises:
            RuntimeError: If there is an actlet named `name` already.

        Returns:
            libactors.actor.actlet: The created actlet object.
        """
        # Avoiding circular logs by lazy import.
        from .actlet import Actlet

        if self.is_actlet_exists(name):
            raise RuntimeError(f'actlet: {name} already exists')
        if hasattr(function, '__self__'):
            raise RuntimeError(f'actlet function: {function} must not be bound')

        name = self._generate_actlet_name(name)

        actlet = Actlet(
            name=name,
            context=context(identity=name),
            entry_point=function,
            # Actlet is created with proxy to the created actor.
            proxy=context.get_proxy(self.actor_id),
            # NOTE: configuration is deep copied since it might include references to internal state structures of actors.
            # After copying the configuration, the receiver actor may either access or modify any property safely.
            configuration=copy.deepcopy(configuration),
        )
        # Add the actlet to the mapping so the actor can keep track of all its actlets.
        self._actlets[name] = actlet
        return actlet

    async def cancel_actlet(self, context: Context, name: str):
        """Cancels the actlet named `name`.

        Args:
            context (Context): Context object.
            name (str): Actlet's name.
        """
        actlet_name = self._generate_actlet_name(name)
        await self._actlets[actlet_name].cancel()
        del self._actlets[actlet_name]

    @staticmethod
    async def _generic_timer(
        context: Context, proxy, configuration: TimerConfiguration
    ) -> TimerDoneMessage:
        """Generic timer function that sends a `configuration.message` every `configuration.interval` seconds.

        Args:
            context (libactors.Context): Context object.
            proxy (libactors.ActorProxy): Proxy to whom send `configuration.message`
            configuration (TimerConfiguration): Timer's configuration.

        Returns:
            TimerDoneMessage: Upon exception/completed all requested repetitions.
        """
        try:
            # If timer is delayed we wait now.
            if configuration.delay:
                await asyncio.sleep(configuration.delay)

            repetitions = configuration.repetitions if configuration.repetitions else float('inf')

            # If timer was configured with `now`, send message before counting down.
            if configuration.now:
                await proxy.tell(
                    context=context,
                    message=configuration.message,
                )
                # Altough it looks weird the repetitions is not on the waiting cycles, but on the amount of messages to send.
                repetitions -= 1

            while repetitions > 0:
                context.debug(f'sleeping {configuration.interval} seconds')
                # NOTE(gil): it is okay to use asyncio.sleep instead of asyncio.call_later or such (asyncio.sleep calls asyncio.call_later)
                await asyncio.sleep(configuration.interval)
                await proxy.tell(
                    context=context,
                    message=configuration.message,
                )
                repetitions -= 1
        except asyncio.CancelledError:
            raise
        except Exception as e:
            context.exception(f'exception in timer: {e}')
        return TimerDoneMessage()

    def _generate_actlet_name(self, name: str):
        return f'{self.context.identity}/actlet/{name}'

    def _generate_timer_name(self, name: str):
        return f'timer/{name}'

    async def create_timer(
        self,
        context: Context,
        name: str,
        message: Message,
        interval: float,
        delay: float = 0,
        now: bool = False,
        repetitions: int = 0
    ):
        """Creates a timer with name `name` (look for `libactors.actor.messages.TimerConfiguration` for full argument description).

        Args:
            context (Context): Context object.
            name (str): Timer's name.
            message (Message): Message to send.
            interval (float): Timer's interval.
            delay (float, optional): Timer's delay. Defaults to 0.
            now (bool, optional): Timer's now. Defaults to False.
            repetitions (int, optional): Timer's repetitions. Defaults to 0.
        """
        return await self.create_actlet(
            context=context,
            name=self._generate_timer_name(name),
            function=Actor._generic_timer,
            configuration=TimerConfiguration(
                message=message,
                interval=interval,
                delay=delay,
                now=now,
                repetitions=repetitions,
            ),
        )

    async def cancel_timer(self, context: Context, name: str):
        """Cancels the timer named `name`.

        Args:
            context (Context): Context object.
            name (str): Timer's name.
        """
        return await self.cancel_actlet(
            context=context,
            name=self._generate_timer_name(name),
        )

    def is_timer_exists(self, name: str) -> bool:
        """Checks if timer named `name` exists.

        Args:
            name (str): The timer name.

        Returns:
            bool: True iff timer named `name` exists.
        """
        return self.is_actlet_exists(self._generate_timer_name(name))

    def is_actlet_exists(self, name: str) -> bool:
        """Checks if actlet named `name` exists.

        Args:
            name (str): The actlet name.

        Returns:
            bool: True iff actlet named `name` exists.
        """
        return self._generate_actlet_name(name) in self._actlets

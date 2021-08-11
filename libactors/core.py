import asyncio
import pathlib
import typing


from . import log
from .actor import (
    Actor,
    ActorProxy,
    ShutdownMessage,
)
from .context import Context

logger = log.get_logger(__name__)

ACTOR_REPOSITORY: typing.Set[Actor] = set()

CORE_IDENTITY = '/'


class Core:
    """The libactors core, the core is resposible of:

    * Actors creation.
    * Actors lookup (returns `ActorProxy`).
    * System shutdown (shuts down all created actors).

    In most of the cases there will be only one `Core` in the system (it can be easily retrieved using the `get_core` function), but it is not enforced.
    """
    def __init__(self, context: typing.Optional[Context] = None):
        # NOTE: The context and the core are chicken-egg problem.
        # On one side, the core uses context for logging and resolving actor proxies.
        # On the other side, the core is accessible from the context so other actors will be able to ask their core stuff.
        # Therefore, usually the core will be initialized without a context.
        # After creating a context with that empty core it will be assigned to the core using the `set_context` function.
        self._actors = dict()
        self._lock = asyncio.Lock()
        self._running = True
        self._context = context

    @property
    def context(self) -> Context:
        return self._context

    def set_context(self, context):
        """Context setter for core (replaces current internal context).

        Args:
            context (libactors.Context): New context to set.
        """
        self._context = context

    def is_actor_type_exists(self, actor_cls: typing.Type[Actor]) -> bool:
        """Checks if actor of type `actor_cls` is already registered.

        Args:
            actor_cls (typing.Type[Actor]): Actor type to check if registered.

        Returns:
            bool: `True` iff `actor_cls` is registered.
        """
        return actor_cls in ACTOR_REPOSITORY

    def _generate_actor_id(self, base: str, actor_id: str):
        # NOTE: it will not work on windows, since path separator is not '/'.
        return str(pathlib.Path(base) / actor_id)

    def _assert_running(self, msg: str = 'Core is not running'):
        if not self._running:
            raise RuntimeError(msg)

    async def create_actor(
        self,
        callee_context: Context,
        actor_id: str,
        actor_cls: typing.Type[Actor],
        log_bindings: typing.Dict[str, typing.Any] = {},
        *args,
        **kwargs
    ) -> ActorProxy:
        """Creates an actor of type `actor_cls` with a given `actor_id` name.
        args and kwargs are passed directly to the internal actor `__init__` function.

        Args:
            callee_context (Context): Callee context to derive new context for the newborn actor.
            actor_id (str): Name of the newborn actor.
            actor_cls (typing.Type[libactors.Actor]): Type of the newborn actor.
            log_bindings (typing.Dict[str, typing.Any]): Log binding for derived context.

        Raises:
            RuntimeError: If `actor_id` already exists.

        Returns:
            ActorProxy: Actor proxy that wraps the newborn actor.
        """

        self._assert_running()

        actor_id = self._generate_actor_id(callee_context.identity, actor_id)

        self.context.info(f'creating actor: `{actor_cls}` with id: `{actor_id}`')
        async with self._lock:
            # Checking if core was shutdown.
            self._assert_running('core is no longer running')

            # Checking if `actor_id` already exists.
            if actor_id in self._actors:
                raise RuntimeError(f'actor {actor_id} already exists')

            # Creating actor and putting it in the internal actors mapping.
            actor = actor_cls(  # type: ignore
                # Derived context of the new created actor is expanded with new `log_bindings` and its new identity is set.
                context     = callee_context(identity=actor_id, **log_bindings),
                actor_id    = actor_id,
                *args,
                **kwargs
            )
            # The actor is saved in the private actors mapping.
            self._actors[actor_id] = actor

            # TODO: Understand Service in backend-common.
            # Starting actor (creates serve task internally)
            actor.start()  # TODO: for completeness who is in charge of shutdown.

            return ActorProxy(
                actor=actor,
                actor_id=actor_id,
            )

    async def remove_actor(self, actor_id: str):
        """Remove a shut-down actor

        Args:
            actor_id: ID of actor to remove

        Raises:
            RuntimeError if the core is not running
            ValueError if the Actor is not shut down
        """
        self._assert_running()

        if actor_id not in self._actors:
            self.context.warning(f'remove_actor failed: no actor with id: {actor_id}')
            return

        actor = self._actors[actor_id]
        if not actor.is_shutdown():
            raise ValueError('Actor {actor_id} is not shut down')

        del self._actors[actor_id]

    async def shutdown(self):
        """Shuts down the core:

        * Disable creating new actors.
        * Send shutdown message to all created actors.
        * Awaits until all actors are shutdown.
        """
        # NOTE: We need to acquire the lock just to make sure there is no inprogress actor creation.
        async with self._lock:
            self.context.info('shutting down')
            self._running = False

        proxies = [self.get_proxy(self.context, actor_id) for actor_id in self._actors]

        for proxy in proxies:
            await proxy.tell(
                context=self.context,
                message=ShutdownMessage(),
            )

        await asyncio.gather(
            *[proxy.wait_until_shutdown() for proxy in proxies],
            return_exceptions=True,
        )

    def get_proxy(self, callee_context: Context, actor_id: str) -> ActorProxy:
        """Get proxy of `actor_id` actor.

        Args:
            callee_context (Context): Context of the callee (`actor_id` will be concat to the callee derived identity).
            actor_id (str): The actor id to get proxy of.

        Raises:
            RuntimeError: If `actor_id` cannot be found.

        Returns:
            ActorProxy: The proxy of `actor_id`.
        """
        actor_id = self._generate_actor_id(callee_context.identity, actor_id)

        if actor_id not in self._actors:
            raise RuntimeError(f'actor: `{actor_id}` doesnt exist')
        return ActorProxy(
            actor=self._actors[actor_id],
            actor_id=actor_id,
        )

    @property
    def actors(self) -> typing.Dict[str, Actor]:
        """Created actors mapping (`actor_id` to `Actor`).

        Returns:
            typing.Dict[str, Actor]: created actors mapping.
        """
        return self._actors


_core = Core()


def get_core() -> Core:
    """System core getter.

    Returns:
        Core: The system core.
    """
    return _core

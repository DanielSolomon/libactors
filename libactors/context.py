import asyncio
import contextlib
import functools
import inspect
import typing

from .message import Envelope

# NOTE: This checking trick is because of the Core typing hint used by Context, if we will import it in runtime it will cause a cyclic import.
if typing.TYPE_CHECKING:
    from .core import Core  # pragma: no cover

__pdoc__ = {
    'Context.__call__': True
}


class Context:
    """Escorting object which encapsulate core and log access.
    It is recommend to inherit from this context object to expand its functionality for external services and utilities.
    """
    def __init__(
        self,
        core: 'Core',
        log,
        identity: str,
        envelope: typing.Optional[Envelope] = None,
        **kwargs
    ):
        """Context object to access the core, log and self identity.

        Args:
            core (libactors.Core): Core object.
            log: Logging-alike object.
            identity (str): context identity (usually actor's id).
            envelope (typing.Optional[libactors.Envelope], optional): Current processed evenlope if any. Defaults to None.

        Kwargs:
            Any key-word argument will be automatically bind to the log.
        """
        self._core = core
        self._log = log
        self._identity = identity
        self._envelope = envelope

        # Bind identity and other kwargs.
        if self._log:
            kwargs.update(identity=identity)
            self._log = self._log.bind(**kwargs)

    def __repr__(self):
        return f'''{self.__class__.__name__}(
    core        = {self._core},
    log         = {self._log},
    identity    = {self._identity!r},
    envelope    = {self._envelope},
)'''

    def __call__(self, *args, **kwargs) -> 'Context':
        """Derive new context from the existing one.

        Returns:
            libactors.Context: Derived context.
        """
        # TODO: buglet, we need to pass kwargs as well (for log bindings).
        # Each keyword is overriden if passed, otherwise we use the current value of this context.
        return Context(
            core=kwargs.get('core') or self._core,
            log=kwargs.get('log') or self._log,
            identity=kwargs.get('identity') or self._identity,
            envelope=kwargs.get('envelope') or self._envelope,
        )

    @contextlib.contextmanager
    def bind(self, **bindings):
        """Context manager for temporarty log bindings.

        Kwargs:
            Any key-word argument will be automatically bind to the log.
        """
        try:
            # Saving old bindings logger object to restore.
            old_log = self._log
            # Bind.
            self._log = self._log.bind(**bindings)
            yield
        finally:
            # Restore old logger with old bindings.
            self._log = old_log

    def bind_function(**bindings):
        """Decorator to use for temporary log bindings as long as the decorated function runs.
        The decorated function must have a context argument in its signature.

        >>> @Context.bind_function(foo='bar')
        ... async def function(self, context):
        ...     context.info('log')  # {'foo': 'bar', 'event': 'log'}
        """
        def _bound(func):
            def _get_context(func, *args, **kwargs):
                """Finds the value of the context argument in a function call.

                Raises:
                    RuntimeError: If `context` argument was not passed.
                """
                signature = inspect.signature(func)
                context = kwargs.get('context')
                if context is None:
                    try:
                        context = args[list(signature.parameters.keys()).index('context')]
                    except Exception:
                        raise RuntimeError('cannot bind contextless function')
                return context

            # The following two wrappers binds before calling the function (separated for coroutine and regular functions).
            @functools.wraps(func)
            async def awrapper(*args, **kwargs):
                with _get_context(func, *args, **kwargs).bind(**bindings):
                    return await func(*args, **kwargs)

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with _get_context(func, *args, **kwargs).bind(**bindings):
                    return func(*args, **kwargs)

            return awrapper if asyncio.iscoroutinefunction(func) else wrapper

        return _bound

    @property
    def core(self):
        """The internal core object.

        Returns:
            libactors.Core: The internal core object.
        """
        return self._core

    @property
    def log(self) -> typing.Callable:
        """The internal log function of the internal logger object.

        Returns:
            typing.Callable: The internal log function.
        """
        return self._log.log

    @property
    def envelope(self) -> typing.Optional[Envelope]:
        """Current handled envelope if any.

        Returns:
            typing.Optional[libactors.Envelope]: Current handled envelope or `None`.
        """
        return self._envelope

    @property
    def sender(self):
        return self._envelope.sender

    @property
    def identity(self):
        return self._identity

    @property
    def debug(self):
        """The internal debug function of the internal logger object.

        Returns:
            typing.Callable: The internal debug function.
        """
        return self._log.debug

    @property
    def info(self):
        """The internal info function of the internal logger object.

        Returns:
            typing.Callable: The internal info function.
        """
        return self._log.info

    @property
    def warning(self):
        """The internal warning function of the internal logger object.

        Returns:
            typing.Callable: The internal warning function.
        """
        return self._log.warning

    @property
    def error(self):
        """The internal error function of the internal logger object.

        Returns:
            typing.Callable: The internal error function.
        """
        return self._log.error

    @property
    def fatal(self):
        """The internal fatal function of the internal logger object.

        Returns:
            typing.Callable: The internal fatal function.
        """
        return self._log.fatal

    @property
    def exception(self):
        """The internal exception function of the internal logger object.

        Returns:
            typing.Callable: The internal exception function.
        """
        return self._log.exception

    async def create_actor(
        self,
        actor_id: str,
        actor_cls,
        log_bindings: typing.Dict[str, typing.Any] = {},
        *args,
        **kwargs
    ):
        """Creates an actor of type `actor_cls`.

        Args:
            actor_id (str): Name of the newborn actor (suffix).
            actor_cls (typing.Type[libactors.Actor]): Type of the newborn actor.
            log_bindings (typing.Dict[str, typing.Any], optional): Log binding for derived context. Defaults to {}.

        Returns:
            libactors.ActorProxy: Actor proxy that wraps the newborn actor.
        """
        return await self._core.create_actor(self, actor_id, actor_cls, *args, **kwargs)

    def get_proxy(self, actor_id: str):
        """Get proxy of `actor_id` actor.

        Args:
            actor_id (str): The actor id to get proxy of.

        Returns:
            libactors.ActorProxy: The proxy of `actor_id`.
        """
        return self._core.get_proxy(self, actor_id)

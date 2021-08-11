import asyncio
import inspect
import typing

from .messages import ActletDoneMessage
from ..context import Context
from ..message import Message

from .proxy import ActorProxy


def _func(context, proxy, configuration):
    pass  # pragma: no cover


ENTRY_POINT_SIGNATURE = inspect.signature(_func)


class Actlet:
    """Entity that runs in parallel to an actor, it is assigned with a task (function) which it solves.
    When finished it sends a message with the result back to its creator actor.
    """
    def __init__(
        self,
        context: Context,
        entry_point: typing.Callable,
        proxy: ActorProxy,
        configuration: Message,
        name: typing.Optional[str] = None
    ):
        signature = inspect.signature(entry_point)
        if signature._parameters.keys() != ENTRY_POINT_SIGNATURE._parameters.keys():
            raise RuntimeError(
                f'signature for entry_point: `{entry_point}` must be: `{ENTRY_POINT_SIGNATURE}`, not: `{signature}`'
            )
        if not asyncio.iscoroutinefunction(entry_point):
            raise RuntimeError(f'entry_point `{entry_point}` must be a coroutine function')

        if name is None:
            name = entry_point.__name__
        self._name = name
        self._context = context
        self._entry_point = entry_point
        self._proxy = proxy
        self._configuration = configuration

        self._task = asyncio.create_task(self._run())

    def __repr__(self):
        return f'''{self.__class__.__name__}(
    name            = {self._name!r},
    context         = {self._context},
    entry_point     = {self._entry_point},
    proxy           = {self._proxy},
    configuration   = {self._configuration},
)'''

    def __await__(self):
        return self._task.__await__()

    async def _run(self):
        # Assigning actlet.
        try:
            result = await self._entry_point(
                context=self._context,
                proxy=self._proxy,
                configuration=self._configuration,
            )
        except Exception:
            self._context.exception(f'an exception as occurred during actlet: {self}')
            # TODO: send exception result
            return

        # Sending actlet done message back to the commanding actor, encapsulating the result
        await self._proxy.tell(
            context=self._context,
            message=ActletDoneMessage(result=result),
        )

    # NOTE(gil): this is async for future-proofing
    async def cancel(self):
        self._task.cancel()

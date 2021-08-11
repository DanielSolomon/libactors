import asyncio
import contextlib
import dataclasses
import typing

from .exceptions import MultiWaiterNotDoneException, MultiWaiterKeyAlreadyExistsException


@dataclasses.dataclass
class Waiter:
    key: typing.Any
    factory: typing.Callable[[typing.Any], typing.Coroutine]
    waiter: typing.Optional[asyncio.Task] = None


class MultiWaiter:
    def __init__(self):
        self._objects: typing.Dict[typing.Any, Waiter] = {}
        self._tasks: typing.Dict[asyncio.Task, typing.Any] = {}

    def add(self, key, waiter_factory):
        if key in self._objects:
            raise MultiWaiterKeyAlreadyExistsException(f'key: {key} already exists')

        waiter = Waiter(key, waiter_factory)
        self._objects[key] = waiter

    async def reset(self, *keys):
        await self._run_waiters(recreate=True, keys=keys)

    async def cancel(self):
        cancelled = []
        for obj in self._objects.values():
            if obj.waiter is None:
                continue

            if not obj.waiter.done():
                obj.waiter.cancel()
                cancelled.append(obj.waiter)

        await asyncio.gather(*cancelled, return_exceptions=True)
        self._tasks.clear()

    async def wait_first(self) -> typing.Set[typing.Any]:
        # Run all objects.
        await self._run_waiters()

        # Wait for the first to complete
        done, _ = await asyncio.wait(
            [obj.waiter for obj in self._objects.values()],
            return_when=asyncio.FIRST_COMPLETED,
        )
        return {self._tasks[task]
                for task in done}

    def done(self, key):
        obj = self._objects[key]
        return obj.waiter is not None and obj.waiter.done()

    def exception(self, key):
        obj = self._objects[key]
        return obj.waiter is not None and obj.waiter.exception()

    def result(self, key):
        obj = self._objects[key]
        if obj.waiter is None or not obj.waiter.done():
            raise MultiWaiterNotDoneException('task is not done yet')

        return obj.waiter.result()

    async def _run_waiters(
        self,
        *,
        recreate: bool = False,
        keys: typing.Optional[typing.List[typing.Any]] = None,
    ):
        # If no keys are passed, we run all available keys.
        keys = set(keys) if keys else self._objects.keys()

        cancelled: typing.List[asyncio.Task] = []
        to_create: typing.List[Waiter] = []

        for obj in self._objects.values():
            if obj.key not in keys:
                continue

            # We cancel the task only if recreate is passed or task is done.
            if obj.waiter is not None and (obj.waiter.done() or recreate):
                obj.waiter.cancel()
                self._tasks.pop(obj.waiter)
                cancelled.append(obj.waiter)
                obj.waiter = None

            if obj.waiter is None:
                # Need to create a task for this obj.
                to_create.append(obj)

        if cancelled:
            await asyncio.gather(*cancelled, return_exceptions=True)

        for obj in to_create:
            obj.waiter = asyncio.create_task(obj.factory(obj.key))
            self._tasks[obj.waiter] = obj.key


@contextlib.asynccontextmanager
async def in_multi_waiter():
    multi_waiter = MultiWaiter()
    try:
        yield multi_waiter
    finally:
        await multi_waiter.cancel()

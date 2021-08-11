import asyncio
import logging
import typing

from .exceptions import ServiceException, ServiceStartupException

logger = logging.getLogger(__name__)

ServiceCallback = typing.Callable[['Service'], None]


class Service:
    def __init__(self):
        self._task: typing.Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._done_event: asyncio.Event = asyncio.Event()
        self._ready_event: asyncio.Event = asyncio.Event()
        self._done_callbacks: typing.List[ServiceCallback] = []
        self._stop_callbacks: typing.List[ServiceCallback] = []

    def start(self):
        if self.started:
            raise ServiceException(f'Service {self} already started')

        self._task = asyncio.ensure_future(self._service_worker())
        self._task.add_done_callback(self._on_worker_done)

    def stop(self):
        logger.info(f'Service {self} stop requested')

        for callback in self._stop_callbacks:
            asyncio.get_event_loop().call_soon(callback, self)

        self._mark_stopping()

    @property
    def stopping(self):
        return self._stop_event.is_set()

    @property
    def ready(self):
        return self._ready_event.is_set()

    @property
    def done(self):
        return self._done_event.is_set()

    @property
    def started(self):
        return self._task is not None

    def exception(self):
        if self._task is None:
            raise ServiceException(f'Service {self} not started')

        if not self._task.done():
            raise ServiceException(f'Service {self} not done')

        return self._task.exception()

    def add_stop_callback(self, callback: ServiceCallback):
        if self._stop_event.is_set():
            raise ServiceException(f'Service {self} already stopping')

        self._stop_callbacks.append(callback)

    def add_done_callback(self, callback: ServiceCallback):
        if self.started and self._task.done():
            raise ServiceException(f'Service {self} already done')

        self._done_callbacks.append(callback)

    async def wait(self):
        if self._task is None:
            raise ServiceException(f'Service {self} not started')

        await self._done_event.wait()

    async def wait_ready(self):
        if self._task is None:
            raise ServiceException(f'Service {self} not started')

        await self._ready_event.wait()

        if self._task is not None and self._task.done() and self._task.exception() is not None:
            raise ServiceStartupException()

    async def wait_stop(self):
        await self._stop_event.wait()

    async def setup(self):
        pass

    async def serve(self):
        await self.wait_stop()

    async def teardown(self):
        pass

    def _mark_ready(self):
        self._ready_event.set()

    def _mark_stopping(self):
        self._stop_event.set()

    def _mark_done(self):
        self._done_event.set()

    def _on_worker_done(self, task):
        logger.info(f'Service {self} completed')

        exc = task.exception()
        if exc is not None:
            logger.exception(f'Service {self} completed with failure', exc_info=exc)

        # Fail any ready waiters
        self._mark_ready()

        # Call callbacks
        for callback in self._done_callbacks:
            asyncio.get_event_loop().call_soon(callback, self)

        # Resolve done event.
        self._mark_done()

        # Resolve stopping event.
        self._mark_stopping()

    async def _service_worker(self):
        setup_called = False
        try:
            # Wait for the our service
            logger.info(f'Service {self} setting up')
            await self.setup()
            setup_called = True

            self._mark_ready()
            logger.info(f'Service {self} is serving')
            await self.serve()
        finally:
            if setup_called:
                logger.info(f'Service {self} tearing down')
                await self.teardown()

            logger.info(f'Service {self} stopping')

            # Mark as stopping
            self._mark_stopping()

import dataclasses
import pytest

import libactors
from libactors import log


@pytest.yield_fixture
async def core():
    c = libactors.Core()
    context = libactors.Context(
        core=c,
        log=log.get_logger(__name__),
        identity='/',
    )
    c.set_context(context)
    yield c
    await c.shutdown()


@pytest.fixture
def context(core):
    return core._context


@dataclasses.dataclass(frozen=True)
class DummyMessage(libactors.Message):
    pass


@dataclasses.dataclass(frozen=True)
class ErringMessage(libactors.Message):
    pass


@dataclasses.dataclass(frozen=True)
class DataMessage(libactors.Message):
    data: str


@dataclasses.dataclass(frozen=True)
class UnhandledMessage(libactors.Message):
    pass


class DummyActor(libactors.Actor):
    def __init__(self, context: libactors.Context, actor_id: str, *args, **kwargs):
        super().__init__(context, actor_id, *args, **kwargs)
        self._message_called = False

    async def initialize(self, context):
        pass

    @libactors.actor.register_handler(DummyMessage)
    async def dummy_message_handler(self, context, message):
        context.info(f'dummy_message_handler: {message}')
        self._message_called = True

    @libactors.actor.register_handler(ErringMessage)
    async def erring_message_handler(self, context, message):
        context.info(f'erring_message_handler: {message}')
        raise RuntimeError('exception')


class FoolishActor(libactors.Actor):
    async def initialize(self, context):
        raise RuntimeError('oh snap such a foolish actor')


class EchoActor(libactors.Actor):
    async def initialize(self, context):
        pass

    @libactors.actor.register_handler(DataMessage)
    async def data_message_handler(self, context, message):
        return message.data


class NotAnActor:
    async def initialize(self, context):
        pass

import conftest
import pytest

from libactors.actor.router import Router
from libactors.message import Message


async def handler(self, context, message):
    pass


class SomeMessage(Message):
    pass


def test_router_add():
    router = Router()
    router.add(SomeMessage, handler)
    assert router._handlers.get(SomeMessage) == handler


def test_double_message_handlers():
    router = Router()
    router.add(SomeMessage, handler)
    with pytest.raises(RuntimeError):
        router.add(SomeMessage, handler)


def test_no_handler_for_message():
    router = Router()
    assert router.match(SomeMessage) is None


def test_valid_handler_signature():
    router = Router()
    router.add(SomeMessage, handler)


def test_invalid_handler_signature():
    async def handler(self, context, message, var):
        pass

    router = Router()
    with pytest.raises(RuntimeError):
        router.add(SomeMessage, handler)


def test_non_async_handler():
    def handler(self, context, message):
        pass

    router = Router()
    with pytest.raises(RuntimeError):
        router.add(SomeMessage, handler)


def test_non_message_subclass_message():
    class MessageWithNoMessageBase:
        pass

    router = Router()
    with pytest.raises(RuntimeError):
        router.add(MessageWithNoMessageBase, handler)


def test_same_message_name():
    class DummyMessage(Message):
        pass

    router = Router()
    router.add(DummyMessage, handler)
    with pytest.raises(RuntimeError):
        router.add(conftest.DummyMessage, handler)

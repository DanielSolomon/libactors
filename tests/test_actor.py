import asyncio
import conftest
import dataclasses
import pytest

import libactors
from libactors.actor import register_handler


def test_init(core):
    actor = conftest.DummyActor(core.context, 'dummy')
    assert core.is_actor_type_exists(type(actor))


def test_init_args_kwargs():
    pass


def test_actor_id(context):
    actor_id = 'dummy'
    actor = conftest.DummyActor(context, actor_id)
    assert actor_id == actor.actor_id


@pytest.mark.asyncio
async def test_shutdown(context):
    proxy = await context.create_actor(
        actor_id='dummy',
        actor_cls=conftest.DummyActor,
    )
    assert not proxy._actor._shutdown_event.is_set()
    assert not proxy._actor.is_shutdown()
    assert len(context.core.actors) == 1

    tracker = await proxy.tell(
        context=context,
        message=libactors.actor.ShutdownMessage(),
    )
    await tracker
    await proxy.wait_until_shutdown()
    assert proxy._actor.is_shutdown()
    assert len(context.core.actors) == 0


@pytest.mark.asyncio
async def test_illegal_shutdowns(context):
    proxy = await context.create_actor(
        actor_id='dummy',
        actor_cls=conftest.DummyActor,
    )
    assert not proxy._actor._shutdown_event.is_set()
    assert len(context.core.actors) == 1

    await context.core.remove_actor('no-such-actor')
    assert len(context.core.actors) == 1

    with pytest.raises(ValueError):
        await context.core.remove_actor('/dummy')
    assert len(context.core.actors) == 1


@pytest.mark.asyncio
async def test_shutdown_actlets(core):
    pass


def test_message_post(context):
    actor = conftest.DummyActor(context, 'dummy')
    envelope = libactors.Envelope(
        id='id',
        sender='sender',
        receiver='receiver',
        message=conftest.DummyMessage(),
    )
    tracker = actor.post(envelope)
    assert (envelope, tracker) == actor._queue.get_nowait()


@pytest.mark.asyncio
async def test_message_handling(context):
    proxy = await context.create_actor(
        actor_id='dummy',
        actor_cls=conftest.DummyActor,
    )
    tracker = await proxy.tell(
        context=context,
        message=conftest.DummyMessage(),
    )
    await tracker
    assert proxy._actor._message_called


@pytest.mark.asyncio
async def test_message_error_handling(context):
    proxy = await context.create_actor(
        actor_id='dummy',
        actor_cls=conftest.DummyActor,
    )
    tracker = await proxy.tell(
        context=context,
        message=conftest.ErringMessage(),
    )
    with pytest.raises(RuntimeError):
        await tracker


@pytest.mark.asyncio
async def test_unhandled_message(context):
    proxy = await context.create_actor(
        actor_id='dummy',
        actor_cls=conftest.DummyActor,
    )
    tracker = await proxy.tell(
        context=context,
        message=conftest.UnhandledMessage(),
    )
    await tracker
    assert not tracker.is_handled


def test_serve():
    pass


def test_register_handler():
    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            pass

    assert SomeMessage in Actor._router._handlers.keys()


def test_register_handler_default_inheritance():
    assert set(conftest.DummyActor._router._handlers.keys()) == {
        libactors.actor.ShutdownMessage,
        libactors.actor.ActletDoneMessage,
        libactors.actor.TimerDoneMessage,
        conftest.ErringMessage,
        conftest.DummyMessage,
    }


def test_register_handler_inheritance():
    class SomeMessage(libactors.Message):
        pass

    class BaseActor(libactors.Actor):
        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            pass

    class Actor(conftest.DummyActor, BaseActor):
        pass

    assert set(Actor._router._handlers.keys()) == {
        libactors.actor.ShutdownMessage,
        libactors.actor.ActletDoneMessage,
        libactors.actor.TimerDoneMessage,
        conftest.ErringMessage,
        conftest.DummyMessage,
        SomeMessage,
    }


def test_register_handler_overrides_parent_handler():
    class Actor(libactors.Actor):
        @libactors.actor.register_handler(libactors.actor.ShutdownMessage)
        async def new_shutdown_handler(self, context, message):
            pass

    assert len(Actor._router._handlers) == 3
    assert Actor._router._handlers[libactors.actor.ShutdownMessage] == Actor.new_shutdown_handler


@pytest.mark.asyncio
async def test_create_actlet(context):
    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_actlet(
                context=context,
                name='not so unique name',
                function=self.class_actlet_function,
                configuration=None,
            )

        async def class_actlet_function(self, context, proxy, configuration):
            pass

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    with pytest.raises(RuntimeError):
        await proxy.wait_until_initialized()


@pytest.mark.asyncio
async def test_cancel_actlet_cleanup(context):
    actlet_name = 'not so unique name'

    @dataclasses.dataclass(frozen=True)
    class CancelMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_actlet(
                context=context,
                name=actlet_name,
                function=self.actlet_function,
                configuration=None,
            )

        @staticmethod
        async def actlet_function(context, proxy, configuration):
            while True:
                await asyncio.sleep(1)

        @libactors.actor.register_handler(CancelMessage)
        async def cancel(self, context, message):
            await self.cancel_actlet(context, actlet_name)

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )

    await proxy.wait_until_initialized()
    assert len(proxy._actor._actlets)
    await proxy.cancel_message(context, sync=True)
    assert not proxy._actor._actlets


@pytest.mark.asyncio
async def test_actlet_done(context):
    @dataclasses.dataclass(frozen=True)
    class ActletResult(libactors.Message):
        res: bool

    class Actor(libactors.Actor):
        async def initialize(self, context):
            self._actlet_res = False
            self._actlet_done = asyncio.Event()

            await self.create_actlet(
                context=context,
                name='short-lived actlet',
                function=self.actlet_function,
                configuration=None,
            )

        @register_handler(ActletResult)
        async def _on_actlet_done(self, context, message: ActletResult):
            """ This method verified that ActletDoneMessage was sent"""
            self._actlet_res = message.res
            self._actlet_done.set()

        @staticmethod
        async def actlet_function(context, proxy, configuration):
            return ActletResult(True)

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )

    await proxy.wait_until_initialized()
    assert not proxy._actor._actlet_res
    await proxy._actor._actlet_done.wait()
    assert proxy._actor._actlet_res
    assert len(proxy._actor._actlets) == 0
    assert not proxy._actor._actlets


@pytest.mark.asyncio
async def test_tell_me(context):
    actor_name = 'tell me actor'

    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            self.tell_me(SomeMessage())

    proxy = await context.create_actor(
        actor_name,
        Actor,
    )

    await proxy.wait_until_initialized()

    envelope, _ = proxy._actor._queue.get_nowait()
    assert envelope.message == SomeMessage()
    assert envelope.sender == f'/{actor_name}'
    assert envelope.receiver == f'/{actor_name}'

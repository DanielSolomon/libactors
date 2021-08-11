import asyncio
import pytest

import libactors


@pytest.mark.parametrize('exists', [True, False])
@pytest.mark.asyncio
async def test_timer_existence(context, exists):
    timer_name = 'timer'

    class Actor(libactors.Actor):
        async def initialize(self, context):
            if exists:
                await self.create_timer(
                    context=context,
                    name=timer_name,
                    message=None,
                    interval=10,
                )

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    await proxy.wait_until_initialized()

    assert proxy._actor.is_timer_exists(timer_name) == exists


@pytest.mark.asyncio
async def test_create_timer(context):
    interval = 0.01
    epsilon = 0.01

    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_timer(
                context=context,
                name='some_message_timer',
                message=SomeMessage(),
                interval=interval,
            )
            self._handled = False

        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            self._handled = True

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    await proxy.wait_until_initialized()
    assert not proxy._actor._handled
    await asyncio.sleep(interval + epsilon)
    assert proxy._actor._handled


@pytest.mark.asyncio
async def test_create_timer_now(context):
    interval = 0.1
    epsilon = 0.01

    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_timer(
                context=context,
                name='some_message_timer',
                message=SomeMessage(),
                interval=interval,
                now=True,
            )
            self._counter = 0

        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            self._counter += 1

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    await proxy.wait_until_initialized()
    assert not proxy._actor._counter
    await asyncio.sleep(epsilon)
    assert proxy._actor._counter == 1
    await asyncio.sleep(interval)
    assert proxy._actor._counter == 2


@pytest.mark.asyncio
async def test_cancel_timer(context):
    name = 'some_message_timer'
    interval = 0.1
    epsilon = 0.01

    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_timer(
                context=context,
                name=name,
                message=SomeMessage(),
                interval=interval,
                now=True,
            )
            self._handled = False

        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            pass

        @libactors.actor.register_handler(libactors.actor.TimerDoneMessage)
        async def timer_done_handler(self, context, message):
            self._handled = True

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    await proxy.wait_until_initialized()
    assert not proxy._actor._handled
    await asyncio.sleep(epsilon)
    await proxy._actor.cancel_timer(proxy._actor.context, name)
    await asyncio.sleep(epsilon)
    assert not proxy._actor._handled


@pytest.mark.asyncio
async def test_exception_timer(context):
    name = 'some_message_timer'
    epsilon = 0.01

    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_timer(
                context=context,
                name=name,
                message=SomeMessage(),
                interval="let's-raise-a-timer-exception",
                now=True,
            )
            self._handled = False

        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            pass

        @libactors.actor.register_handler(libactors.actor.TimerDoneMessage)
        async def timer_done_handler(self, context, message):
            self._handled = True

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    await proxy.wait_until_initialized()
    assert not proxy._actor._handled
    await asyncio.sleep(epsilon)
    assert proxy._actor._handled


@pytest.mark.parametrize('repetitions', [
    1,
    5,
])
@pytest.mark.parametrize('now', [
    True,
    False,
])
@pytest.mark.asyncio
async def test_create_timer_repetitions(context, repetitions, now):
    interval = 0.1

    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_timer(
                context=context,
                name='some_message_timer',
                message=SomeMessage(),
                repetitions=repetitions,
                interval=interval,
                now=now,
            )
            self._counter = 0
            self._done = False

        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            self._counter += 1

        @libactors.actor.register_handler(libactors.actor.TimerDoneMessage)
        async def timer_done(self, context, message):
            self._done = True

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    await proxy.wait_until_initialized()
    assert not proxy._actor._counter
    assert not proxy._actor._done
    await asyncio.sleep(interval * (repetitions + 1))
    assert proxy._actor._counter == repetitions
    assert proxy._actor._done
    assert len(proxy._actor._actlets) == 0


@pytest.mark.parametrize('now', [
    True,
    False,
])
@pytest.mark.asyncio
async def test_create_timer_delay(context, now):
    interval = 0.1
    delay = 0.5
    epsilon = 0.01

    class SomeMessage(libactors.Message):
        pass

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_timer(
                context=context,
                name='some_message_timer',
                message=SomeMessage(),
                delay=delay,
                interval=interval,
                now=now,
            )
            self._counter = 0

        @libactors.actor.register_handler(SomeMessage)
        async def handler(self, context, message):
            self._counter += 1

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    await proxy.wait_until_initialized()
    assert not proxy._actor._counter
    await asyncio.sleep(2 * interval)
    assert not proxy._actor._counter

    additional = 1 if now else 0
    await asyncio.sleep(3 * interval + epsilon)
    assert proxy._actor._counter == 0 + additional
    await asyncio.sleep(interval)
    assert proxy._actor._counter == 1 + additional

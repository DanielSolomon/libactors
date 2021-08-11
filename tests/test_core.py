import asyncio
import pytest

import conftest
import libactors
from libactors import log


def test_core_context(core):
    assert core.context.core == core
    assert core.context.identity == '/'

    logger = log.get_logger(__name__).bind(identity='/')
    assert core.context._log == logger


@pytest.mark.parametrize('actor_cls', [
    conftest.DummyActor,
    conftest.FoolishActor,
])
def test_actors_existence(core, actor_cls):
    assert core.is_actor_type_exists(actor_cls)


@pytest.mark.parametrize('actor_cls', [
    conftest.NotAnActor,
])
def test_actors_inexistence(core, actor_cls):
    assert not core.is_actor_type_exists(actor_cls)


@pytest.mark.parametrize('actor_cls', [
    conftest.DummyActor,
])
@pytest.mark.asyncio
async def test_create_actor(core, actor_cls):
    proxy = await core.create_actor(
        core.context,
        str(actor_cls),
        actor_cls,
    )

    await proxy.wait_until_initialized()
    assert proxy.initialized


@pytest.mark.parametrize('actor_cls', [
    conftest.FoolishActor,
])
@pytest.mark.asyncio
async def test_create_actor_failure(core, actor_cls):
    proxy = await core.create_actor(
        core.context,
        str(actor_cls),
        actor_cls,
    )

    with pytest.raises(RuntimeError):
        await proxy.wait_until_initialized()
    assert proxy.initialized


@pytest.mark.asyncio
async def test_create_actor_while_shutting_down(core):
    block_time = 0.1

    # Will block on core shutdown.
    class BlockingActor(libactors.Actor):
        @libactors.actor.register_handler(libactors.actor.messages.ShutdownMessage)
        async def shutdown_handler(self, context, message):
            # TODO: What can we do with real blocking actors?
            await asyncio.sleep(block_time)
            await super().handle_shutdown(context, message)

    await core.create_actor(
        core.context,
        'BlockingActor',
        BlockingActor,
    )

    # Trigger core shutdown.
    task = asyncio.create_task(core.shutdown())
    await asyncio.sleep(block_time / 2)

    # Validate actor creation throws.
    with pytest.raises(RuntimeError):
        await core.create_actor(core.context, 'DummyActor', conftest.DummyActor)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_create_multiple_actors(core: libactors.Core):
    proxies = [
        await core.create_actor(
            core.context,
            f'dummy_actor_{i}',
            conftest.DummyActor,
        ) for i in range(10)
    ]

    await asyncio.gather(*[p.wait_until_initialized() for p in proxies])

    for p in proxies:
        assert p.initialized


@pytest.mark.asyncio
async def test_duplicate_actor_id(core: libactors.Core):
    actor_id = 'dummy_actor'
    await core.create_actor(core.context, actor_id, conftest.DummyActor)
    with pytest.raises(RuntimeError):
        await core.create_actor(core.context, actor_id, conftest.DummyActor)


@pytest.mark.asyncio
async def test_shutdown_actors(core: libactors.Core):
    pass


def test_core_shutdown():
    pass


@pytest.mark.asyncio
async def test_not_running_core(core):
    assert core._running
    await core.shutdown()
    assert not core._running

    actor_id = 'dummy_actor'
    with pytest.raises(RuntimeError):
        await core.create_actor(core.context, actor_id, conftest.DummyActor)


@pytest.mark.parametrize('actor_cls', [
    conftest.DummyActor,
])
@pytest.mark.asyncio
async def test_create_actor_with_bindings(core, actor_cls):
    bindings = dict(
        foo='bar',
        one=2,
    )
    proxy = await core.create_actor(
        core.context,
        str(actor_cls),
        actor_cls,
        log_bindings=bindings,
    )

    bindings['identity'] = proxy._actor.actor_id
    proxy._actor.context._log._context == bindings

    await proxy.wait_until_initialized()
    assert proxy.initialized

    # Making sure source context has not changed somehow.
    assert core.context._log._context == {
        'identity': '/'
    }

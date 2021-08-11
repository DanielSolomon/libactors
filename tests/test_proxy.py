import dataclasses
import pytest

import conftest
import libactors


@pytest.mark.asyncio
async def test_get_proxy_for_existing_actor(context):
    actor_id = 'dummy_actor'
    await context.create_actor(actor_id, conftest.DummyActor)
    assert context.get_proxy(actor_id).actor_id == f'/{actor_id}'


@pytest.mark.asyncio
async def test_get_proxy_inexistent_actor(context):
    actor_id = 'dummy_actor'
    with pytest.raises(RuntimeError):
        assert context.get_proxy(actor_id)


@pytest.mark.asyncio
async def test_ask(context):
    proxy = await context.create_actor(
        actor_id='echo',
        actor_cls=conftest.EchoActor,
    )

    message = conftest.DataMessage('test')
    assert await proxy.ask(
        context=context,
        message=message,
    ) == message.data


@pytest.mark.asyncio
async def test_unhandled_ask(context):
    proxy = await context.create_actor(
        actor_id='echo',
        actor_cls=conftest.EchoActor,
    )

    with pytest.raises(RuntimeError):
        await proxy.ask(context=context, message=conftest.UnhandledMessage())


@pytest.mark.asyncio
async def test_erring_ask(context):
    proxy = await context.create_actor(
        actor_id='dummy',
        actor_cls=conftest.DummyActor,
    )

    with pytest.raises(RuntimeError):
        await proxy.ask(context=context, message=conftest.ErringMessage())


@pytest.mark.asyncio
async def test_auto_gen_proxy_sync(context):
    @dataclasses.dataclass(frozen=True)
    class Message(libactors.Message):
        content: str

    class Actor(libactors.Actor):
        async def initialize(self, context):
            pass

        @libactors.actor.register_handler(Message)
        async def handler(self, context, message):
            assert context.envelope.message == message
            assert context.envelope.sender == '/'
            assert context.envelope.receiver == '/actor'
            return message.content

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    content = 'test'
    assert await proxy.message(
        context=context,
        sync=True,
        content=content,
    ) == content


@pytest.mark.asyncio
async def test_auto_gen_proxy_async(context):
    @dataclasses.dataclass(frozen=True)
    class Message(libactors.Message):
        content: str

    class Actor(libactors.Actor):
        async def initialize(self, context):
            pass

        @libactors.actor.register_handler(Message)
        async def handler(self, context, message):
            return message.content

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    content = 'test'
    tracker = await proxy.message(
        context=context,
        sync=False,
        content=content,
    )
    assert await tracker == content


@pytest.mark.parametrize('sync', [True, False])
@pytest.mark.asyncio
async def test_auto_gen_proxy_no_handler(context, sync):
    @dataclasses.dataclass(frozen=True)
    class Message(libactors.Message):
        content: str

    class Actor(libactors.Actor):
        async def initialize(self, context):
            pass

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    content = 'test'
    with pytest.raises(KeyError):
        await proxy.message(
            context=context,
            sync=sync,
            content=content,
        )


@pytest.mark.parametrize('sync', [True, False])
@pytest.mark.asyncio
async def test_auto_gen_proxy_cache(context, sync):
    @dataclasses.dataclass(frozen=True)
    class Message(libactors.Message):
        content: str

    class Actor(libactors.Actor):
        async def initialize(self, context):
            pass

        @libactors.actor.register_handler(Message)
        async def handler(self, context, message):
            return message.content

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )
    content = 'test'

    # caching content
    proxy['content'] = content

    result = await proxy.message(
        context=context,
        sync=sync,
    )
    if sync:
        assert result == content
    else:
        assert await result == content


@pytest.mark.asyncio
async def test_cache(context):
    class Actor(libactors.Actor):
        async def initialize(self, context):
            pass

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )

    assert proxy._cache == dict()
    proxy['foo'] = 'bar'
    assert proxy._cache == dict(foo='bar')
    assert proxy['foo'] == 'bar'
    del proxy['foo']
    assert proxy._cache == dict()

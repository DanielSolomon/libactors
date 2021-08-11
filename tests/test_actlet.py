import asyncio
import dataclasses
import pytest

import libactors


@dataclasses.dataclass(frozen=True)
class ConfigurationMessage(libactors.Message):
    pass


@dataclasses.dataclass(frozen=True)
class ResultMessage(libactors.Message):
    result: str


''' NOTE(gil): this test is done through an Actor (and a core) instead of an Actlet because its hard to synthesize
            the requirements for an Actlet (context, proxy, etc..)
'''


@pytest.mark.asyncio
async def test_init(context):
    actlet_result = 'work'
    actlet_name = 'example'

    class Actor(libactors.Actor):
        async def initialize(self, context):
            self._actlet_result = None
            await self.create_actlet(
                context=context,
                name=actlet_name,
                function=self.actlet_function,
                configuration=ConfigurationMessage(),
            )

        @libactors.actor.register_handler(ResultMessage)
        async def handler(self, context, message):
            self._actlet_result = message.result

        @staticmethod
        async def actlet_function(context, proxy, configuration):
            return ResultMessage(actlet_result)

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )

    # Waiting until actor is initialized (actlet was created).
    await proxy.wait_until_initialized()
    assert proxy._actor._actlet_result is None
    assert len(proxy._actor._actlets) == 1

    # Waiting until actlet finishes its work.
    await list(proxy._actor._actlets.values())[0]

    # Waiting until actor handles the actlet result message.
    assert not proxy._actor._queue.empty()
    await proxy._actor._queue.join()

    assert proxy._actor._actlet_result == actlet_result
    assert len(proxy._actor._actlets) == 0


@pytest.mark.asyncio
async def test_cancel(core):
    async def actlet_function(context, proxy, configuration):
        await asyncio.sleep(10)

    actlet = libactors.actor.Actlet(
        name='actlet',
        context=None,
        entry_point=actlet_function,
        proxy=None,
        configuration=None,
    )

    await actlet.cancel()
    with pytest.raises(asyncio.CancelledError):
        await actlet


@pytest.mark.asyncio
async def test_invalid_function_signature(core):
    async def actlet_function(context):
        pass

    with pytest.raises(RuntimeError):
        libactors.actor.Actlet(
            name='actlet',
            context=None,
            entry_point=actlet_function,
            proxy=None,
            configuration=None,
        )


@pytest.mark.asyncio
async def test_invalid_function_signature_allow_typing(core):
    async def actlet_function(context: int, proxy: str, configuration) -> str:
        pass

    libactors.actor.Actlet(
        name='actlet',
        context=None,
        entry_point=actlet_function,
        proxy=None,
        configuration=None,
    )


@pytest.mark.asyncio
async def test_invalid_function_not_async(core):
    def actlet_function(context, proxy, configuration):
        pass

    with pytest.raises(RuntimeError):
        libactors.actor.Actlet(
            name='actlet',
            context=None,
            entry_point=actlet_function,
            proxy=None,
            configuration=None,
        )


@pytest.mark.asyncio
async def test_same_actlet_names(context):
    actlet_name = 'not so unique name'

    class Actor(libactors.Actor):
        async def initialize(self, context):
            await self.create_actlet(
                context=context,
                name=actlet_name,
                function=self.actlet_function,
                configuration=None,
            )
            await self.create_actlet(
                context=context,
                name=actlet_name,
                function=self.actlet_function,
                configuration=None,
            )

        @staticmethod
        async def actlet_function(context, proxy, configuration):
            pass

    proxy = await context.create_actor(
        actor_id='actor',
        actor_cls=Actor,
    )

    with pytest.raises(RuntimeError):
        await proxy.wait_until_initialized()


@pytest.mark.asyncio
async def test_none_result(core):
    pass

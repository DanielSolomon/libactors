import pytest

from . import mocks


@pytest.fixture
def core():
    return mocks.CoreMock()


@pytest.fixture
async def actor_factory(request, context, mock_tell_me):
    actors = []

    async def factory(actor):
        # start actor and wait for it.
        actor.start()
        await actor.wait_until_initialized()

        # save for cleanup.
        actors.append(actor)
        return actor

    try:
        yield factory
    finally:
        for actor in reversed(actors):
            await actor.handle_shutdown(
                context,
                # TODO: fix
                None,
            )
            await actor.wait_until_shutdown()


@pytest.fixture
async def mock_tell_me(mocker):
    return mocker.patch('libactors.Actor.tell_me')


@pytest.fixture
async def actlet_factory(mocker):
    return mocker.patch('libactors.actor.actlet.Actlet', new_callable=mocks.ActletMockFactory)

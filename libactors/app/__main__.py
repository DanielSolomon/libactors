import asyncio
import asyncclick as click
import structlog
import hypercorn
import hypercorn.asyncio

import libactors

from . import (
    actors,
    api,
)

logger = structlog.get_logger()


@click.group()
def cli():
    pass


@cli.command()
async def run():
    # Setup.
    core = libactors.get_core()
    context = libactors.Context(
        core=core,
        log=logger,
        identity='/',
    )
    core.set_context(context)

    # Create main actor.
    hello_world = await context.create_actor(
        actor_id='hello-world',
        actor_cls=actors.hello_world_actor.HelloWorldActor,
    )

    # Run.
    app = api.create_app(context)
    config = hypercorn.Config()
    config.bind = ['localhost:8080']

    await asyncio.wait(
        [
            hello_world.wait_until_shutdown(),
            hypercorn.asyncio.serve(app, config=config),
        ],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if not hello_world._actor.is_shutdown():
        await hello_world.tell(context, libactors.actor.ShutdownMessage())
        await hello_world.wait_until_shutdown()


if __name__ == '__main__':
    try:
        cli(_anyio_backend='asyncio')
    except Exception as e:
        logger.exception(f'{e}')

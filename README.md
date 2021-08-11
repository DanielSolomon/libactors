# libactors
> asyncio concurrency framework without locks based on the actor model.

## Table of contents
* [Setup](#setup)
    * [Requirements](#requirements)
    * [Instructions](#instructions)
* [Documentation](#documentation)
* [Tutorial](#tutorial)

## Setup
### Requirements
* python 3.8+
* pipenv

### Instructions
```bash
$ git clone git@github.com:DanielSolomon/libactors.git
$ cd libactors
$ pipenv --python 3.8
$ pipenv shell
$ pipenv install --dev
$ python -m pytest tests/ # All test should pass!
```

## Documentation
You can easily generate documentation using `pdoc3` (which is installed automatically if you followed [setup instructions](#instructions)):
```bash
$ pdoc --html -o docs/html libactors
$ google-chrome docs/html/libactors/index.html
```

## Tutorial

Let's learn by examples.

### Hello, World!

```python
import asyncio
import dataclasses
import libactors
import logging
import structlog


logger = structlog.get_logger()


@dataclasses.dataclass(frozen=True)
class HelloMessage(libactors.Message):
    pass


class HelloWorldActor(libactors.Actor):

    @libactors.actor.register_handler(HelloMessage)
    async def on_hello_message(self, context, message: HelloMessage):
        context.fatal('Hello, World!')


def init_core_and_context():
    core: libactors.Core = libactors.get_core()
    context: libactors.Context = libactors.Context(
        core        = core,
        log         = logger,
        identity    = '/',
    )
    core.set_context(context)
    return core, context


async def send_hello_messages(context: libactors.Context, hello_world_proxy: libactors.ActorProxy):
    for i in range(5):
        context.fatal(f'sending hello message #{i+1}')
        await hello_world_proxy.tell(context, HelloMessage())
        # Giving HelloWorld Actor CPU time.
        await asyncio.sleep(0.01)
    # We don't need it anymore
    await hello_world_proxy.tell(context, libactors.actor.ShutdownMessage())


async def main():
    core, context = init_core_and_context()
    hello_world_proxy: libactors.ActorProxy = await core.create_actor(context, 'hello-world', actor_cls=HelloWorldActor)
    
    await asyncio.gather(
        send_hello_messages(context, hello_world_proxy),
        hello_world_proxy.wait_until_shutdown(),
    )

    context.fatal('done')


if __name__ == '__main__':
    asyncio.run(main())
```
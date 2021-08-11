import asyncio

import libactors

from . import messages


class HelloWorldActor(libactors.Actor):
    def __init__(self, context, actor_id):
        super().__init__(context, actor_id)

        self._sleep = 1
        self._message = 'Hello, World! {count}'
        self._count = 0

    async def initialize(self, context):
        self.tell_me(messages.PrepareMessage())

    @libactors.actor.register_handler(messages.PrepareMessage)
    async def prepare(self, context, message: messages.PrepareMessage):
        context.info(f'handling PrepareMessage')
        self.tell_me(messages.LogMessage())

    @libactors.actor.register_handler(messages.LogMessage)
    async def log(self, context, message: messages.LogMessage):
        self._count += 1
        context.fatal(self._message.format(count=self._count))
        self.tell_me(messages.LogMessage())
        await asyncio.sleep(self._sleep)

    @libactors.actor.register_handler(messages.SlowDownMessage)
    async def slow_down(self, context, message: messages.SlowDownMessage):
        self._sleep *= message.times
        context.info(f'slowing down: {message.times} times, new sleep is: {self._sleep}')

    @libactors.actor.register_handler(messages.SpeedUpMessage)
    async def speed_up(self, context, message: messages.SpeedUpMessage):
        self._sleep /= message.times
        context.info(f'speeding up: {message.times} times, new sleep is: {self._sleep}')

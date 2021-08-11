import asyncio
import queue
import typing

from ...actor.messages import Message


class EnvelopeTrackerMock:
    def __init__(self):
        self._fut = asyncio.get_event_loop().create_future()
        # TODO: expose api to control result
        self._fut.set_result(None)

    def __await__(self):
        return self._fut.__await__()


class ProxyMock:
    def __init__(self, actor_mock):
        self._actor_mock = actor_mock
        self._tell = []
        self._ask = []
        self._cache = {}
        self._ask_responses = queue.Queue()

    # MOCK API

    @property
    def is_initialized(self) -> bool:
        return True

    async def wait_until_initialized(self) -> bool:
        return True

    async def wait_until_shutdown(self) -> bool:
        return True

    async def tell(self, context, message, reply_to=None):
        self._actor_mock._messages.append(message)
        self._tell.append(message)
        return EnvelopeTrackerMock()

    async def ask(self, context, message):
        self._actor_mock._messages.append(message)
        self._ask.append(message)
        if self._ask_responses.empty():
            return None
        response = self._ask_responses.get()
        if isinstance(response, Exception):
            raise response
        return response

    def __getitem__(self, key):
        return self._cache.__getitem__(key)

    def __setitem__(self, key, value):
        return self._cache.__setitem__(key, value)

    def __delitem__(self, key):
        return self._cache.__delitem__(key)

    def __getattr__(self, func):
        message = ''.join(s.capitalize() for s in func.split('_'))
        message_cls = self._actor_mock._actor_cls._router.get_message_cls(message)

        async def message_sender(context, sync: bool = False, **kwargs):
            for key in message_cls.__dataclass_fields__.keys():
                if key not in kwargs and key in self._cache:
                    kwargs[key] = self._cache[key]
            message = message_cls(**kwargs)
            if sync:
                return await self.ask(context, message)
            else:
                return await self.tell(context, message)

        return message_sender

    # TEST API

    @property
    def actor_id(self):
        return self._actor_mock._actor_id

    @property
    def messages(self) -> typing.List[Message]:
        return self._actor_mock.messages

    def has_message(self, message: Message) -> bool:
        return message in self.messages

    def message_index(self, message: Message) -> int:
        return self.messages.index(message)

    def get_ask_messages(self):
        return self._ask

    def get_tell_messages(self):
        return self._tell

    def set_ask_response(self, response):
        self._ask_responses = queue.Queue()
        self._ask_responses.put(response)

    def set_ask_exception(self, exception: Exception):
        self._ask_responses = queue.Queue()
        self._ask_responses.put(exception)

    def put_ask_responses(self, *responses):
        for response in responses:
            self._ask_responses.put(response)

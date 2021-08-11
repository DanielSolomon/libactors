from .proxy import ProxyMock
from .actor import ActorMock


class CoreMock:
    def __init__(self):
        self._actors = {}
        self._proxies = {}

    @property
    def created_actors(self):
        return self._actors

    @property
    def created_proxies(self):
        return self._proxies

    async def create_actor(self, callee_context, actor_id, actor_cls, *args, **kwargs) -> ProxyMock:
        return self._create_actor(callee_context, actor_id, actor_cls, *args, **kwargs)

    def _create_actor(self, callee_context, actor_id, actor_cls, *args, **kwargs) -> ProxyMock:
        actor = ActorMock(actor_id, actor_cls, *args, **kwargs)
        self._actors[actor_id] = actor

        proxy = ProxyMock(actor)
        self._proxies[actor_id] = proxy

        return proxy

    async def remove_actor(self, actor_id: str):
        # TODO: fix
        return True
        del self._actors[actor_id]

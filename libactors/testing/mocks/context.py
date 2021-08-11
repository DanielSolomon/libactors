import contextlib


from ... import log
from .proxy import ProxyMock
from .actor import ActorMock

logger = log.get_logger(__name__)


class ContextMock:
    def __init__(self, core, identity, envelope=None):
        self._core = core
        self._identity = identity
        self._log = logger.bind(identity=identity)
        self._envelope = envelope
        self._logged_lines = set()
        self._raise_on_unknown_actor: bool = False

    # mock API
    def __call__(self, *args, **kwargs):
        return ContextMock(core=self._core, identity=self._identity, envelope=self._envelope)

    @contextlib.contextmanager
    def bind(self, **bindings):
        try:
            # Saving old bindings logger object to restore.
            old_log = self._log
            # Bind.
            self._log = self._log.bind(**bindings)
            yield
        finally:
            # Restore old logger with old bindings.
            self._log = old_log

    def log(self, level, event, component, timestamp, **kwargs):
        self._logged_lines.add(event)

    @property
    def identity(self):
        return self._identity

    @property
    def sender(self):
        return 'sender'

    @property
    def envelope(self):
        return self._envelope

    @property
    def core(self):
        return self._core

    def debug(self, *args, **kwargs):
        self._log.debug(*args, **kwargs)

    def info(self, *args, **kwargs):
        self._log.info(*args, **kwargs)

    def warning(self, *args, **kwargs):
        self._log.warning(*args, **kwargs)

    def error(self, *args, **kwargs):
        self._log.error(*args, **kwargs)

    def fatal(self, *args, **kwargs):
        self._log.fatal(*args, **kwargs)

    def exception(self, *args, **kwargs):
        self._log.exception(*args, **kwargs)

    async def create_actor(self, actor_id, actor_cls, *args, **kwargs):
        return self._create_actor(actor_id, actor_cls, *args, **kwargs)

    def get_proxy(self, actor_id):
        if actor_id not in self._core.created_proxies:
            if self.raise_on_unknown_actor:
                raise RuntimeError(f'unknown {actor_id}')
            # create anonymous actor.
            actor = ActorMock(actor_id, 'anonymous_actor')
            self._core.created_proxies[actor_id] = ProxyMock(actor)
        return self._core.created_proxies[actor_id]

    # test API
    @property
    def created_actors(self):
        return list(self._core.created_actors.values())

    @property
    def created_proxies(self):
        return list(self._core.created_proxies.values())

    @property
    def raise_on_unknown_actor(self) -> bool:
        return self._raise_on_unknown_actor

    @raise_on_unknown_actor.setter
    def raise_on_unknown_actor(self, flag: bool):
        self._raise_on_unknown_actor = flag

    def _create_actor(self, actor_id, actor_cls, *args, **kwargs):
        return self._core._create_actor(self, actor_id, actor_cls, *args, **kwargs)

class ActorMock:
    def __init__(self, actor_id, actor_cls, *args, **kwargs):
        self._actor_id = actor_id
        self._actor_cls = actor_cls

        self._init_args = args
        self._init_kwargs = kwargs

        self._messages = []

    def __repr__(self):
        return f'{self.__class__.__name__}(actor_id={self._actor_id!r}, actor_cls={self._actor_cls})'

    @property
    def init_args(self):
        return self._init_args

    @property
    def init_kwargs(self):
        return self._init_kwargs

    @property
    def messages(self):
        return self._messages

    def has_message(self, message):
        return message in self.messages

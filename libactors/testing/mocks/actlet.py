import asyncio


class ActletMockFactory:
    def __init__(self):
        self._actlets = {}

    def __call__(self, context, entry_point, proxy, configuration, name):
        actlet = ActletMock(context, entry_point, proxy, configuration, name)
        self._actlets[name] = actlet
        return actlet


class ActletMock:
    def __init__(self, context, entry_point, proxy, configuration, name):
        self._name = name
        self._context = context
        self._entry_point = entry_point
        self._proxy = proxy
        self._configuration = configuration
        self._fut = asyncio.get_event_loop().create_future()
        # TODO: expose api to control result
        self._fut.set_result(None)

    def __await__(self):
        return self._fut.__await__()

    async def cancel(self):
        return

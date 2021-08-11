import pytest

import libactors
from libactors import log


def test_context_logs():
    logger = log.get_logger(__name__)
    context = libactors.Context(None, logger, 'dummy')
    logger = logger.bind(identity='dummy')

    assert context._log == logger
    assert context.debug == context._log.debug
    assert context.info == context._log.info
    assert context.warning == context._log.warning
    assert context.error == context._log.error
    assert context.fatal == context._log.fatal
    assert context.exception == context._log.exception


def test_init():
    core = 'core'
    logger = log.get_logger(__name__)
    identity = 'identity'
    envelope = 'envelope'

    context = libactors.Context(
        core=core,
        log=logger,
        identity=identity,
        envelope=envelope,
    )

    assert context._core == core
    assert context._log == logger.bind(identity=identity)
    assert context._identity == identity
    assert context._envelope == envelope


def test_empty_context_call():
    core = 'core'
    logger = log.get_logger(__name__)
    identity = 'identity'
    envelope = 'envelope'

    context = libactors.Context(
        core=core,
        log=logger,
        identity=identity,
        envelope=envelope,
    )

    derived_context = context()

    assert context._core == derived_context._core
    assert context._log == derived_context._log
    assert context._identity == derived_context._identity
    assert context._envelope == derived_context._envelope


def test_overriding_context_call():
    core = 'core'
    logger = log.get_logger(__name__)
    identity = 'identity'
    envelope = 'envelope'

    context = libactors.Context(
        core=core,
        log=logger,
        identity=identity,
        envelope=envelope,
    )

    derived_core = 'derived_core'
    derived_identity = 'derived_identity'
    derived_log = log.get_logger(__name__).bind(identity=derived_identity)
    derived_envelope = 'derived_envelope'
    derived_context = context(
        core=derived_core,
        log=derived_log,
        identity=derived_identity,
        envelope=derived_envelope,
    )

    assert derived_context._core == derived_core
    assert derived_context._log == derived_log
    assert derived_context._identity == derived_identity
    assert derived_context._envelope == derived_envelope


@pytest.mark.asyncio
async def test_create_actor_correct_id(context):
    actor_id = 'actor'

    class Actor(libactors.Actor):
        pass

    proxy = await context.create_actor(actor_id=actor_id, actor_cls=Actor)
    assert proxy.actor_id == f'/{actor_id}'


@pytest.mark.asyncio
async def test_create_actor_chain_correct_ids(context):
    actor_id = 'actor'

    class Actor(libactors.Actor):
        pass

    proxy = await context.create_actor(actor_id=actor_id, actor_cls=Actor)
    assert proxy.actor_id == f'/{actor_id}'

    proxy = await proxy._actor._context.create_actor(actor_id=actor_id, actor_cls=Actor)
    assert proxy.actor_id == f'/{actor_id}/{actor_id}'


@pytest.mark.asyncio
async def test_create_actor_with_absolute_id(context):
    actor_id = 'actor'
    abs_actor_id = '/abs/actor'

    class Actor(libactors.Actor):
        pass

    proxy = await context.create_actor(actor_id=actor_id, actor_cls=Actor)
    assert proxy.actor_id == f'/{actor_id}'

    proxy = await proxy._actor._context.create_actor(actor_id=abs_actor_id, actor_cls=Actor)
    assert proxy.actor_id == abs_actor_id


@pytest.mark.asyncio
async def test_get_proxies_absolute_and_relative(context):
    actor_id = 'actor'

    class Actor(libactors.Actor):
        pass

    proxy_parent = await context.create_actor(actor_id=actor_id, actor_cls=Actor)
    assert proxy_parent.actor_id == f'/{actor_id}'

    proxy_child = await proxy_parent._actor._context.create_actor(
        actor_id=actor_id, actor_cls=Actor
    )
    assert proxy_child.actor_id == f'/{actor_id}/{actor_id}'

    # relative
    proxy = proxy_parent._actor.context.get_proxy(actor_id)
    assert proxy.actor_id == proxy_child.actor_id

    # absolute
    proxy = proxy_parent._actor.context.get_proxy(proxy_parent.actor_id)
    assert proxy.actor_id == proxy_parent.actor_id


def test_get_proxy():
    pass


def test_bind():
    core = 'core'
    logger = log.get_logger(__name__)
    identity = 'identity'
    envelope = 'envelope'

    context = libactors.Context(
        core=core,
        log=logger,
        identity=identity,
        envelope=envelope,
    )

    bindings = context._log._context
    additional_bindings = dict(
        foo='bar',
        one=2,
    )
    with context.bind(**additional_bindings):
        expected_bindings = dict(**bindings, **additional_bindings)
        assert expected_bindings == context._log._context
    assert bindings == context._log._context


def test_bind_override():
    core = 'core'
    logger = log.get_logger(__name__)
    identity = 'identity'
    envelope = 'envelope'

    context = libactors.Context(
        core=core,
        log=logger,
        identity=identity,
        envelope=envelope,
    )

    bindings = context._log._context
    additional_bindings = dict(
        foo='bar',
        one=2,
        identity='new_identity',
    )
    with context.bind(**additional_bindings):
        expected_bindings = bindings.copy()
        expected_bindings.update(additional_bindings)
        assert expected_bindings == context._log._context
    assert bindings == context._log._context


def test_bind_on_init():
    core = 'core'
    logger = log.get_logger(__name__)
    identity = 'identity'
    envelope = 'envelope'

    additional_bindings = dict(
        foo='bar',
        one=2,
    )

    context = libactors.Context(
        core=core,
        log=logger,
        identity=identity,
        envelope=envelope,
        **additional_bindings,
    )

    additional_bindings['identity'] = identity
    assert additional_bindings == context._log._context


@pytest.mark.asyncio
async def test_bind_function(context):

    bindings = context._log._context.copy()

    additional_bindings = dict(
        foo='bar',
        one=2,
    )

    @libactors.bind(**additional_bindings)
    def foo(context, *args, **kwargs):
        bindings.update(additional_bindings)
        assert context._log._context == bindings

    @libactors.bind(**additional_bindings)
    async def afoo(context, *args, **kwargs):
        bindings.update(additional_bindings)
        assert context._log._context == bindings

    foo(context, 1, a=2)
    await afoo(context, 1, a=2)


@pytest.mark.asyncio
async def test_bind_function_context_in_kwargs(context):

    bindings = context._log._context.copy()

    additional_bindings = dict(
        foo='bar',
        one=2,
    )

    @libactors.bind(**additional_bindings)
    def foo(*args, **kwargs):
        bindings.update(additional_bindings)
        assert kwargs['context']._log._context == bindings

    @libactors.bind(**additional_bindings)
    async def afoo(*args, **kwargs):
        bindings.update(additional_bindings)
        assert kwargs['context']._log._context == bindings

    foo(1, a=2, context=context)
    await afoo(1, a=2, context=context)


@pytest.mark.asyncio
async def test_bind_method(context):

    bindings = context._log._context.copy()

    additional_bindings = dict(
        foo='bar',
        one=2,
    )

    class Foo:
        @libactors.bind(**additional_bindings)
        def foo(self, context, *args, **kwargs):
            bindings.update(additional_bindings)
            assert context._log._context == bindings

        @libactors.bind(**additional_bindings)
        async def afoo(self, context, *args, **kwargs):
            bindings.update(additional_bindings)
            assert context._log._context == bindings

    Foo().foo(context, 1, a=2)
    await Foo().afoo(context, 1, a=2)


@pytest.mark.asyncio
async def test_bind_class_method(context):

    bindings = context._log._context.copy()

    additional_bindings = dict(
        foo='bar',
        one=2,
    )

    class Foo:
        @classmethod
        @libactors.bind(**additional_bindings)
        def foo(cls, context, *args, **kwargs):
            bindings.update(additional_bindings)
            assert context._log._context == bindings

        @classmethod
        @libactors.bind(**additional_bindings)
        async def afoo(cls, context, *args, **kwargs):
            bindings.update(additional_bindings)
            assert context._log._context == bindings

    Foo().foo(context, 1, a=2)
    Foo.foo(context, 1, a=2)

    await Foo().afoo(context, 1, a=2)
    await Foo.afoo(context, 1, a=2)


@pytest.mark.asyncio
async def test_bind_static_method(context):

    bindings = context._log._context.copy()

    additional_bindings = dict(
        foo='bar',
        one=2,
    )

    class Foo:
        @staticmethod
        @libactors.bind(**additional_bindings)
        def foo(context, *args, **kwargs):
            bindings.update(additional_bindings)
            assert context._log._context == bindings

        @staticmethod
        @libactors.bind(**additional_bindings)
        async def afoo(context, *args, **kwargs):
            bindings.update(additional_bindings)
            assert context._log._context == bindings

    Foo().foo(context, 1, a=2)
    Foo.foo(context, 1, a=2)

    await Foo().afoo(context, 1, a=2)
    await Foo.afoo(context, 1, a=2)


@pytest.mark.asyncio
async def test_bind_function_no_context(context):
    @libactors.bind(a=1)
    def foo(*args, **kwargs):
        pass

    with pytest.raises(RuntimeError):
        foo()

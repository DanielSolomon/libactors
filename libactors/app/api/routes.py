import logging
import traceback

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.requests import Request

from .. import actors


def get_hello_world(context):
    hello_world = context.get_proxy('/hello-world')
    return hello_world


def create_app(context):

    app: FastAPI = FastAPI()

    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=dict(
                error=str(exc),
                traceback=traceback.format_exc(),
            ),
        )

    @app.get('/')
    async def home():
        context.info('received / request, redirecting to /docs')
        return RedirectResponse(url='/docs')

    @app.post('/slow-down')
    async def slow_down(times: int):
        context.info(f'received /slow-down request: {times}')
        hello_world_proxy = get_hello_world(context)
        await hello_world_proxy.ask(
            context, actors.hello_world_actor.messages.SlowDownMessage(times=times)
        )

    @app.post('/speed-up')
    async def speed_up(times: int):
        context.info(f'received /speed-up request: {times}')
        hello_world_proxy = get_hello_world(context)
        await hello_world_proxy.ask(
            context, actors.hello_world_actor.messages.SpeedUpMessage(times=times)
        )

    return app

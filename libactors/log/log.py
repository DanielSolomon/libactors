import logging
import inspect
import structlog
import datetime
import typing

TIME_FMT = '%Y-%m-%dT%H:%M:%S.%fZ'

DEFAULT_DISABLED_LOGGERS = [
    'hpack',
    'hpack.table',
    'hpack.hpack',
    'pgnotify.notify',
]


def add_caller_info(logger, method_name, event_dict):
    frame = inspect.currentframe()
    while frame:
        frame = frame.f_back
        module = frame.f_globals['__name__']
        if module.startswith('structlog.') or module == 'logging':
            continue

        event_dict['module'] = module
        event_dict['func'] = event_dict.get('func', frame.f_code.co_name)
        event_dict['line'] = event_dict.get('line', frame.f_lineno)
        return event_dict


def add_timestamp(logger, method_name, event_dict):
    event_dict['timestamp'] = datetime.datetime.utcnow().strftime(TIME_FMT)
    return event_dict


class StructlogHandler(logging.Handler):
    """
    Feeds all events back into structlog.
    """
    def __init__(self, *args, **kw):
        super(StructlogHandler, self).__init__(*args, **kw)
        self._log = structlog.get_logger()

    def emit(self, record):
        tags = dict(
            level=record.levelno,
            event=record.getMessage(),
            name=record.name,
            module=record.filename,
            func=record.funcName,
            line=record.lineno,
            timestamp=record.created,
            exc_info=bool(record.exc_info),
        )
        self._log.log(**tags)


def monkey_patch_logging(disabled_logs: typing.List[str] = DEFAULT_DISABLED_LOGGERS):
    if structlog.is_configured():
        return

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,  # adds log level
            structlog.stdlib.add_log_level_number,  # adds log level number
            add_timestamp,  # adds toka timestamp
            add_caller_info,  # adds caller info
            structlog.processors.format_exc_info,  # adds exc on exc

            # Must be last
            structlog.processors.JSONRenderer(),  # outputs as json
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    for logger_name in disabled_logs:
        print(f'disabling logger for: {logger_name}')
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)

    handler = StructlogHandler()
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers = []
    logger.addHandler(handler)


def get_logger(name):
    return structlog.get_logger(name)

import dataclasses
from typing import Any

from ..message import (
    Message,
)


@dataclasses.dataclass(frozen=True)
class ActletDoneMessage(Message):
    """Framework-level message sent internally when Actlet execution ends
    """
    result: Any


@dataclasses.dataclass(frozen=True)
class TimerConfiguration(Message):
    """Timer configuration.

    Args:
        message (libactors.Message): Message to send when time is up.
        interval (float): Timer countdown interval in seconds.
        delay (float): Timer delay before starting first countdown in seconds.
        now (bool): Whether or not send `message` before starting countdown.
        repetitions (int): How many cycles of the timer (0 represents infinite).
    """
    message: Message
    interval: float
    delay: float
    now: bool
    repetitions: int


@dataclasses.dataclass(frozen=True)
class TimerDoneMessage(Message):
    """In case that the timer was configured with finite repetitions.
    This message will be sent to the created actor, indicating the timer has finished its job.
    """
    pass


@dataclasses.dataclass(frozen=True)
class ShutdownMessage(Message):
    """Shutdown message to request an actor to turn off.
    """
    pass

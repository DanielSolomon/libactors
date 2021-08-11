import dataclasses

import libactors


@dataclasses.dataclass(frozen=True)
class PrepareMessage(libactors.Message):
    pass


@dataclasses.dataclass(frozen=True)
class LogMessage(libactors.Message):
    pass


@dataclasses.dataclass(frozen=True)
class SlowDownMessage(libactors.Message):
    times: int


@dataclasses.dataclass(frozen=True)
class SpeedUpMessage(libactors.Message):
    times: int

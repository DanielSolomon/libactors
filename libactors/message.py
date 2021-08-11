import typing
import dataclasses
import mashumaro


@dataclasses.dataclass(frozen=True)
class Message(mashumaro.DataClassJSONMixin):
    """Base message, any new message must derive from it.
    """
    pass


@dataclasses.dataclass(frozen=True)
class Envelope(mashumaro.DataClassJSONMixin):
    """Envelope which wraps a message with metadata, each envelope has unique id.
    """
    id: str
    sender: str
    receiver: str
    message: Message
    reply_to: typing.Optional[str] = None

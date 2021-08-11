from ..exceptions import AioException


class MultiWaiterException(AioException):
    pass


class MultiWaiterKeyAlreadyExistsException(AioException):
    pass


class MultiWaiterNotDoneException(MultiWaiterException):
    pass

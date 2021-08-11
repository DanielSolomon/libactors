from ..exceptions import AioException


class ServiceException(AioException):
    pass


class ServiceStartupException(ServiceException):
    pass

import abc


class BaseDataGetter(metaclass=abc.ABCMeta):
    def __call__(self, system):
        raise NotImplementedError

import abc
import time

from .base_getter_filter import BaseDataGetterFilter

from core.lib.common import ClassFactory, ClassType

__all__ = ('CASVADataGetterFilter',)


@ClassFactory.register(ClassType.GEN_GETTER_FILTER, alias='casva')
class CASVADataGetterFilter(BaseDataGetterFilter, abc.ABC):

    def __init__(self):
        self.skip_count = 0
        self.latest_time = 0

    def reset_filter(self):
        self.skip_count = 0

    def __call__(self, system):
        data_coming_interval = 2
        record_time = time.time()
        if self.latest_time > 0 and record_time - self.latest_time > data_coming_interval:
            self.skip_count += 1
            self.latest_time = record_time
            return False
        else:
            self.latest_time = record_time
            return True

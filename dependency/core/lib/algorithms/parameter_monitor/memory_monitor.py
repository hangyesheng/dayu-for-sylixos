import abc


from .base_monitor import BaseMonitor

from core.lib.common import ClassFactory, ClassType, LOGGER

__all__ = ('MemoryMonitor',)


@ClassFactory.register(ClassType.MON_PRAM, alias='memory')
class MemoryMonitor(BaseMonitor, abc.ABC):
    def __init__(self, system):
        super().__init__(system)
        self.name = 'memory'

    def get_parameter_value(self):
        import psutil
        return psutil.virtual_memory().percent

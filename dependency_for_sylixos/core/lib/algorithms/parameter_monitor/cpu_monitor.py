import abc


from .base_monitor import BaseMonitor

from core.lib.common import ClassFactory, ClassType, LOGGER

__all__ = ('CPUMonitor',)


@ClassFactory.register(ClassType.MON_PRAM, alias='cpu')
class CPUMonitor(BaseMonitor, abc.ABC):
    def __init__(self, system):
        super().__init__(system)
        self.name = 'cpu'

    def get_parameter_value(self):
        import psutil
        return psutil.cpu_percent()



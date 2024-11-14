import abc
import threading


class BaseMonitor(metaclass=abc.ABCMeta):

    def __init__(self, system):
        self.name = ''
        self.system = system

    def __call__(self):
        return threading.Thread(target=self.run_monitor, args=(self.system,))

    def get_parameter_value(self):
        raise NotImplementedError

    def run_monitor(self, system):
        system.resource_info.update({self.name: self.get_parameter_value()})

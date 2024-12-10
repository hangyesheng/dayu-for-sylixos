import abc
import json
import os
import shutil
import subprocess

from .base_operation import BaseBSTOperation

from core.lib.common import ClassFactory, ClassType, LOGGER, VideoOps
from core.lib.content import Task

__all__ = ('CEVASBSTOperation',)


@ClassFactory.register(ClassType.GEN_BSTO, alias='cevas')
class CEVASBSTOperation(BaseBSTOperation, abc.ABC):
    def __init__(self):
        pass

    def __call__(self, system, compressed_file, hash_codes):
        task = system.current_task
        tmp_data = task.get_tmp_data()

        file_size = os.path.getsize(compressed_file)
        tmp_data['file_size'] = file_size
        task.set_tmp_data(tmp_data)

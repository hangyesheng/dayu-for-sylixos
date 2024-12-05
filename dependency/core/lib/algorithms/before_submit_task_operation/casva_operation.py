import abc
import json
import os

from .base_operation import BaseBSTOperation

from core.lib.common import ClassFactory, ClassType
from core.lib.content import Task

__all__ = ('CASVABSTOperation',)


@ClassFactory.register(ClassType.GEN_BSO, alias='casva')
class CASVABSTOperation(BaseBSTOperation, abc.ABC):
    def __init__(self):
        # in multiprocessing env, we should use disk file to transmit past task info
        self.past_info_record_path = 'casva_info_record.json'

    def load_past_info_record(self):
        if not os.path.exists(self.past_info_record_path):
            return None

        with open(self.past_info_record_path, 'r') as f:
            return json.load(f)

    def save_past_info_record(self, past_info_record):
        with open(self.past_info_record_path, 'w') as f:
            json.dump(past_info_record, f)

    def __call__(self, system, compressed_file, hash_codes):
        task = system.current_task

        # TODO: calculate content dynamics
        tmp_data = task.get_tmp_data()
        meta_data = task.get_metadata()
        file_size = os.path.getsize(compressed_file)
        tmp_data['file_size'] = file_size

        tmp_data['file_dynamics'] = xxx



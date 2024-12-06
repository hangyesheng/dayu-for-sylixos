import abc
import json
import time

from .base_getter import BaseDataGetter

from core.lib.common import ClassFactory, ClassType, LOGGER, FileOps
from core.lib.network import http_request
from core.lib.estimation import TimeEstimator

__all__ = ('HttpVideoGetter',)


@ClassFactory.register(ClassType.GEN_GETTER, alias='http_video')
class HttpVideoGetter(BaseDataGetter, abc.ABC):
    """
    get video data from http (fastapi)
    preprocessed video data with accuracy information
    """

    def __init__(self):
        self.file_name = None
        self.hash_codes = None

    @TimeEstimator.estimate_duration_time
    def request_source_data(self, system):
        data = {
            'resolution': system.meta_data['resolution'],
            'encoding': system.meta_data['encoding'],
            'fps': system.meta_data['fps'],
            'raw_fps': system.raw_meta_data['fps'],
            'buffer_size': system.meta_data['buffer_size']
        }

        response = None
        self.hash_codes = None
        while not self.hash_codes or not response:
            self.hash_codes = http_request(system.video_data_source + '/source', method='GET',
                                           data={'data': json.dumps(data)})

            if self.hash_codes:
                response = http_request(system.video_data_source + '/file', method='GET', no_decode=True)

        self.file_name = f'video_source_{system.source_id}_task_{system.task_id}.mp4'

        with open(self.file_name, 'wb') as f:
            f.write(response.content)

    @staticmethod
    def compute_cost_time(system, cost):
        return max(1 / system.meta_data['fps'] * system.meta_data['buffer_size'] - cost, 0)

    def __call__(self, system):
        delay = self.request_source_data(system)

        sleep_time = self.compute_cost_time(system, delay)
        LOGGER.info(f'[Camera Simulation] source {system.source_id}: sleep {sleep_time}s')
        time.sleep(sleep_time)

        system.submit_task_to_controller(self.file_name, self.hash_codes)

        FileOps.remove_file(self.file_name)

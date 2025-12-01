import abc
import threading
import copy
import os
import time

from .base_getter import BaseDataGetter

from core.lib.common import ClassFactory, ClassType, LOGGER, FileOps, Counter, NameMaintainer

__all__ = ('RtspVideoGetter',)


@ClassFactory.register(ClassType.GEN_GETTER, alias='rtsp_video')
class RtspVideoGetter(BaseDataGetter, abc.ABC):
    """
    get video data from rtsp stream (in real time)
    simulate real video source, without accuracy information
    """

    def __init__(self):
        self.file_index = 0

    def generate_and_send_new_task(self, system, file_name, new_task_id, task_dag, meta_data, ):
        LOGGER.debug(f'[Frame Buffer] (source {system.source_id} / task {new_task_id}) ')
        
        new_task = system.generate_task(new_task_id, task_dag, meta_data, file_name, None)
        system.submit_task_to_controller(new_task)
        FileOps.remove_file(file_name)

    def __call__(self, system):
        saved_dir = system.generator_saved_dir
        file_name = saved_dir + f"{self.file_index}.mp4"

        while not os.path.exists(file_name):
            time.sleep(0.5)
            
        LOGGER.info(f"New video file detected: {file_name}")

        # generate tasks in parallel to avoid getting stuck with video compression
        new_task_id = Counter.get_count('task_id')
        threading.Thread(target=self.generate_and_send_new_task,
                         args=(system,
                               file_name,
                               new_task_id,
                               copy.deepcopy(system.task_dag),
                               copy.deepcopy(system.meta_data),)).start()
        
        self.file_index += 1

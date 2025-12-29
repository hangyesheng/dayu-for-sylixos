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
        file_name = system.absolute_saved_dir + f"{self.file_index}.mp4"
        next_file_name = system.absolute_saved_dir + f"{self.file_index + 1}.mp4"

        while not os.path.exists(next_file_name):
            time.sleep(0.05)
        
        # 检测到下一个文件，上传当前已经完整的文件
        LOGGER.info(f"New video file detected: {next_file_name}, submitting task for {file_name}")

        new_task_id = Counter.get_count('task_id')
        threading.Thread(target=self.generate_and_send_new_task,
                         args=(system,
                               system.generator_saved_dir + f"{self.file_index}.mp4",
                               new_task_id,
                               copy.deepcopy(system.task_dag),
                               copy.deepcopy(system.meta_data),)).start()
        
        self.file_index += 1

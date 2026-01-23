import os
import time

from .processor import Processor

from core.lib.content import Task
from core.lib.common import LOGGER, Context
from core.lib.common import ClassFactory, ClassType, VideoOps


@ClassFactory.register(ClassType.PROCESSOR, alias='detector_processor')
class DetectorProcessor(Processor):
    def __init__(self):
        super().__init__()

        self.detector = Context.get_instance('Detector')
    
    def scale_bboxes(self, boxes, original_size, target_size):
        """按比例缩放边界框坐标"""
        orig_w, orig_h = original_size
        target_w, target_h = target_size
        scale_x = target_w / orig_w
        scale_y = target_h / orig_h

        scaled_boxes = []
        for box in boxes:
            x1, y1, x2, y2 = box
            x1 = int(x1 * scale_x)
            y1 = int(y1 * scale_y)
            x2 = int(x2 * scale_x)
            y2 = int(y2 * scale_y)
            x1 = max(0, min(x1, target_w - 1))
            y1 = max(0, min(y1, target_h - 1))
            x2 = max(0, min(x2, target_w - 1))
            y2 = max(0, min(y2, target_h - 1))
            scaled_boxes.append([x1, y1, x2, y2])
        return scaled_boxes
    
    def __call__(self, task: Task):
        data_file_path = os.path.join("/apps", task.get_file_path())

        start_time = time.time()
        result = self.detector(data_file_path, task)
        end_time = time.time()
        LOGGER.debug(f'[Detector Processor] Detection Time: {end_time - start_time:.4f} seconds')

        # 如果未收到任何结果，返回空
        if len(result) == 0:
            LOGGER.critical('ERROR: image list length is 0')
            LOGGER.critical(f'Source: {task.get_source_id()}, Task: {task.get_task_id()}')
            LOGGER.critical(f'file_path: {data_file_path}')
            return None

        start_time = time.time()
        task = self.get_scenario(result, task)

        frame_size = (640, 640)
        target_size = VideoOps.text2resolution('1080p')
        for idx in range(len(result)):
            result[idx] = self.scale_bboxes(result[idx], frame_size, target_size)
            
        task.set_current_content([result])
        end_time = time.time()
        LOGGER.debug(f'[Detector Processor] Post-processing Time: {end_time - start_time:.4f} seconds')

        return task


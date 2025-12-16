import abc

from .base_extraction import BaseExtraction
from core.lib.common import ClassFactory, ClassType, VideoOps

__all__ = ('ObjectSizeExtraction',)


@ClassFactory.register(ClassType.PRO_SCENARIO, alias='obj_size')
class ObjectSizeExtraction(BaseExtraction, abc.ABC):
    def __init__(self):
        super().__init__()

    def __call__(self, result, task):
        obj_size = []
        frame_size = VideoOps.text2resolution(task.get_metadata()['resolution'])
        frame_area = frame_size[0] * frame_size[1]

        for frame_bboxes in result:
            if not frame_bboxes:
                boxes_size = 0.0
            else:
                areas = [((box[2] - box[0]) * (box[3] - box[1])) / frame_area for box in frame_bboxes]
                boxes_size = sum(areas) / len(areas)
            obj_size.append(boxes_size)


        return obj_size

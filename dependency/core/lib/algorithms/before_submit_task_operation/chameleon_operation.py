import abc

from .base_operation import BaseBSTOperation

from core.lib.common import ClassFactory, ClassType, EncodeOps
from core.lib.content import Task

__all__ = ('ChameleonBSTOperation',)


@ClassFactory.register(ClassType.GEN_BSO, alias='chameleon')
class ChameleonBSTOperation(BaseBSTOperation, abc.ABC):
    def __init__(self):
        pass

    def __call__(self, system, compressed_file, hash_codes):
        import cv2
        cap = cv2.VideoCapture(compressed_file)
        ret, frame = cap.read()
        if ret:
            system.temp_encoded_frame = EncodeOps.encode_image(frame)
        else:
            system.temp_encoded_frame = ''

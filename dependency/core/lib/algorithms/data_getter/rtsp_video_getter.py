import abc
import multiprocessing

from .base_getter import BaseDataGetter

from core.lib.common import ClassFactory, ClassType, LOGGER, FileOps

__all__ = ('RtspVideoGetter',)


@ClassFactory.register(ClassType.GEN_GETTER, alias='rtsp_video')
class RtspVideoGetter(BaseDataGetter, abc.ABC):
    """
    get video data from rtsp stream (in real time)
    simulate real video source, without accuracy information
    """

    def __init__(self):
        self.data_source_capture = None
        self.frame_buffer = []

    @staticmethod
    def filter_frame(system, frame):
        return system.frame_filter(system, frame)

    @staticmethod
    def process_frame(system, frame):
        return system.frame_process(system, frame)

    @staticmethod
    def compress_frames(system, frame_buffer):
        assert type(frame_buffer) is list and len(frame_buffer) > 0, 'Frame buffer is not list or is empty'
        return system.frame_compress(system, frame_buffer, system.source_id, system.task_id)

    def get_one_frame(self, system):
        import cv2
        if not self.data_source_capture:
            self.data_source_capture = cv2.VideoCapture(system.video_data_source)

        ret, frame = self.data_source_capture.read()
        first_no_signal = True

        # retry when no video signal
        while not ret:
            if first_no_signal:
                LOGGER.warning(f'No video signal from source {system.source_id}!')
                first_no_signal = False
            self.frame_buffer = []
            self.data_source_capture = cv2.VideoCapture(system.video_data_source)
            ret, frame = self.data_source_capture.read()

        if not first_no_signal:
            LOGGER.info(f'Get video stream data from source {system.source_id}..')

        return frame

    def process_full_frame_buffer(self, system, frame_buffer):
        LOGGER.debug(f'[Frame Buffer] (source {system.source_id} / task {system.task_id}) '
                     f'buffer size: {len(frame_buffer)}')

        frame_buffer = [self.process_frame(system, frame) for frame in frame_buffer]
        compressed_file_path = self.compress_frames(system, frame_buffer)
        system.submit_task_to_controller(compressed_file_path, None)
        FileOps.remove_file(compressed_file_path)

    def __call__(self, system):
        while len(self.frame_buffer) < system.meta_data['buffer_size']:
            frame = self.get_one_frame(system)
            if self.filter_frame(system, frame):
                self.frame_buffer.append(frame)

        multiprocessing.Process(target=self.process_full_frame_buffer,
                                args=(system, self.frame_buffer.copy())).start()

        self.frame_buffer = []

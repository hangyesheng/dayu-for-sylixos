import os

from fastapi import FastAPI, Form, BackgroundTasks

from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import cv2
import json

import uvicorn
import argparse
import time

from core.lib.common import VideoOps, FileOps


class VideoSource:
    def __init__(self, data_root, path, play_mode):
        self.app = FastAPI(routes=[
            APIRoute(f'/{path}/source',
                     self.get_source_data,
                     response_class=JSONResponse,
                     methods=['GET']
                     ),
            APIRoute(f'/{path}/file',
                     self.get_source_file,
                     response_class=FileResponse,
                     methods=['GET']
                     )
        ], log_level='trace', timeout=6000)

        self.app.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_credentials=True,
            allow_methods=["*"], allow_headers=["*"],
        )

        self.data_root = data_root
        self.data_dir = os.path.join(self.data_root, 'frames')

        self.play_mode = play_mode

        self.frame_count = 0

        self.is_end = False

        self.frame_max_count = len(os.listdir(self.data_dir))

        self.file_name = f'{time.time()}.mp4'

    def get_source_data(self, data: str = Form(...)):

        if self.is_end:
            return []

        data = json.loads(data)
        fps = data['fps']
        raw_fps = data['raw_fps']
        fps = min(fps, raw_fps)
        buffer_size = data['buffer_size']
        encoding = data['encoding']
        resolution = data['resolution']

        if fps / raw_fps < 0.5:
            ratio = raw_fps // fps
            frames_index = [self.frame_count + ratio * i for i in range(buffer_size)]
            self.frame_count = frames_index[-1] + ratio
        elif 0.5 <= fps / raw_fps < 1:
            ratio = raw_fps // (raw_fps - fps)
            frames_index = [self.frame_count + i for i in range(buffer_size + (buffer_size - 1) // (ratio - 1))
                            if i % ratio != ratio - 1][:buffer_size]
            self.frame_count = frames_index[-1] + 1
        else:
            frames_index = list(range(self.frame_count, self.frame_count + buffer_size))
            self.frame_count = frames_index[-1] + 1

        self.frame_count = self.frame_count % self.frame_max_count

        if self.play_mode == 'non-cycle' and frames_index[-1] >= self.frame_max_count:
            self.is_end = True
            frames_index = [x for x in frames_index if x < self.frame_max_count]
        else:
            frames_index = [x % self.frame_max_count for x in frames_index]

        resolution = VideoOps.text2resolution(resolution)
        out = cv2.VideoWriter(self.file_name, cv2.VideoWriter_fourcc(*encoding), 30,
                              resolution)

        for i in frames_index:
            frame = cv2.imread(os.path.join(self.data_dir, f'{i}.jpg'))
            frame = cv2.resize(frame, (resolution[0], resolution[1]))
            out.write(frame)

        out.release()

        return frames_index

    def get_source_file(self, backtask: BackgroundTasks):
        return FileResponse(path=self.file_name, filename=self.file_name, media_type='text/plain',
                            background=backtask.add_task(FileOps.remove_file, self.file_name))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=str, required=True)
    parser.add_argument('--address', type=str, required=True)
    parser.add_argument('--play_mode', type=str, required=True)
    args = parser.parse_args()

    port = int(args.address.split(':')[-1].split('/')[0])
    path = args.address.split(':')[-1].split('/')[-1]
    video = VideoSource(args.root, path, args.play_mode)
    uvicorn.run(video.app, host='0.0.0.0', port=port)

ARG REG=docker.io
FROM ${REG}/python:3.8

LABEL authors="skyrim"

ENV TZ=Asia/Shanghai

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /rtsp_server

ENV RTSP_PATH="/rtsp_server"

RUN wget -O mediamtx.tar.gz https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_arm64v8.tar.gz && \
    tar -zxvf mediamtx.tar.gz

RUN sed -i 's/rtspAddress: :8554/rtspAddress: :8000/' mediamtx.yml \
 && sed -i 's/rtpAddress: :8000/rtpAddress: :7000/' mediamtx.yml \
 && sed -i 's/rtcpAddress: :8001/rtcpAddress: :7001/' mediamtx.yml \
 && sed -i 's/writeQueueSize: 512/writeQueueSize: 2048/' mediamtx.yml

CMD ["/bin/bash"]

ARG REG=docker.io
FROM ${REG}/docker:19.03.13-dind

ENV DEBIAN_FRONTEND=noninteractive

ENV DOCKER_HOST=unix:///var/run/docker.sock

RUN apk update && \
    apk add --no-cache ca-certificates curl gnupg bash wget vim git


RUN wget https://github.com/docker/buildx/releases/download/v0.10.4/buildx-v0.10.4.linux-amd64 && \
    mkdir -p /root/.docker/cli-plugins && \
    mv buildx-v0.10.4.linux-amd64 /root/.docker/cli-plugins/docker-buildx && \
    chmod +x /root/.docker/cli-plugins/docker-buildx


CMD ["dockerd-entrypoint.sh"]

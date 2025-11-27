#!/bin/bash

# 定义镜像列表
images=(
    generator
    controller
    car_detection
    face_detection
)

# 遍历镜像列表
for img in "${images[@]}"; do
    echo "Building $img.tar ..."
    cd $img
    rm -rf $img*
    ecsc build . -t $img:latest
    ecsc pack $img -t $img:latest $img.tar
    if [ $? -ne 0 ]; then
        echo "Failed to build $img.tar" >&2
    else
        echo "Successfully builded $img.tar"
    fi
    cd ..
done

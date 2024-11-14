#!/bin/bash

function show_help() {
    echo "Usage: $0 --root <folder> --address <address>"
    echo
    echo "This script continuously streams all video files in the input folder to an RTSP server."
    echo
    echo "Arguments:"
    echo "  --root <folder>:    Path to the folder containing video files."
    echo "  --address <address>: Specific address to append to 'rtsp://127.0.0.1/'."
    echo
    echo "Example:"
    echo "  $0 --root /path/to/your/video/folder --address your_specific_address"
    exit 1
}


input_folder=""
rtsp_address=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --root) input_folder="$2"; shift ;;
        --address) rtsp_address="$2"; shift ;;
        -h|--help) show_help ;;
        *) echo "Unknown parameter passed: $1"; show_help ;;
    esac
    shift
done

if [[ -z "$input_folder" || -z "$rtsp_address" ]]; then
    echo "Error: --root and --address are required."
    show_help
fi

if [[ ! -d "$input_folder" ]]; then
    echo "Error: The specified root path '$input_folder' is not a directory or does not exist."
    exit 1
fi

echo "Starting mediamtx server..."
"$RTSP_PATH"/mediamtx  "$RTSP_PATH"/mediamtx.yml &

rtsp_url="$rtsp_address"

while true; do
    for video_file in "$input_folder"/*; do
        if [[ -f "$video_file" ]]; then
            echo "Streaming $video_file to $rtsp_url"
            ffmpeg -re -i "$video_file" -c:v copy -f rtsp "$rtsp_url"
        fi
    done
done

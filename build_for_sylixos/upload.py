import os
import hashlib
import requests

# 要上传的 tar 文件列表（相对于当前工作目录）
tar_files = [
    "generator/generator.tar",
    "car_detection/car_detection.tar",
    "face_detection/face_detection.tar",
    "controller/controller.tar"
]

BACKEND_ECSM_HOST = "114.212.81.186"
BACKEND_ECSM_PORT = "13001"

API_URL = f"http://{BACKEND_ECSM_HOST}:{BACKEND_ECSM_PORT}/api/v1/image"
DESCRIPTION = "Upload"

def compute_sha1(file_path):
    """计算文件的 SHA-1 哈希值"""
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha1.update(chunk)
    return sha1.hexdigest()

def upload_tar_file(file_path):
    if not os.path.isfile(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return

    # 获取文件大小
    total_size = os.path.getsize(file_path)

    # 计算 SHA-1
    image_hash = compute_sha1(file_path)

    # 读取整个文件内容
    with open(file_path, 'rb') as f:
        file_data = f.read()

    # 构造 headers（整文件上传：1个分片）
    headers = {
        "description": DESCRIPTION,
        "total": "1",
        "index": "1",
        "imageHash": image_hash,
        "totalSize": str(total_size),
        "bufferSize": str(total_size),
        "offset": str(total_size),
        "Content-Type": "application/octet-stream"
    }

    print(f"📤 正在上传: {file_path}")
    print(f"   Hash: {image_hash}")
    print(f"   Size: {total_size} bytes")

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            data=file_data
        )
        response.raise_for_status()
        print(f"✅ 上传成功: {file_path} → {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 上传失败: {file_path} → {e}")
        if hasattr(e.response, 'text'):
            print("   错误详情:", e.response.text)

def main():
    for tar_file in tar_files:
        upload_tar_file(tar_file)

if __name__ == "__main__":
    main()
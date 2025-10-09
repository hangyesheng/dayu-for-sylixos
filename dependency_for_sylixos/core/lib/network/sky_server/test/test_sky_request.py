'''
@Project ：dependency_for_sylixos 
@File    ：test_sky_request.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/25 1:13 
'''
import json

import requests
from core.lib.network.sky_server.sky_request import sky_request, get, post

res = get("http://127.0.0.1:9200/predict")
print(res.text)

res = post("http://127.0.0.1:9200/trans", json={'name': 'skyrim'})
print(res.text)

res = post("http://127.0.0.1:9200/sleep", json={'command': 'pls sleep'})
print(res.text)

res = post("http://127.0.0.1:9200/form", data={'command': 'form sleep', 'name': 'skyrim'})
print(res.text)

f = open('test_server.jsonl', 'rb')
file = {
    "own_file": ("test_server_target.jsonl", f.read(), "application/json")
}
res = sky_request(method='POST', url="http://127.0.0.1:9200/file", files=file)
print(res.text)

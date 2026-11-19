"""Week 1：單次模型呼叫，觀察一次 HTTP Request / Response。

把「請模型回答」還原成一次可觀察的 HTTP 交易：
  - Request  : POST /v1/chat/completions + Authorization / Content-Type headers + JSON body
  - Response : status code（2xx / 4xx）、JSON body
  - 模型回覆 : body 的 choices[0].message.content
  - token 統計: body 的 usage

用法：
  export NVIDIA_API_KEY=...   # 金鑰只從環境變數讀取，不寫進原始碼
  python week1_single_call.py
"""

import json
import os

import requests

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "minimaxai/minimax-m3.1-flash"


def call_model(messages):
  api_key = os.environ["NVIDIA_API_KEY"]
  resp = requests.post(
      API_URL,
      headers={
          "Authorization": f"Bearer {api_key}",
          "Content-Type": "application/json",
      },
      json={
          "model": MODEL,
          "messages": messages,
          "max_tokens": 512,
          "temperature": 1,
          "top_p": 0.95,
      },
      timeout=60,
  )
  print("status:", resp.status_code)
  data = resp.json()
  print(json.dumps(data, ensure_ascii=False, indent=2))
  if resp.ok:
      print("reply:", data["choices"][0]["message"]["content"])
  else:
      print("error:", data.get("error", data))
  return data


if __name__ == "__main__":
  call_model([{"role": "user", "content": "用一句話說明什麼是 HTTP"}])

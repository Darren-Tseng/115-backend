"""Week 1（NVIDIA 官方 openai SDK 寫法）：呼叫同一個 Chat Completions 端點。

與 week1_single_call.py 的差異：
  - week1_single_call.py 用 requests 自己組 HTTP request，可以對照 curl -v 的
    Request Line / Headers / Body 與 Response Status Code。
  - 本檔用 openai SDK，HTTP 細節由 SDK 處理，觀察點改成 SDK 物件：
        串流   : chunk.choices[0].delta.reasoning_content / .delta.content
        非串流 : completion.choices[0].message.content、completion.usage
  - 兩者都是同一個 endpoint（base_url + /chat/completions），只差 Client 是誰。

用法：
  py -3.15 week1_single_call_openai.py               # 串流（預設），看得到 reasoning
  py -3.15 week1_single_call_openai.py --no-stream   # 一次拿到完整回應物件
  $env:NVIDIA_MODEL = "minimaxai/minimax-m3.1-flash" # 換回教材預設模型

金鑰只從環境變數讀取：
  $env:NVIDIA_API_KEY = "nvapi-..."
"""

import argparse
import json
import os

from openai import APIStatusError, OpenAI

BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
QUESTION = "用一句話說明什麼是 HTTP"


def request_kwargs():
  return {
      "model": MODEL,
      "messages": [{"role": "user", "content": QUESTION}],
      "temperature": 1,
      "top_p": 0.95,
      "max_tokens": 4096,
      "seed": 42,
      "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
  }


def make_client():
  return OpenAI(base_url=BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])


def run_stream(client):
  print("model:", MODEL, "(stream=True)")
  answer = []
  in_reasoning = False
  stream = client.chat.completions.create(stream=True, **request_kwargs())
  for chunk in stream:
      if not chunk.choices:
          continue
      delta = chunk.choices[0].delta
      reasoning = getattr(delta, "reasoning_content", None)
      if reasoning:
          if not in_reasoning:
              print("\n[reasoning]")
              in_reasoning = True
          print(reasoning, end="", flush=True)
      if delta.content:
          answer.append(delta.content)
          print(delta.content, end="", flush=True)
  print("\n\nreply:", "".join(answer).strip())


def run_once(client):
  resp = client.chat.completions.create(stream=False, **request_kwargs())
  print("model:", resp.model)
  print("status: 200 (SDK 只有在非 2xx 時才丟出 APIStatusError)")
  print(json.dumps(resp.model_dump(), ensure_ascii=False, indent=2))
  print("reply:", resp.choices[0].message.content)
  if resp.usage:
      print("usage:", json.dumps(resp.usage.model_dump(), ensure_ascii=False))


def main():
  parser = argparse.ArgumentParser(description="Week 1：單次模型呼叫（openai SDK 版）")
  parser.add_argument("--no-stream", action="store_true", help="改用非串流，一次印出完整回應")
  args = parser.parse_args()

  client = make_client()
  try:
      if args.no_stream:
          run_once(client)
      else:
          run_stream(client)
  except APIStatusError as exc:
      # 4xx / 5xx：SDK 會丟出 APIStatusError，狀態碼與 response body 在 exc 上
      print("status:", exc.status_code)
      print("error:", exc.response.text)
      raise SystemExit(1)


if __name__ == "__main__":
  main()

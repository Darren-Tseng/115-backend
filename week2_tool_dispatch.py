"""Week 2：工具描述與分派：模型提出，程式執行。

把一次工具呼叫拆成兩筆可觀察的 API 交易：
  1. 第一次 request 帶 tools（tool schema）→ 回應的 choices[0].message 為
     role: assistant、content: null、tool_calls（模型只「提出建議」，還沒執行）。
  2. 程式依 tool_calls[].function.name / .arguments 真的執行工具（dispatch）。
     注意：arguments 是 JSON 字串，不是 Python dict，要先 json.loads。
  3. 把執行結果包成 role: "tool" 訊息回填 messages，
     tool_call_id 必須和第一次回應的 tool_calls[].id 相同，
     模型才知道這筆結果對應哪個建議。
  4. 第二次 request 不帶 tools → 模型只能根據 tool result 產生最終
     choices[0].message.content。

用法：
  export NVIDIA_API_KEY=...                    # 金鑰只從環境變數讀取，不寫進原始碼
  python3 week2_tool_dispatch.py               # 完整兩步流程
  python3 week2_tool_dispatch.py --url https://example.com
  python3 week2_tool_dispatch.py --record docs/week2-tool-use.json   # 另存完整交易紀錄
  python3 week2_tool_dispatch.py --self-test   # 不呼叫模型、不連網，只驗證 dispatch 與回填

可由環境變數覆寫的參數：
  NVIDIA_MODEL       預設 minimaxai/minimax-m3.1-flash（教材指定）
  NVIDIA_MAX_TOKENS  預設 4096。教材的 512 是給一般短提問；reasoning model
                     的 thinking tokens 也算在 max_tokens 內，塞不下就會
                     finish_reason: length、拿不到 tool_calls，所以這裡留額度。
  NVIDIA_TIMEOUT     預設 120 秒（NVIDIA 共享端點排隊時可調大）
"""

import argparse
import json
import os
import time

import requests

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
TARGET_URL = "https://example.com"

# 工具的 JSON schema：送進 Request Body 的 tools 陣列，模型靠它決定要不要呼叫、
# 呼叫哪個工具、以及怎麼產生 arguments。
HTTP_GET_TOOL = {
    "type": "function",
    "function": {
        "name": "http_get",
        "description": "Fetch a URL with HTTP GET. Return status code and a short body summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Absolute http(s) URL to fetch.",
                }
            },
            "required": ["url"],
        },
    },
}


def env_number(name, default, cast):
  """讀環境變數裡的數字；格式錯誤時給可讀訊息，不要留 traceback。"""
  raw = os.environ.get(name)
  if raw is None or raw == "":
      return default
  try:
      return cast(raw)
  except ValueError:
      raise SystemExit(f"{name} 必須是數字，目前是 {raw!r}")


MODEL = os.environ.get("NVIDIA_MODEL", "minimaxai/minimax-m3.1-flash")
MAX_TOKENS = env_number("NVIDIA_MAX_TOKENS", 4096, int)
TIMEOUT = env_number("NVIDIA_TIMEOUT", 120.0, float)


def user_prompt(url):
  return f"用 http_get 抓取 {url}，然後用一句話說明你看到什麼。"


def call_model(messages, tools=None):
  """送一次 Chat Completions，回傳 (status_code, Response Body 解析後的 dict)。"""
  api_key = os.environ["NVIDIA_API_KEY"]
  payload = {
      "model": MODEL,
      "messages": messages,
      "max_tokens": MAX_TOKENS,
      "temperature": 1,
      "top_p": 0.95,
  }
  if tools is not None:
      payload["tools"] = tools
  try:
      resp = requests.post(
          API_URL,
          headers={
              "Authorization": f"Bearer {api_key}",
              "Content-Type": "application/json",
          },
          json=payload,
          timeout=TIMEOUT,
      )
  except requests.RequestException as exc:
      print(f"網路層失敗（{type(exc).__name__}）：{exc}")
      print("若是 ReadTimeout：NVIDIA 共享端點可能在排隊，")
      print("可改 Model 或把 NVIDIA_TIMEOUT 調大後重試：")
      print("  NVIDIA_MODEL=private/nvidia/nemotron-3.5-super-120b-a12b NVIDIA_MAX_TOKENS=8192 python3 week2_tool_dispatch.py")
      raise SystemExit(1)
  print("status:", resp.status_code)
  try:
      data = resp.json()
  except ValueError:
      print("error: response body 不是 JSON:", resp.text[:200])
      raise SystemExit(1)
  if not resp.ok:
      print("error:", json.dumps(data.get("error", data), ensure_ascii=False))
      raise SystemExit(1)
  return resp.status_code, data


def http_get(url):
  """工具的實作：真的送出 HTTP GET，回傳狀態碼與前 120 字 summary。"""
  if not url.startswith(("http://", "https://")):
      raise ValueError(f"http_get 只接受絕對 http(s) URL: {url!r}")
  resp = requests.get(url, timeout=10)
  return {
      "status_code": resp.status_code,
      "body_summary": resp.text[:120],
  }


def dispatch(name, arguments):
  """照模型提出的 name / arguments 執行工具。

  arguments 是模型回傳的 JSON 字串（不是 dict），所以先 json.loads 再取 url。
  """
  if name != "http_get":
      raise ValueError(f"unknown tool: {name}")
  args = json.loads(arguments)
  return http_get(args["url"])


def build_tool_message(call, result):
  """把執行結果包成 role: "tool" 訊息；tool_call_id 沿用模型提出的 id。"""
  return {
      "role": "tool",
      "tool_call_id": call["id"],
      "content": json.dumps(result, ensure_ascii=False),
  }


def assistant_message_from(first_message):
  """只回填標準欄位。

  模型的 message 可能夾帶非標準欄位（例如 Week 1 看到的 reasoning_content），
  把整包 message 原樣送回第二次 request 可能被 API 以 400 拒絕；
  第二筆 request 只需要 role / content / tool_calls 三個欄位。
  """
  return {
      "role": "assistant",
      "content": first_message.get("content"),
      "tool_calls": first_message["tool_calls"],
  }


def print_message_diagnostics(label, choice, data):
  """印出回應重點：finish_reason、content、usage，並在額度用完時給提示。"""
  message = choice["message"]
  finish_reason = choice.get("finish_reason")
  print(f"{label} finish_reason:", finish_reason)
  print(f"{label} content:", json.dumps(message.get("content"), ensure_ascii=False))
  print(f"{label} usage:", json.dumps(data.get("usage"), ensure_ascii=False))
  if finish_reason == "length":
      print("注意：finish_reason 是 length，代表 max_tokens 用完（含 reasoning tokens）。")
      print("把 NVIDIA_MAX_TOKENS 調大（例如 8192）後重試，否則內容會被截斷。")
  return message


def run_two_step(target_url, record_path=None):
  messages = [{"role": "user", "content": user_prompt(target_url)}]

  print("=== [前置] 第一次 API 請求：帶 tools（Request Body 多一個 tools 欄位）")
  print("model:", MODEL, "/ max_tokens:", MAX_TOKENS, "/ timeout:", TIMEOUT)
  print("送出的 tools:", json.dumps([HTTP_GET_TOOL], ensure_ascii=False))
  first_status, first_data = call_model(messages, tools=[HTTP_GET_TOOL])

  first = first_data["choices"][0]
  print("=== [1/4] 第一次 API 回應：模型提出 tool_calls（尚未執行）")
  print("role:", first["message"].get("role"))
  first_message = print_message_diagnostics("第一次 API 回應", first, first_data)
  print("tool_calls:", json.dumps(first_message.get("tool_calls"), ensure_ascii=False, indent=2))

  if not first_message.get("tool_calls"):
      if first.get("finish_reason") == "length":
          print("沒有拿到 tool_calls，而且是 length 截斷：把 NVIDIA_MAX_TOKENS 調大後重試。")
      else:
          print("沒有拿到 tool_calls；先檢查 user message 有沒有明確要求使用工具、tools 有沒有送出。")
      raise SystemExit(1)

  messages.append(assistant_message_from(first_message))

  executions = []
  for call in first_message["tool_calls"]:
      function = call["function"]
      print()
      print("=== [2/4] 工具執行：name =", function["name"])
      print("模型建議的 arguments（JSON 字串）:", function["arguments"])
      try:
          result = dispatch(function["name"], function["arguments"])
      except (ValueError, KeyError, TypeError, requests.RequestException) as exc:
          print(f"工具執行失敗（{type(exc).__name__}）：{exc}")
          print("Week 2 只驗證成功路徑；Week 4 會把工具錯誤包成 tool message 回填給模型。")
          raise SystemExit(2)
      print("程式實際執行結果:", json.dumps(result, ensure_ascii=False))
      tool_message = build_tool_message(call, result)
      print("回填 tool message：tool_call_id =", tool_message["tool_call_id"])
      messages.append(tool_message)
      executions.append({
          "tool_call_id": call["id"],
          "name": function["name"],
          "arguments_raw": function["arguments"],
          "arguments": json.loads(function["arguments"]),
          "result": result,
      })

  suggested_ids = [call["id"] for call in first_message["tool_calls"]]
  tool_ids = [message["tool_call_id"] for message in messages if message.get("role") == "tool"]
  if tool_ids != suggested_ids:
      raise SystemExit(f"tool_call_id 對不上：assistant 建議 {suggested_ids} / 回填 {tool_ids}")

  print()
  print("=== [3/4] 第二次 API 請求：不帶 tools，回填 tool result")
  print("assistant 提出的 tool_call_id:", suggested_ids)
  print("回填的 tool_call_id:", tool_ids, "→ 相同，模型可對應")
  print("送出的 messages:", json.dumps(messages, ensure_ascii=False, indent=2))
  second_status, second_data = call_model(messages)

  second = second_data["choices"][0]
  print("=== [4/4] 第二次 API 回應：最終 content")
  second_message = print_message_diagnostics("第二次 API 回應", second, second_data)
  if second_message.get("content") is None:
      print("注意：第二次回應的 content 是 null（可能被 length 截斷）；先看 finish_reason 與 usage。")
  if second_message.get("tool_calls"):
      print("注意：第二次又出現 tool_calls，代表任務需要更多步驟；Week 3 會把這兩步接成執行迴圈。")

  if record_path:
      directory = os.path.dirname(record_path)
      if directory:
          os.makedirs(directory, exist_ok=True)
      record = {
          "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
          "api_url": API_URL,
          "model": MODEL,
          "max_tokens": MAX_TOKENS,
          "timeout_seconds": TIMEOUT,
          "first_request": {
              "messages": [{"role": "user", "content": user_prompt(target_url)}],
              "tools": [HTTP_GET_TOOL],
          },
          "first_response": {
              "status": first_status,
              "message": first_message,
              "finish_reason": first.get("finish_reason"),
              "usage": first_data.get("usage"),
          },
          "tool_execution": executions,
          "second_request": {
              "messages": messages,
              "tools": None,
          },
          "second_response": {
              "status": second_status,
              "message": second_message,
              "finish_reason": second.get("finish_reason"),
              "usage": second_data.get("usage"),
          },
      }
      with open(record_path, "w", encoding="utf-8") as handle:
          json.dump(record, handle, ensure_ascii=False, indent=2)
      print("已寫出完整交易紀錄:", record_path)


class _FakeResponse:
  """self-test 用的假 HTTP 回應，不連網。"""

  status_code = 200
  text = "<!doctype html><html><head><title>Example Domain</title></head></html>"


def run_self_test():
  """不呼叫模型、不連網：驗證 arguments 解析、dispatch、tool_call_id 回填。"""
  original_get = requests.get
  requests.get = lambda url, timeout: _FakeResponse()
  try:
      call = {
          "id": "call_self_test_1",
          "type": "function",
          "function": {
              "name": "http_get",
              "arguments": json.dumps({"url": "https://example.com"}),
          },
      }
      result = dispatch(call["function"]["name"], call["function"]["arguments"])
      assert result["status_code"] == 200, result
      assert result["body_summary"].startswith("<!doctype html>"), result

      tool_message = build_tool_message(call, result)
      assert tool_message["role"] == "tool", tool_message
      assert tool_message["tool_call_id"] == call["id"], tool_message
      assert json.loads(tool_message["content"]) == result, tool_message

      assistant_message = assistant_message_from({
          "role": "assistant",
          "content": None,
          "reasoning_content": "這段不該被回填",
          "tool_calls": [call],
      })
      assert set(assistant_message) == {"role", "content", "tool_calls"}, assistant_message

      try:
          dispatch("unknown_tool", "{}")
      except ValueError:
          pass
      else:
          raise AssertionError("unknown tool 應該丟出 ValueError")

      try:
          dispatch("http_get", json.dumps({"url": "file:///etc/passwd"}))
      except ValueError:
          pass
      else:
          raise AssertionError("非 http(s) URL 應該丟出 ValueError")

      try:
          dispatch("http_get", "{not valid json}")
      except ValueError:
          pass
      else:
          raise AssertionError("arguments 不是合法 JSON 應該丟出 ValueError")
  finally:
      requests.get = original_get

  print("self-test ok：arguments JSON 字串可解析、dispatch 執行成功、")
  print("tool_call_id 回填一致、非標準欄位不會被回填、未知工具/非 http(s) URL/壞 JSON 被拒絕")


def main():
  parser = argparse.ArgumentParser(description="Week 2：工具描述與分派（模型提出，程式執行）")
  parser.add_argument("--url", default=TARGET_URL, help="要讓模型用 http_get 抓取的 URL")
  parser.add_argument("--record", metavar="PATH", help="把兩次 API 交易與工具執行結果寫成 JSON")
  parser.add_argument("--self-test", action="store_true", help="不呼叫模型，只驗證 dispatch 與回填")
  args = parser.parse_args()

  if args.self_test:
      run_self_test()
      return

  if not os.environ.get("NVIDIA_API_KEY"):
      print("缺少 NVIDIA_API_KEY：金鑰只從環境變數讀取，不寫進原始碼、也不 commit。")
      raise SystemExit(1)

  run_two_step(args.url, args.record)


if __name__ == "__main__":
  main()

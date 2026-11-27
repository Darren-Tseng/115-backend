# Week 2 觀察紀錄：工具描述與分派（模型提出，程式執行）

- 執行時間：2026-11-27 11:17:49（Asia/Taipei）
- Client：`week2_tool_dispatch.py --record docs/week2-tool-use.json`（`requests`）
- Endpoint：`POST https://integrate.api.nvidia.com/v1/chat/completions`
- 送出 model：`minimaxai/minimax-m3.1-flash`（教材指定 model，本次沒遇到排隊）
- 參數：`max_tokens: 4096`、`temperature: 1`、`top_p: 0.95`、timeout 120 秒
- user message：`用 http_get 抓取 https://example.com，然後用一句話說明你看到什麼。`
- tools：`http_get`（參數 `url: string`，`required: ["url"]`）

## 四列對照表（作業要求）

| 步驟 | 模型建議 | 程式實際執行 |
| --- | --- | --- |
| 第一次 API 回應 | `name: http_get`、`arguments: {"url":"https://example.com"}`（JSON 字串；`finish_reason: tool_calls`、`content: null`） | 尚未執行；只收到建議 |
| 工具執行 | 無 | `status_code: 200`、`body_summary` 前 120 字（見下方） |
| 第二次 API 請求 | 無 | `role: "tool"` 訊息的 `tool_call_id` = `call-6f6561aa-dfd8-4810-82c0-1537f35f76c5`，與第一次的 id 相同 |
| 第二次 API 回應 | 無 | `choices[0].message.content`：一句話說明（見下方） |

工具執行實際拿到的 `body_summary`（`resp.text[:120]`，共 120 字）：

```text
<!doctype html><html lang=en><head><meta charset=utf-8><link rel=icon href=data:,><meta name=viewport content="width=dev
```

## 第一次 API 回應（status 200）：模型提出 tool_calls

```json
{
  "content": null,
  "refusal": null,
  "tool_calls": [
    {
      "id": "call-6f6561aa-dfd8-4810-82c0-1537f35f76c5",
      "type": "function",
      "function": {
        "name": "http_get",
        "arguments": "{\"url\":\"https://example.com\"}"
      }
    }
  ],
  "role": "assistant",
  "reasoning_content": "The user wants me to fetch https://example.com using http_get, then describe in one sentence what I saw. Simple task. Let me call the tool."
}
```

重點：

- `content` 是 `null`：這個階段模型還沒回答問題，只提出要呼叫哪個工具。
- `tool_calls[0].id` = `call-6f6561aa-dfd8-4810-82c0-1537f35f76c5`：程式等一下要用同一個 id 回填結果。
- `tool_calls[0].function.arguments` 是 **JSON 字串** `{"url":"https://example.com"}`，
  不是 Python dict；`dispatch()` 要先 `json.loads` 才拿得到 `url`。
- `finish_reason` = `tool_calls`，代表模型停在「等你執行工具」的狀態。
- `usage`：prompt 446 / completion 64（其中 reasoning 34）/ total 510。
- 模型另外回了非標準欄位 `reasoning_content`（英文思考過程）；第二次 request
  只回填 `role` / `content` / `tool_calls`，不把這個欄位原樣送回去。

## 工具執行：程式做的兩件事（作業表格第 2 列）

1. `dispatch(name, arguments)`：比對 `name == "http_get"`，`json.loads(arguments)` 後取 `url`。
2. `http_get(url)`：真的發出 `requests.get(url, timeout=10)`，回傳：

```json
{
  "status_code": 200,
  "body_summary": "<!doctype html><html lang=en><head><meta charset=utf-8><link rel=icon href=data:,><meta name=viewport content=\"width=dev"
}
```

模型建議的是「要抓哪個 URL」；程式實際得到的是「HTTP 狀態碼 + 前 120 字 body」。
兩者不同：前者是建議（尚未發生），後者是執行後的事實。

## 第二次 API 請求：不帶 tools，回填 tool message（作業表格第 3 列）

```json
[
  {
    "role": "user",
    "content": "用 http_get 抓取 https://example.com，然後用一句話說明你看到什麼。"
  },
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call-6f6561aa-dfd8-4810-82c0-1537f35f76c5",
        "type": "function",
        "function": {
          "name": "http_get",
          "arguments": "{\"url\":\"https://example.com\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call-6f6561aa-dfd8-4810-82c0-1537f35f76c5",
    "content": "{\"status_code\": 200, \"body_summary\": \"<!doctype html><html lang=en><head><meta charset=utf-8><link rel=icon href=data:,><meta name=viewport content=\\\"width=dev\"}"
  }
]
```

- `messages` 順序是 `user → assistant（content: null + tool_calls）→ tool`。
- `tool` 訊息的 `tool_call_id` = `call-6f6561aa-dfd8-4810-82c0-1537f35f76c5`，和第一次 `tool_calls[0].id` 完全相同；
  模型靠這個 id 把結果對應回它剛才的建議。
- 第二筆 request **沒有** `tools` 欄位（record 的 `second_request.tools` 是 `null`）。

## 第二次 API 回應（status 200）：最終 content（作業表格第 4 列）

```text
http_get 回傳狀態碼 200，內容是一段標準 HTML（`<!doctype html>`、`lang="en"`、utf-8 編碼與 viewport 等 meta 標籤），即 example.com 那個用於示範用途的佔位頁面（工具回傳的 body 摘要有所截斷）。
```

- `finish_reason` = `stop`，`content` 有值（非 null），這次沒有再出現 `tool_calls`。
- `usage`：prompt 292 / completion 546（其中 reasoning 475）/ total 838。
- 若第二次又出現 `tool_calls`，不是錯誤，而是任務需要更多步驟；Week 3 會把兩步接成迴圈。

## 觀察：為什麼 `max_tokens` 用 4096，而不是教材的 512

| 呼叫 | prompt tokens | completion tokens | 其中 reasoning | 512 夠不夠 |
| --- | --- | --- | --- | --- |
| 第一次（產生 tool_calls） | 446 | 64 | 34 | 夠 |
| 第二次（整理最終回答） | 292 | 546 | 475 | **不夠**（546 > 512，會被截成 `finish_reason: length`） |

教材註明 `max_tokens` 要同時容納「思考 + 最終回答」，短提問先設 512。本次第二次回應
光是 reasoning 就 475 tokens、加回答 546 tokens，512 會在拿到完整回答前被切斷。
因此程式預設 `max_tokens: 4096`，可用 `NVIDIA_MAX_TOKENS` 覆寫；若看到
`finish_reason: length`，程式也會提示把額度調大。

## 自我檢查（教材四問）

1. **模型建議的 URL 在哪裡？**
   在第一次回應的 `choices[0].message.tool_calls[0].function.arguments`，內容是 JSON 字串
   `{"url":"https://example.com"}`；程式要 `json.loads` 才拿得到 `url`。
2. **程式用哪個函式真的發出請求？**
   `dispatch()` 依 name 找到工具後呼叫 `http_get(url)`，由 `requests.get` 真的發出 HTTP GET；
   模型本身沒有連網能力。
3. **`tool_call_id` 對不上會發生什麼？**
   模型無法把 tool result 對應到剛才的建議。API 通常回 400（`tool` 訊息必須對應
   `assistant` 的 `tool_calls[].id`）；本程式在送出第二次 request 前就先比對
   `assistant` 的 id 與回填的 id，不一致就直接中止，避免送出註定失敗的請求。
4. **為什麼第二次呼叫不帶 tools？**
   工具已經執行完，模型這一步只需要「根據 tool result 用文字回答」，不需要再提新建議；
   不帶 tools 也避免它又產生 `tool_calls`，並省下 tools schema 的 prompt tokens
   （本次 446 → 292）。

## 邊界與失敗處理

- **id 對不上**：送出第二次 request 前有斷言（`tool_ids != suggested_ids` 就中止）。
- **模型給的 arguments 壞掉**：`json.loads` 失敗、缺 `url`、或 URL 不是 http(s) 時，
  `dispatch()` 丟出 `ValueError`，程式印出可讀訊息（Week 4 才會把工具錯誤回填給模型）。
- **額度用完**：`finish_reason: length` 且沒有 `tool_calls` 時，程式提示調高
  `NVIDIA_MAX_TOKENS`，而不是只說「沒有拿到 tool_calls」。
- **網路層錯誤**：`requests` 的 `RequestException`（含端點排隊造成的 timeout）會被轉成
  可讀訊息 + 備援 model 指令，不會只丟 traceback。
- **非標準欄位**：`assistant` 訊息只回填 `role` / `content` / `tool_calls`，
  `reasoning_content` 不原樣送回。

## 重現方式

```bash
cd "/Users/cengyoulun/Documents/雲科大/三上/網頁程式設計/115-backend"
source .venv/bin/activate
set -a; . ./.env; set +a

# 完整兩步流程 + 留下交易紀錄
python week2_tool_dispatch.py --record docs/week2-tool-use.json

# 只驗證 dispatch / 回填邏輯（不呼叫模型、不連網）
python week2_tool_dispatch.py --self-test
```

完整原始交易紀錄：[docs/week2-tool-use.json](week2-tool-use.json)（含兩次 request / response
與工具執行結果，不含 API key 或 Authorization header）。

## 結論

- 一次工具呼叫是 **兩筆 API 交易**：第一筆模型提出 `tool_calls`（content 為 null），
  第二筆模型根據 `role: "tool"` 的結果產出最終 `content`。
- 模型只負責「建議 name / arguments」；`json.loads`、真的發出 HTTP、以及用相同
  `tool_call_id` 回填，全都是程式的責任。
- 第二筆 request 不帶 `tools`，模型看不到工具，就只能根據 tool result 回答；
  這也是為什麼 tool result 的內容與 id 對應必須正確。

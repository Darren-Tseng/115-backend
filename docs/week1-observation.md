# Week 1 觀察紀錄：一次模型呼叫的 Request / Response

- 執行時間：2026-11-20
- Client：`week1_single_call_openai.py --no-stream`（openai SDK）
- Endpoint：`POST https://integrate.api.nvidia.com/v1/chat/completions`
- 送出 model：`private/nvidia/nemotron-3.5-super-120b-a12b`
- 問題（`messages[0]`）：`用一句話說明什麼是 HTTP`

## 成功案例：status 200

### 回傳重點欄位

| 欄位 | 值 |
| --- | --- |
| Response Status Code | `200` |
| `choices[0].finish_reason` | `stop` |
| `choices[0].message.role` | `assistant` |
| `choices[0].message.content` | `HTTP（超文字傳輸協議）是一種用於在網頁瀏覽器與伺服器之間傳輸網頁等超文本資料的應用層通訊協議。` |
| `choices[0].message.reasoning_content` | 有值（英文思考過程，本次 337 tokens） |
| `usage.prompt_tokens` | 27 |
| `usage.completion_tokens` | 393（其中 `completion_tokens_details.reasoning_tokens` = 337） |
| `usage.total_tokens` | 420 |

### 對照 `curl -v` 的位置

| HTTP 元素 | 本次觀察 |
| --- | --- |
| Request Line | `POST /v1/chat/completions HTTP/2` |
| Request Headers | `Authorization: Bearer ***`（已遮蔽）、`Content-Type: application/json` |
| Request Body | `model`、`messages`（另含 `temperature: 1`、`top_p: 0.95`、`max_tokens: 4096`、`seed: 42`） |
| Response Status Code | `200`，程式印出的 `status: 200` |
| Response Body | 上表 JSON（NVIDIA 另回 `metadata`、`moderation` 等擴充欄位） |
| 模型回覆文字 | `choices[0].message.content`，程式印出的 `reply:` |
| token 統計 | `usage`，程式印出的 `usage:` |

### 觀察：回答只有一句，`completion_tokens` 卻有 393

- `completion_tokens` 393 = `reasoning_tokens` 337 + 實際回答文字約 56 tokens。
- 模型把思考過程放在非標準欄位 `message.reasoning_content`，最終答案才放 `message.content`。
- 所以 Week 1 只取 `choices[0].message.content` 是正確的；`reasoning_content` 是模型額外
  提供的欄位，不是要繳交的答案，但可以用來解釋「為什麼一個問題會花 420 tokens」。

## 失敗案例：status 403

刻意把 `Authorization` 換成無效金鑰：

```text
status: 403
error: {"status":403,"title":"Forbidden","detail":"Authorization failed"}
```

判定：

- `4xx` 表示 Client 送出的 request 有問題，不是伺服器壞掉。
- 這次是 Request Header 的 `Authorization` 憑證錯誤。NVIDIA 這個端點回 `403`
  （而不是教材表格寫的 `401`），仍屬「認證類」錯誤。
- 對照組：若 `model` 名稱錯誤或必要欄位缺失，會是 `400` / `404`，且 body 會指出被拒絕的欄位，
  與本案例的 `Authorization failed` 不同。

## 重現方式

```powershell
# 金鑰只放環境變數，不寫進程式
$env:NVIDIA_API_KEY = "nvapi-..."

# 成功案例
py -3.15 week1_single_call_openai.py --no-stream

# 失敗案例（故意用錯誤金鑰）
$env:NVIDIA_API_KEY = "nvapi-invalid-test-key"
py -3.15 week1_single_call_openai.py --no-stream
```

## 結論

- 狀態碼看 Response Line（`< HTTP/2 200`）；模型回覆看 `choices[0].message.content`；
  送出的任務看 Request Body 的 `messages`；成本看 `usage`。
- `2xx` 代表 request 被接受並處理；`4xx` 要先從錯誤訊息判斷是認證、model 名稱還是 JSON 欄位問題。

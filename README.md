# 115-backend

網頁程式設計 115 —— 「從模型 API 到執行迴圈：六週實作」作業 repo。

用 OpenAI 相容的 Chat Completions API，從單次呼叫一路實作到可追蹤的工具執行迴圈。

## 進度

| 週次 | 主題 | 檔案 | 狀態 |
| --- | --- | --- | --- |
| Week 1 | 第一次模型呼叫：在 `curl -v` 裡看見回覆 | `week1_single_call.py`、`week1_single_call_openai.py`、[觀察紀錄](docs/week1-observation.md) | ✅ |
| Week 2 | 工具描述與分派 | `week2_tool_dispatch.py` | ⬜ |
| Week 3 | 執行迴圈與對話狀態 | `week3_agent_loop.py` | ⬜ |
| Week 4 | 多工具與錯誤回填 | `week4_multi_tools.py` | ⬜ |
| Week 5 | 執行紀錄與邊界 | trace 檔 | ⬜ |
| Week 6 | 整合驗收 | `harness.py` | ⬜ |

## 環境

- Python 3
- 依賴套件：`requests`、`openai`

```bash
pip install -r requirements.txt
```

## 設定 API key

金鑰只放在環境變數，不寫進原始碼、也不 commit。

```bash
export NVIDIA_API_KEY=YOUR_NVIDIA_API_KEY
```

（Windows PowerShell：`$env:NVIDIA_API_KEY = "YOUR_NVIDIA_API_KEY"`）

也可以放在 `.env`，但要確認 `.env` 已在 `.gitignore` 內；請自行載入，程式只讀環境變數。

## Week 1：單次模型呼叫

同一個 endpoint，兩種 Client 寫法：

| 檔案 | Client | 觀察重點 |
| --- | --- | --- |
| `week1_single_call.py` | `requests` | 對照 `curl -v`：status code、完整 JSON、`choices[0].message.content` |
| `week1_single_call_openai.py` | 官方 `openai` SDK | SDK 物件：`message.content`、`delta.reasoning_content`、`usage` |

### 教材版：`week1_single_call.py`

```bash
python week1_single_call.py
```

預設 model 是教材指定的 `minimaxai/minimax-m3.1-flash`；可用環境變數換 model：

```bash
NVIDIA_MODEL="private/nvidia/nemotron-3.5-super-120b-a12b" python week1_single_call.py
```

### 官方 SDK 版：`week1_single_call_openai.py`

```bash
python week1_single_call_openai.py              # 串流（預設）
python week1_single_call_openai.py --no-stream  # 非串流，印出完整回應
```

預設 model 是 **本機實測可用** 的 `private/nvidia/nemotron-3.5-super-120b-a12b`
（2026-11-20 實測 status 200）。NVIDIA 官方模型頁的 id 是
`nvidia/nemotron-3.5-super-vl-120b-a12b`；要換回教材 model 時：

```bash
NVIDIA_MODEL="minimaxai/minimax-m3.1-flash" python week1_single_call_openai.py
```

想看 SDK 底層實際送出的 HTTP request/response：

```bash
OPENAI_LOG=debug python week1_single_call_openai.py
```

### 對照 `curl -v` 的觀察位置

| 你要指出的東西 | 在哪裡看 |
| --- | --- |
| Request Line | `> POST /v1/chat/completions HTTP/2` |
| Request Headers | `Authorization: Bearer ***`、`Content-Type: application/json` |
| Request Body | `model` 與 `messages`（即 `-d` 的內容） |
| Response Status Code | `< HTTP/2 200`，程式印出的 `status:` |
| 模型回覆文字 | `choices[0].message.content`，程式印出的 `reply:` |
| token 統計 | `usage.prompt_tokens / completion_tokens / total_tokens` |

狀態碼非 2xx 時先看 status 再看 response body 的 `error` 欄位，判斷責任在 request 的哪一部分：

| 情境 | 實際觀察 |
| --- | --- |
| `Authorization` 缺少或錯誤 | `status: 403`，body 為 `{"detail": "Authorization failed"}`（NVIDIA 回 403 而不是 401） |
| `model` 名稱錯誤或欄位缺失 | `400` / `404`，body 指出被拒絕的欄位 |

### Week 1 實測結果

2026-11-20 以 `private/nvidia/nemotron-3.5-super-120b-a12b` 執行 `--no-stream`：

```text
status: 200
finish_reason: stop
reply: HTTP（超文字傳輸協議）是一種用於在網頁瀏覽器與伺服器之間傳輸網頁等超文本資料的應用層通訊協議。
usage: prompt_tokens 27 / completion_tokens 393（其中 reasoning_tokens 337）/ total_tokens 420
```

完整欄位對照與失敗案例（`403 Authorization failed`）見
[Week 1 觀察紀錄](docs/week1-observation.md)。

## 安全提醒

`Authorization` header 會帶出金鑰。貼出 `curl -v` 紀錄、截圖或分享檔案前先遮蔽；
若懷疑外洩，到 NVIDIA 後台撤銷並重新產生。

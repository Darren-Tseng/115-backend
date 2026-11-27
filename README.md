# 115-backend

網頁程式設計 115 —— 「從模型 API 到執行迴圈：六週實作」作業 repo。

用 OpenAI 相容的 Chat Completions API，從單次呼叫一路實作到可追蹤的工具執行迴圈。

## 進度

| 週次 | 主題 | 檔案 | 狀態 |
| --- | --- | --- | --- |
| Week 1 | 第一次模型呼叫：在 `curl -v` 裡看見回覆 | `week1_single_call.py`、`week1_single_call_openai.py`、[觀察紀錄](docs/week1-observation.md) | ✅ |
| Week 2 | 工具描述與分派：模型提出，程式執行 | `week2_tool_dispatch.py`、[觀察紀錄](docs/week2-observation.md) | ✅ |
| Week 3 | 執行迴圈與對話狀態 | `week3_agent_loop.py` | ⬜ |
| Week 4 | 多工具與錯誤回填 | `week4_multi_tools.py` | ⬜ |
| Week 5 | 執行紀錄與邊界 | trace 檔 | ⬜ |
| Week 6 | 整合驗收 | `harness.py` | ⬜ |

## 環境

- Python 3（本機以 Python 3.13 建立 `.venv`）
- 依賴套件：`requests`、`openai`

建立並啟用虛擬環境（repo 已建立過 `.venv`，重 clone 或換機器才需要重做；`.venv/` 已被 `.gitignore` 忽略）：

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell：.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

之後在專案根目錄先 `source .venv/bin/activate`，或直接指定直譯器：`.venv/bin/python week2_tool_dispatch.py`。

## 設定 API key

金鑰只放在環境變數，不寫進原始碼、也不 commit。

```bash
export NVIDIA_API_KEY=YOUR_NVIDIA_API_KEY
```

（Windows PowerShell：`$env:NVIDIA_API_KEY = "YOUR_NVIDIA_API_KEY"`）

也可以放在 `.env`（repo 已提供 `.env.example` 範本，`.env` 已在 `.gitignore` 內）：

```bash
cp .env.example .env    # 編輯 .env，填入 NVIDIA_API_KEY=nvapi-...
set -a; . ./.env; set +a   # 把 .env 載入目前 shell（Windows 請自行設定環境變數）
```

程式只從環境變數讀金鑰，不會讀檔，也不需要把金鑰寫進原始碼。

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

### 為什麼用 `private/nvidia/nemotron-3.5-super-120b-a12b`

教材指定的 `minimaxai/minimax-m3.1-flash` 在 NVIDIA playground 顯示
`There are 1138 requests in the queue...` —— 這是共享端點的容量排隊，不是 key 或
程式錯誤；request 會卡在佇列裡，實務上容易直接撞到 client timeout。
本週因此改用 `private/nvidia/nemotron-3.5-super-120b-a12b` 完成觀察：
同一個 endpoint、同一組參數，HTTP 層與 `choices[0].message.content` 的位置完全相同。
要用教材模型時設定 `NVIDIA_MODEL` 即可（排隊緩解後再切回）。

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

## Week 2：工具描述與分派（模型提出，程式執行）

把一次工具呼叫拆成兩筆 API 交易：第一次帶 `tools` 取得 `tool_calls`（模型只提出建議），
程式依 `name` / `arguments` 真的執行工具，再用 `role: "tool"` + 相同 `tool_call_id` 回填，
第二次「不帶 tools」取得最終 `content`。

```bash
source .venv/bin/activate
set -a; . ./.env; set +a

python week2_tool_dispatch.py                                    # 完整兩步流程
python week2_tool_dispatch.py --record docs/week2-tool-use.json  # 另存完整交易紀錄
python week2_tool_dispatch.py --self-test                        # 不呼叫模型，只驗證 dispatch / 回填
```

| 檔案 | 用途 |
| --- | --- |
| `week2_tool_dispatch.py` | 兩步 tool-use 流程：tool schema、dispatch、tool message 回填、四列（\[1/4\]～\[4/4\]）輸出 |
| `docs/week2-observation.md` | 一次完整 tool-use 觀察紀錄（四列對照表、自我檢查） |
| `docs/week2-tool-use.json` | 程式輸出的兩次請求／回應原始紀錄（不含金鑰） |

### 模型與參數

- model：教材指定的 `minimaxai/minimax-m3.1-flash`（2026-11-27 實測可用，這次沒遇到排隊）；
  可用 `NVIDIA_MODEL` 覆寫，排隊時切 Week 1 的備援 model：
  `NVIDIA_MODEL=private/nvidia/nemotron-3.5-super-120b-a12b python week2_tool_dispatch.py`。
- `max_tokens` 預設 **4096**（`NVIDIA_MAX_TOKENS` 可覆寫）。教材建議的 512 對一般短問答夠用，
  但 reasoning model 的 thinking tokens 也算在內：本次第二次回應用了 546 completion tokens
  （其中 475 是 reasoning），512 會在拿到完整回答前被截斷成 `finish_reason: length`。
- 其他參數：`temperature: 1`、`top_p: 0.95`；`NVIDIA_TIMEOUT` 預設 120 秒。

### Week 2 實測結果

2026-11-27 以 `minimaxai/minimax-m3.1-flash` 執行 `--record`，兩次呼叫都 `status: 200`：

| 步驟 | 觀察 |
| --- | --- |
| 第一次 API 回應 | `finish_reason: tool_calls`、`content: null`、`tool_calls[0].id = call-6f6561aa-…`、`arguments: {"url":"https://example.com"}`（JSON 字串） |
| 工具執行 | `status_code: 200`、`body_summary` 前 120 字為 `<!doctype html>…` |
| 第二次 API 請求 | `role: "tool"`、`tool_call_id` 與第一次相同、不帶 `tools` |
| 第二次 API 回應 | `finish_reason: stop`，`content` 為一句話說明（HTTP 200 + HTML） |

完整欄位（含 `usage`、第二次 request 的 messages）、自我檢查與失敗邊界見
[Week 2 觀察紀錄](docs/week2-observation.md)。

## 安全提醒

`Authorization` header 會帶出金鑰。貼出 `curl -v` 紀錄、截圖或分享檔案前先遮蔽；
若懷疑外洩，到 NVIDIA 後台撤銷並重新產生。

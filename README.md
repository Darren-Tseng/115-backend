# 115-backend

網頁程式設計 115 —— 「從模型 API 到執行迴圈：六週實作」作業 repo。

用 OpenAI 相容的 Chat Completions API，從單次呼叫一路實作到可追蹤的工具執行迴圈。

## 進度

| 週次 | 主題 | 檔案 | 狀態 |
| --- | --- | --- | --- |
| Week 1 | 第一次模型呼叫：在 `curl -v` 裡看見回覆 | `week1_single_call.py` | ✅ |
| Week 2 | 工具描述與分派 | `week2_tool_dispatch.py` | ⬜ |
| Week 3 | 執行迴圈與對話狀態 | `week3_agent_loop.py` | ⬜ |
| Week 4 | 多工具與錯誤回填 | `week4_multi_tools.py` | ⬜ |
| Week 5 | 執行紀錄與邊界 | trace 檔 | ⬜ |
| Week 6 | 整合驗收 | `harness.py` | ⬜ |

## 環境

- Python 3
- 依賴套件：`requests`

```bash
pip install -r requirements.txt
```

## Week 1：單次模型呼叫

### 設定 API key

金鑰只放在環境變數，不寫進原始碼、也不 commit。

```bash
export NVIDIA_API_KEY=YOUR_NVIDIA_API_KEY
```

（Windows PowerShell：`$env:NVIDIA_API_KEY = "YOUR_NVIDIA_API_KEY"`）

也可以放在 `.env`，但要確認 `.env` 已在 `.gitignore` 內。

### 執行

```bash
python week1_single_call.py
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

狀態碼非 2xx 時（例如 `401` 認證錯誤、`400`/`404` model 名稱或欄位錯誤），
先看 status 再看 response body 的 `error` 欄位判斷責任在 request 的哪一部分。

## 安全提醒

`Authorization` header 會帶出金鑰。貼出 `curl -v` 紀錄、截圖或分享檔案前先遮蔽；
若懷疑外洩，到 NVIDIA 後台撤銷並重新產生。

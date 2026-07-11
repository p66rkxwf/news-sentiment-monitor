# 模型選型依據（Phase 4）

> 對應申請表預期成果「客觀的模型選型依據」：不只看分數，綜合
> 「Macro F1 提升幅度 vs 推論成本」給出選型理由。數據見 [model_comparison.md](model_comparison.md)。

## 選型結果：**BERT（fine-tuned，lr=2e-5、max_length=64）**

## 選型方法

1. **以驗證集 Macro F1 選型、測試集只做最終確認**——用測試集挑模型會產生樂觀偏差，
   測試集數字只能報告、不能參與決策。
2. 對驗證集最佳的 transformer（BERT）做超參數搜尋（lr ∈ {1e-5, 2e-5, 3e-5} ×
   max_length ∈ {64, 128}，`python -m newssent.ml.tune --model bert`），
   仍以驗證集選出最佳組合。
3. Macro F1 為主指標：PhraseBank 的 neutral 佔約六成，Accuracy 會被「全猜 neutral」
   灌水（多數類基線 Accuracy 即達 0.59）。

## 比較與取捨（2026-07-11）

| 候選 | 驗證 F1 | 測試 F1 | GPU ms/句 | CPU ms/句 | 大小 | 評語 |
|---|---|---|---|---|---|---|
| **bert（選定）** | **0.8542** | **0.8458** | 0.37 | 13.9 | 439MB | 驗證/測試雙冠；GPU 部署下推論成本可忽略 |
| roberta | 0.8451 | 0.8455 | 0.84 | 15.3 | 502MB | 測試 F1 與 bert 相當，但驗證 F1 較低、模型更大 |
| distilbert | 0.8395 | 0.8129 | 0.89 | 7.4 | 269MB | CPU 推論快近 2 倍；無 GPU 的部署環境首選 |
| tfidf_lr | 0.7121 | 0.7240 | — | 0.07 | 0.5MB | 極端資源受限時的底線方案 |
| svm | 0.7079 | 0.7286 | — | 0.32 | 1.6MB | 同上；兩基線已被 transformer 拉開 12 個百分點 |

## 推論成本的兩種部署場景（PLAN.md 要求 GPU/CPU 兩欄分列的原因）

- **部署機有 GPU（本專題 demo 環境）**：BERT 單句 0.37ms，一次分析 20 則新聞
  約 7ms——推論成本完全不構成選型壓力，直接選 F1 最高者。
- **部署到無 GPU 環境**：BERT 單句約 14ms（20 則 ≈ 0.3 秒）仍可接受；若要更快，
  DistilBERT 以犧牲 3.3 個百分點測試 F1 換取近 2 倍 CPU 速度與 60% 的模型體積，
  是合理的替代選項。

## 相對基線的提升幅度

fine-tuned BERT 測試 Macro F1 **0.8458** vs 最佳基線 svm **0.7286**：
提升 **+11.7 個百分點**（相對錯誤率下降約 43%），符合 PLAN.md
「transformer 必須明顯超越基線才有部署價值」的門檻，也落在文獻上
PhraseBank fine-tuned BERT 類模型 0.85–0.95 的合理區間下緣
（本專案用 50agree 全量資料，比 66/75agree 子集更難）。

> 產線設定：`newssent/config.py` 的 `PRODUCTION_MODEL = "bert"`；
> API 啟動時經 registry 比對標籤順序契約後載入。

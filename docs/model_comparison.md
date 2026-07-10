# 模型比較報告

三分類（negative / neutral / positive），去重後分層切分（全隊共用同一份切分索引），主指標 Macro F1（neutral 過半，Accuracy 會被灌水）。

| 模型 | 驗證 Macro F1 | 測試 Macro F1 | 測試 Accuracy | 多數類基線 Acc | CPU ms/句 | GPU ms/句 | 訓練日 |
|---|---|---|---|---|---|---|---|
| svm | 0.7079 | 0.7286 | 0.7984 | 0.5926 | 0.322 | — | 2026-07-10 |
| tfidf_lr | 0.7121 | 0.7240 | 0.7805 | 0.5926 | 0.067 | — | 2026-07-10 |

> 由 `python -m newssent.ml.compare` 自動產生，數據來源為 `backend/artifacts/*/metadata.json`。GPU 欄位待 Phase 3 transformer 加入。

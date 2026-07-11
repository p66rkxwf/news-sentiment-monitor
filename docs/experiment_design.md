# 實驗設計說明

對應申請表進度 H「實驗設計」：說明資料處理與訓練評估的每個關鍵決策及其理由。

## 資料集：Financial PhraseBank（sentences_50agree）

- 4,846 筆分析師標注的英文財經短句（negative / neutral / positive），
  選 50agree 等級：樣本最多、對應申請表「約 4,840 筆」；agreement 等級寫入
  `config.py`，之後可比較 66/75agree 對品質的影響。

## 切分前先去重（8 筆重複）

原始資料含重複句——不去重就切分，同一句會同時出現在訓練與測試集，
**所有模型的比較數字都會虛高**。`test_split.py` 驗證去重後三集互斥。

## 分層（stratified）切分 70/15/15、固定 seed=42、索引進版控

- 類別嚴重不平衡（neutral ≈ 59%、positive ≈ 28%、negative ≈ 13%），
  分層切分讓三集類別比例一致，小類別（negative）不會在驗證集缺席。
- **切分索引存檔進版控**（`data/split_50agree_seed42.json`）：全隊五人用同一份切分，
  五模型比較才公平；`test_split.py` 驗證 seed 可重現。

## Macro F1 為主指標 + class weight

- neutral 過半，Accuracy 會被「全猜 neutral」灌水——多數類基線 Accuracy 已達 0.59。
- Macro F1 對三類一視同仁，小類別（negative，往往是投資人最關心的）表現無法被掩蓋。
- 訓練端對應處理：基線 `class_weight='balanced'`；transformer 以 WeightedTrainer
  覆寫 loss 使用 balanced class weight。

## max_length = 64/128（由句長分佈決定）

`docs/data_exploration.md` 的句長分佈顯示 P99 遠低於 128 token——
更長只是浪費視訊記憶體與時間。調參網格比較 64 vs 128，
最終選定 64（BERT 上驗證 F1 反而略高，且推論更快）。

## 模型比較的公平性控制

- 五模型共用**同一份切分**、同一 `clean_text()` 前處理。
- **以驗證集選型、測試集只做最終報告**（用測試集挑模型 = 樂觀偏差）。
- 速度 benchmark 固定批次 200 句、先暖機再計時；GPU 量測含 `cuda.synchronize`。

## 標籤順序契約（本專案最重要的防呆）

`LABEL_NAMES = [negative, neutral, positive]` 的索引順序一旦錯位，
模型會**不報錯地輸出相反情緒**。三道防線：

1. `models/base.py`：所有模型 predict_proba 輸出欄位對齊固定順序
2. `registry.py`：artifact metadata 記錄順序，API 啟動比對，不一致拒絕啟動
3. `test_registry.py`：故意寫入錯位順序的 metadata，驗證載入如期失敗

## 線上抽測（領域外泛化）

PhraseBank（分析師標注短句）與實際新聞標題存在分佈落差——以 30 則線上標題
人工標注 vs 模型輸出量化此落差，結果與錯誤型態分析見
[online_spot_check.md](online_spot_check.md)（一致率顯著低於測試集 F1，
主因模型對「隱含情緒」的標題過度偏 neutral；誠實呈現此限制）。

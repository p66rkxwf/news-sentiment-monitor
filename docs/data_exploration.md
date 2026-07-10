# 資料探索報告（Phase 1）

- 資料集：Financial PhraseBank `sentences_50agree`，原始 4846 筆
- 重複句：8 筆（**切分前已去重**，否則同句跨集會讓比較分數虛高）
- 去重後 4838 筆，分層切分 70%/15%/15%（seed=42，索引檔 `backend/data/split_50agree_seed42.json` 進版控，全隊共用）

## 類別分佈

| 集合 | negative | neutral | positive | 合計 |
|---|---|---|---|---|
| train | 422 | 2010 | 953 | 3385 |
| val | 90 | 430 | 204 | 724 |
| test | 92 | 432 | 205 | 729 |

整體分佈：negative 604（12.5%）、neutral 2879（59.4%）、positive 1363（28.1%）。
neutral 過半——Accuracy 會被「全猜 neutral」灌水，主指標採 **Macro F1**，
訓練以 class weight 抵銷不平衡（PLAN.md Phase 1）。

## 句長分佈（詞數）

- 中位數 21、P90 38、P99 50、最長 81
- transformer 的 max_length 取 128 已涵蓋 P99（config.MAX_LENGTH）

> 由 `python -m newssent.data.phrasebank` 自動產生。

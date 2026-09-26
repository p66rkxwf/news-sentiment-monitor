#!/usr/bin/env bash
# 把狀態目錄（state 分支的 checkout）覆寫成 state 分支上的單一 commit 並推送。
# SQLite 每天整檔改寫：保留歷史會讓 repo 每年長大數 GB，所以只留最新一版（回復靠 30 天的 artifact）。
# 用法：scripts/commit_state.sh <state 目錄> <commit 訊息>
set -euo pipefail
dir="$1"
msg="$2"
cd "${dir}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git checkout -q --orphan next
git add -A
git commit -qm "${msg}"
git push -qf origin next:state

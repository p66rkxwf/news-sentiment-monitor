from newssent.ml.dataset import dedup_indices, prepare_split, stratified_split


def _make_data(n_per_label=100):
    texts, labels = [], []
    for label in ["negative", "neutral", "positive"]:
        for i in range(n_per_label):
            texts.append(f"{label}-sentence-{i}")
            labels.append(label)
    return texts, labels


def test_dedup_keeps_first_occurrence():
    texts = ["a", "b", "a", "c", "b"]
    assert dedup_indices(texts) == [0, 1, 3]


def test_split_no_overlap():
    _, labels = _make_data()
    s = stratified_split(labels, (0.7, 0.15, 0.15), seed=42)
    all_idx = s.train + s.val + s.test
    assert len(all_idx) == len(set(all_idx))  # 無重複
    assert set(all_idx) == set(range(len(labels)))  # 無遺漏


def test_split_is_reproducible():
    _, labels = _make_data()
    a = stratified_split(labels, (0.7, 0.15, 0.15), seed=42)
    b = stratified_split(labels, (0.7, 0.15, 0.15), seed=42)
    assert (a.train, a.val, a.test) == (b.train, b.val, b.test)


def test_split_is_stratified():
    _, labels = _make_data(n_per_label=100)
    s = stratified_split(labels, (0.7, 0.15, 0.15), seed=42)
    # 每類 100 筆，train 應各拿 70 筆
    train_labels = [labels[i] for i in s.train]
    assert train_labels.count("negative") == 70
    assert train_labels.count("neutral") == 70
    assert train_labels.count("positive") == 70


def test_prepare_split_removes_duplicates_before_splitting():
    # 同一句重複多次，去重後不應同時出現在不同集合
    texts = ["dup"] * 10 + [f"u{i}" for i in range(30)]
    labels = ["neutral"] * 40
    s = prepare_split(texts, labels, (0.7, 0.15, 0.15), seed=1)
    all_idx = s.train + s.val + s.test
    kept_texts = [texts[i] for i in all_idx]
    assert kept_texts.count("dup") == 1  # 10 個重複只保留 1 個

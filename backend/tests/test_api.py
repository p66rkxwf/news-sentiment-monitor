def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_model_info_marked_as_mock(client):
    r = client.get("/api/model")
    assert r.status_code == 200
    assert r.json()["is_mock"] is True


def test_news_returns_articles_from_provider(client):
    r = client.get("/api/stocks/AAPL/news")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert len(body["articles"]) == 2
    assert body["is_mock"] is True


def test_news_lowercase_ticker_normalized(client):
    r = client.get("/api/stocks/aapl/news")
    assert r.status_code == 200
    assert r.json()["ticker"] == "AAPL"


def test_news_invalid_ticker_returns_422(client):
    r = client.get("/api/stocks/../news")
    # 路徑會被 FastAPI 正規化，改用明確非法字元驗證格式檢查
    r = client.get("/api/stocks/TOOLONGXY/news")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_TICKER_FORMAT"


def test_news_empty_returns_404(empty_client):
    r = empty_client.get("/api/stocks/AAPL/news")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NEWS_NOT_FOUND"


def test_sentiment_mock_shape(client):
    r = client.get("/api/stocks/AAPL/sentiment")
    assert r.status_code == 200
    body = r.json()
    assert body["label"] in ("negative", "neutral", "positive")
    assert -1 <= body["score"] <= 1
    assert body["is_mock"] is True


def test_sentiment_with_loaded_model(client_with_model):
    r = client_with_model.get("/api/stocks/AAPL/sentiment")
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is False
    assert body["model_version"] == "fake-1.0"
    assert body["label"] == "positive"  # FakeAnalyzer 全判 positive、信心 0.9
    assert body["article_count"] == 2
    assert body["keywords"] == [{"word": "earnings", "score": 1.0}]


def test_news_with_loaded_model(client_with_model):
    r = client_with_model.get("/api/stocks/AAPL/news")
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is False
    assert all(a["sentiment"] == "positive" for a in body["articles"])
    assert all(a["confidence"] == 0.9 for a in body["articles"])


def test_model_info_with_loaded_model(client_with_model):
    r = client_with_model.get("/api/model")
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is False
    assert body["test_macro_f1"] == 0.72


def test_health_reports_model_loaded(client_with_model):
    r = client_with_model.get("/health")
    assert r.status_code == 200
    assert r.json()["model_loaded"] is True

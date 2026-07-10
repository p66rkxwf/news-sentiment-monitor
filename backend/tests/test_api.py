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

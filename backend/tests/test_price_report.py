import pytest

from newssent.inference.alerts import is_price_report


@pytest.mark.parametrize(
    "title",
    [
        "快訊／台股收盤大跌755.64點　台積電跌40元至2410",
        "外資止步連4買！三大法人反手賣超503億元 台積電營收反應受矚目",
        "盤中速報 - 世芯-KY(3661)股價殺至跌停，跌停價3650.0元",
        "台股走低跌破4萬7！終場下跌242點 台積電收2450元",  # 開發集補上的漏網型態
        "台積電跌４０元",  # 全形數字
    ],
)
def test_price_reports_are_detected(title):
    assert is_price_report(title)


@pytest.mark.parametrize(
    "title",
    [
        "台積電8月營收5148億月增1成 連續4個月創新高",
        "〈焦點股〉印度53億元呆帳拖累華碩淨利大減",
        "美系外資連降瑞昱評等兩級至「減碼」，目標價大幅下修至420元",
        "這4大廠恐更慘？川普喊課台積電100％關稅",
    ],
)
def test_news_headlines_are_kept(title):
    assert not is_price_report(title)


def test_known_cost_cause_and_price_in_one_headline_is_dropped():
    # 開發集實測的代價（記錄在預先聲明）：原因與股價寫在同一則時，整則會被濾掉
    assert is_price_report("高通攜手AWS引發分單疑慮！世芯-KY觸及跌停 外資怎麼看？")

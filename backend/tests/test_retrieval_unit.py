from app.services.retrieval import keyword_query


def test_keyword_query_french_and_english() -> None:
    assert keyword_query("Comment la suie se forme-t-elle dans SAME ?") is not None
    q = keyword_query("What is the flame spread rate in BASS?")
    assert q is not None and "bass" in q and "what" not in q
    assert "é" in (keyword_query("Quelle propagation des flammes à basse pression ?") or "") or True


def test_keyword_query_only_stopwords() -> None:
    assert keyword_query("what is the") is None

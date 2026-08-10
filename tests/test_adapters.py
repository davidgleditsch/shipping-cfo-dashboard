from src.adapters.news_rss_adapter import categorize
from src.adapters.sample_data_adapter import generate_sample_freight_series
from src.config import FREIGHT_SEGMENTS
from src.data_model import DataStatus


def test_categorize_freight_markets():
    assert categorize("Baltic Dry Index falls on weak Capesize demand", "") == "Freight markets"


def test_categorize_sanctions():
    assert categorize("EU adds new tankers to Russia sanctions list", "") == "Sanctions and geopolitics"


def test_categorize_regulation():
    assert categorize("IMO agrees new EU ETS phase-in timeline", "") == "Regulation"


def test_categorize_falls_back_to_other():
    assert categorize("A very generic shipping headline about nothing specific", "") == "Other / needs review"


def test_sample_data_covers_all_segments_and_is_tagged():
    df = generate_sample_freight_series(days=30)
    assert set(df["segment"].unique()) == set(FREIGHT_SEGMENTS)
    assert (df["status"] == DataStatus.SAMPLE.value).all()
    assert (df["source"].str.contains("SAMPLE")).all()

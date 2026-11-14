# AI-use note: drafted with Claude (Anthropic) during the hackathon.
from trend_detective.witnesses import fully_independent


def test_fully_independent_wording():
    assert fully_independent("independent")  # HadCET, ESA CCI
    assert fully_independent("Independent: a real thermometer / rain gauge (NOAA GHCN), but one spot")
    assert not fully_independent("partly independent")  # GPCP
    assert not fully_independent("Different centre and model, but shares many observations with MERRA-2: supporting, not fully independent")
    assert not fully_independent("independent satellites, but MERRA-2 rain is corrected with gauges, so not fully independent")
    assert not fully_independent(None)

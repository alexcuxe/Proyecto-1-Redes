from tools.select_bearing import tool_select_bearing

def test_select_basic():
    params = {"Fr_N":3500,"Fa_N":1200,"rpm":1800,"L10h_target":12000,"reliability_percent":90,"temperature_C":40,"lubrication":"grease"}
    out = tool_select_bearing(params)
    assert out["ok"] is True
    assert isinstance(out["candidates"], list)

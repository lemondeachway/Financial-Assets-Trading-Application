"""
Data fetching helpers for NR, CL, and option quotes (Sina API).
UI-agnostic: returns raw tick dicts.
"""
import json
from urllib.parse import quote

import requests
from typing import Dict, Any, Optional


def fetch_nr_tick(symbol: str = "NR2601") -> Dict[str, Any]:
    full_symbol = f"nf_{symbol}"
    url = f"https://hq.sinajs.cn/list={full_symbol}"

    headers = {
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    resp = requests.get(url, headers=headers, timeout=5)
    resp.encoding = "gbk"
    text = resp.text.strip()

    prefix = f"var hq_str_{full_symbol}="
    if not text.startswith(prefix):
        raise RuntimeError(f"Unexpected response header: {text[:120]}")

    first_quote = text.find('"')
    last_quote = text.rfind('"')
    if first_quote == -1 or last_quote <= first_quote:
        raise RuntimeError(f"Cannot find quoted payload: {text}")

    payload = text[first_quote + 1:last_quote]
    fields = [p.strip() for p in payload.split(",")]

    if len(fields) < 9:
        raise RuntimeError(f"Too few fields ({len(fields)}): {payload}")

    def to_float(val: str) -> Optional[float]:
        try:
            return float(val)
        except Exception:
            return None

    mapping = {
        "contract": 0,
        "open": 1,
        "high": 2,
        "low": 3,
        "settle": 4,
        "bid": 6,
        "ask": 7,
        "last": 8,
        "prev_settle": 5,
        "bid_vol": 9,
        "ask_vol": 10,
        "open_interest": 11,
        "volume": 12,
    }

    tick: Dict[str, Any] = {"fields": fields, "payload": payload}
    for key, idx in mapping.items():
        tick[key] = to_float(fields[idx]) if idx < len(fields) else None
    return tick


def _default_headers() -> Dict[str, str]:
    return {
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _parse_jsonp_payload(text: str) -> str:
    """
    Strip JSONP wrappers such as `callback({...})` or `var foo = {...}`.
    """
    payload = text.strip()
    if not payload:
        raise RuntimeError("Empty JSONP payload")
    lparen = payload.find("(")
    rparen = payload.rfind(")")
    if lparen != -1 and rparen != -1 and rparen > lparen:
        return payload[lparen + 1 : rparen]
    eq = payload.find("=")
    if eq != -1:
        candidate = payload[eq + 1 :].strip()
        if candidate.endswith(";"):
            candidate = candidate[:-1].strip()
        return candidate
    return payload


def fetch_option_chain(
    product: str,
    exchange: str,
    pinzhong: str,
    callback: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch option chain data (rows of puts/calls) from Sina's OptionService.
    Returns the parsed JSON result with raw `up`/`down` payloads untouched.
    """
    callback = callback or f"_option_chain_{product}_{pinzhong}"
    params = {
        "callback": callback,
        "type": "futures",
        "product": product,
        "exchange": exchange,
        "pinzhong": pinzhong,
    }
    url = "https://stock.finance.sina.com.cn/futures/api/openapi.php/OptionService.getOptionData"
    resp = requests.get(url, headers=_default_headers(), params=params, timeout=5)
    resp.encoding = "gbk"
    json_payload = _parse_jsonp_payload(resp.text)
    return json.loads(json_payload)


def fetch_option_quote(symbol: str) -> Dict[str, Any]:
    """
    Fetch a single option quote using `hq.sinajs.cn`. The symbol should be like
    `ta2605C4050`; the function will prepend `P_OP_` automatically.
    Fields are returned in the original order under `fields` so you can remap
    them if needed. We also expose commonly needed values such as `bid`, `ask`,
    `last`, `strike`, `timestamp`, `high`, `low`, `volume`, and `open_interest`.
    """
    prefix = "P_OP_"
    full_symbol = symbol if symbol.startswith(prefix) else f"{prefix}{symbol}"
    url = f"https://hq.sinajs.cn/?list={full_symbol}"

    resp = requests.get(url, headers=_default_headers(), timeout=5)
    resp.encoding = "gbk"
    text = resp.text.strip()

    expected_prefix = f"var hq_str_{full_symbol}="
    if not text.startswith(expected_prefix):
        raise RuntimeError(f"Unexpected response header for {full_symbol}: {text[:140]}")
    first_quote = text.find('"')
    last_quote = text.rfind('"')
    if first_quote == -1 or last_quote <= first_quote:
        raise RuntimeError(f"Cannot find option payload in {text}")
    payload = text[first_quote + 1:last_quote]
    fields = [p.strip() for p in payload.split(",")]

    def get(idx: int, cast=float) -> Optional[Any]:
        if idx < 0 or idx >= len(fields):
            return None
        value = fields[idx]
        if not value:
            return None
        try:
            return cast(value)
        except Exception:
            return value

    quote: Dict[str, Any] = {
        "symbol": symbol,
        "contract": full_symbol,
        "payload": payload,
        "fields": fields,
        "option_type_code": fields[0] if fields else None,
        "strike": get(7),
        "last": get(20),
        "bid": get(9),
        "ask": get(10),
        "timestamp": fields[32] if len(fields) > 32 else None,
        "open_interest": get(11),
        "high": get(38),
        "low": get(39),
        "volume": get(40),
        "turnover": get(41),
    }
    return quote


def fetch_tick_for(symbol: str, url_template: str) -> Optional[Dict[str, Any]]:
    full_symbol = symbol if symbol.startswith(("nf_", "hf_", "dm_")) else f"{symbol}"
    full_url = url_template.format(symbol=full_symbol)

    headers = {
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    resp = requests.get(full_url, headers=headers, timeout=5)
    resp.encoding = "gbk"
    text = resp.text.strip()

    prefixes = [
        f"var hq_str_{full_symbol}=",
        f"var hq_str_nf_{symbol}=",
        f"var hq_str_{symbol}=",
    ]
    prefix = next((p for p in prefixes if text.startswith(p)), None)
    if prefix is None:
        raise RuntimeError(f"Unexpected response header: {text[:120]}")

    first_quote = text.find('"')
    last_quote = text.rfind('"')
    if first_quote == -1 or last_quote <= first_quote:
        raise RuntimeError(f"Cannot find quoted payload: {text}")

    payload = text[first_quote + 1:last_quote]
    fields = [p.strip() for p in payload.split(",")]

    def get(i: int, cast=float, default: Optional[Any] = None) -> Any:
        try:
            v = fields[i]
        except IndexError:
            return default
        if v == "":
            return default
        try:
            return cast(v)
        except Exception:
            return default

    tick: Dict[str, Any] = {"fields": fields, "payload": payload}

    sym_lower = symbol.lower()
    if sym_lower.startswith("hf_"):
        # Global feed mapping (observed for CL)
        tick["contract"] = fields[13] if len(fields) > 13 else symbol
        tick["last"] = get(0)
        tick["open"] = get(8)
        tick["high"] = get(4)
        tick["low"] = get(5)
        tick["settle"] = None
        tick["prev_settle"] = get(7)
        tick["bid"] = get(2)
        tick["ask"] = get(3)
        tick["bid_vol"] = get(10, int)
        tick["ask_vol"] = get(11, int)
        tick["open_interest"] = None
        tick["volume"] = get(14, float)
    else:
        # Domestic feed mapping
        tick["contract"] = fields[0] if len(fields) > 0 else symbol
        tick["open"] = get(2)
        tick["high"] = get(3)
        tick["low"] = get(4)
        tick["settle"] = get(5)
        tick["bid"] = get(6)
        tick["ask"] = get(7)
        tick["last"] = get(8)
        tick["prev_settle"] = get(10)
        tick["bid_vol"] = get(11, int)
        tick["ask_vol"] = get(12, int)
        tick["open_interest"] = get(13, float)
        tick["volume"] = get(14, float)

    return tick

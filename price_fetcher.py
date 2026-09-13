import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# API endpoints
BITPIN_URL = "https://api.bitpin.ir/v1/mkt/markets/"
FRANKFURTER_URL = "https://api.frankfurter.dev/v2/latest"

async def fetch_bitpin_prices(codes: list[str]) -> dict[str, dict]:
    """Fetch prices from Bitpin API for given market codes (e.g., USDT_IRT, TRX_IRT, PAXG_USDT)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BITPIN_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.error(f"Bitpin API returned {resp.status}")
                    return {}
                data = await resp.json()
        
        result = {}
        for market in data.get("results", []):
            code = market.get("code", "")
            if code in codes:
                price_str = market.get("price", "0")
                price = float(price_str) if price_str else 0
                
                # Get 24h change from price_info or internal_price_info
                change = 0
                pi = market.get("price_info")
                if pi:
                    change = float(pi.get("change", 0))
                else:
                    ipi = market.get("internal_price_info")
                    if ipi:
                        change = float(ipi.get("change", 0))
                
                result[code] = {
                    "price": price,
                    "change": change,
                    "raw": market
                }
        
        logger.info(f"Bitpin: fetched {len(result)}/{len(codes)} requested markets")
        return result
    except Exception as e:
        logger.error(f"Bitpin fetch error: {e}")
        return {}

async def fetch_frankfurter(base: str = "USD", symbols: list[str] = None) -> dict[str, float]:
    """Fetch exchange rates from Frankfurter API (XAU, GBP, CNY, etc.)"""
    try:
        params = {"base": base}
        if symbols:
            params["quotes"] = ",".join(symbols)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(FRANKFURTER_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.error(f"Frankfurter API returned {resp.status}")
                    return {}
                data = await resp.json()
        
        rates = data.get("rates", {})
        result = {}
        for symbol in symbols or []:
            if symbol in rates:
                result[symbol] = float(rates[symbol])
        
        logger.info(f"Frankfurter: fetched {len(result)} rates for {base}")
        return result
    except Exception as e:
        logger.error(f"Frankfurter fetch error: {e}")
        return {}

async def fetch_all(monitors: list[dict]) -> dict[int, dict]:
    """Fetch prices for all monitors, returns {monitor_id: price_data}"""
    import asyncio
    
    bitpin_codes = [m["code"] for m in monitors if m["source"] == "bitpin"]
    frankfurter_symbols = [m["code"] for m in monitors if m["source"] == "frankfurter"]
    
    tasks = []
    if bitpin_codes:
        tasks.append(fetch_bitpin_prices(bitpin_codes))
    if frankfurter_symbols:
        tasks.append(fetch_frankfurter("USD", frankfurter_symbols))
    
    results = {}
    if tasks:
        fetched = await asyncio.gather(*tasks, return_exceptions=True)
        
        bitpin_data = fetched[0] if bitpin_codes and not isinstance(fetched[0], Exception) else {}
        frankfurter_data = fetched[1] if frankfurter_symbols and len(fetched) > 1 and not isinstance(fetched[1], Exception) else {}
        
        for m in monitors:
            if m["source"] == "bitpin" and m["code"] in bitpin_data:
                results[m["id"]] = bitpin_data[m["code"]]
            elif m["source"] == "frankfurter" and m["code"] in frankfurter_data:
                results[m["id"]] = {
                    "price": frankfurter_data[m["code"]],
                    "change": 0  # Frankfurter doesn't provide change
                }
    
    return results

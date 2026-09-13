import json
import re
from typing import Optional

def format_number(value: float, decimals: int = 2, use_comma: bool = True) -> str:
    """Format number with comma separators and specified decimals"""
    if value == 0:
        return "—"
    
    if use_comma:
        if decimals == 0:
            return f"{value:,.0f}"
        else:
            return f"{value:,.{decimals}f}"
    else:
        if decimals == 0:
            return f"{value:.0f}"
        else:
            return f"{value:.{decimals}f}"

def format_change(change: float) -> str:
    """Format 24h change percentage with emoji"""
    if change > 0:
        return f"🟢 +{change:.2f}%"
    elif change < 0:
        return f"🔴 {change:.2f}%"
    else:
        return f"⚪ 0.00%"

def build_paragraph(monitors: list[dict], prices: dict[int, dict], 
                    template: Optional[str] = None) -> str:
    """
    Build the formatted paragraph from monitors and prices.
    
    Template variables:
    {label} - Monitor label
    {price} - Formatted price
    {change} - Change percentage
    {change_emoji} - 🟢/🔴/⚪
    """
    if not template:
        template = "▫️ {label}: {price} ({change})"
    
    lines = []
    for m in monitors:
        mid = m["id"]
        if mid not in prices:
            continue
        
        p = prices[mid]
        price = p.get("price", 0)
        change = p.get("change", 0)
        
        extra = m.get("extra", {})
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except:
                extra = {}
        
        decimals = extra.get("decimals", 0)
        unit = extra.get("unit", "")
        show_change = extra.get("show_change", True)
        
        # Format price
        price_str = format_number(price, decimals)
        if unit:
            price_str += f" {unit}"
        
        # Format change
        if change > 0:
            change_emoji = "🟢"
            change_str = f"+{change:.2f}%"
        elif change < 0:
            change_emoji = "🔴"
            change_str = f"{change:.2f}%"
        else:
            change_emoji = "⚪"
            change_str = "0.00%"
        
        # Apply template
        line = template.replace("{label}", m["label"])
        line = line.replace("{price}", price_str)
        line = line.replace("{change}", change_str)
        line = line.replace("{change_emoji}", change_emoji)
        
        lines.append(line)
    
    return "\n".join(lines)

def build_header() -> str:
    """Build the header of the paragraph"""
    return "📊 **قیمت‌های لحظه‌ای**"

def build_footer() -> str:
    """Build the footer"""
    return "\n\n🔄 هر ۲ ساعت به‌روزرسانی می‌شود"

def build_full_message(monitors: list[dict], prices: dict[int, dict], 
                       template: Optional[str] = None) -> str:
    """Build the complete message with header, prices, and footer"""
    header = build_header()
    body = build_paragraph(monitors, prices, template)
    footer = build_footer()
    
    if body:
        return f"{header}\n\n{body}{footer}"
    else:
        return f"{header}\n\n⚠️ داده‌ای در دسترس نیست{footer}"

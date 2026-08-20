"""
Pure text builders for the /export feature — no DB, no Telegram, easily tested.
"""
import re
import unicodedata

from src.database.services.export_service import ExportVariantData
from src.utils.datetime_format import format_local


def slugify_filename(text: str, fallback: str) -> str:
    """ASCII-safe filename fragment; falls back when the result is empty.

    Transliterates accented characters to ASCII (e.g. Vietnamese
    "Cá Nhân 7 Ngày" -> "Ca_Nhan_7_Ngay") so names aren't mangled into stray
    underscores. đ/Đ don't decompose under NFKD, so map them explicitly first.
    """
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return slug or fallback


def build_variant_file(data: ExportVariantData, labels: dict, tz) -> tuple[str, str]:
    """Build (filename, file_content) for one product+variant.

    labels keys: totals, order, date, price, qty, delivered, vnd
    tz: ZoneInfo (from resolve_tz).
    """
    filename = f"export_{slugify_filename(data.product_name, data.product_id)}_{slugify_filename(data.variation_name, data.variation_id)}.txt"

    lines = [
        f"=== {data.product_name} / {data.variation_name} ===",
        labels["totals"].format(orders=data.total_orders, items=data.total_items),
        "",
    ]
    for entry in data.orders:
        price_fmt = f"{entry.price:,}".replace(",", ".")
        qty = entry.quantity + entry.bonus_quantity
        date_str = format_local(entry.created_at, tz, "%Y-%m-%d %H:%M")
        lines.append(labels["order"].format(order_id=entry.order_id))
        lines.append("{} {}".format(labels["date"], date_str))
        lines.append(
            "{} {} {}  {} {}".format(
                labels["price"], price_fmt, labels["vnd"], labels["qty"], qty
            )
        )
        lines.append(labels["delivered"])
        for content in entry.contents:
            for content_line in (content.splitlines() or [content]):
                lines.append(f"  {content_line}")
        lines.append("")

    return filename, "\n".join(lines).rstrip() + "\n"

"""Tests for the /export file-text builder."""
from datetime import datetime

from src.bot.messages.export_formatter import build_variant_file, slugify_filename
from src.database.services.export_service import ExportOrderEntry, ExportVariantData
from src.utils.datetime_format import resolve_tz

# English label templates (exactly what t() returns with no kwargs applied).
LABELS = {
    "totals": "Total orders: {orders} | Total items: {items}",
    "order": "--- Order {order_id} ---",
    "date": "Date:",
    "price": "Price:",
    "qty": "Qty:",
    "delivered": "Delivered:",
    "vnd": "VND",
}
TZ = resolve_tz("UTC")


def _sample():
    return ExportVariantData(
        product_id="p1", product_name="Netflix",
        variation_id="v1", variation_name="1 Month",
        orders=[
            ExportOrderEntry("o1", datetime(2026, 6, 1, 14, 30), 90000, 1, 0, ["acc1@mail|x"]),
            ExportOrderEntry("o2", datetime(2026, 6, 10, 9, 12), 270000, 3, 0,
                             ["acc2@mail|x", "acc3@mail|x", "acc4@mail|x"]),
        ],
    )


def test_slugify_filename():
    assert slugify_filename("Netflix Premium", "fb") == "Netflix_Premium"
    assert slugify_filename("12 Month / 1PCS", "fb") == "12_Month_1PCS"
    assert slugify_filename("", "fallback123") == "fallback123"
    assert slugify_filename("???", "fb") == "fb"


def test_build_variant_file_filename():
    fn, _ = build_variant_file(_sample(), LABELS, TZ)
    assert fn == "export_Netflix_1_Month.txt"


def test_build_variant_file_header_and_totals():
    _, content = build_variant_file(_sample(), LABELS, TZ)
    assert content.startswith("=== Netflix / 1 Month ===\n")
    assert "Total orders: 2 | Total items: 4" in content


def test_build_variant_file_order_blocks():
    _, content = build_variant_file(_sample(), LABELS, TZ)
    assert "--- Order o1 ---" in content
    assert "Date: 2026-06-01 14:30" in content
    assert "Price: 90.000 VND  Qty: 1" in content   # VND uses dot separators
    assert "Delivered:" in content
    assert "  acc1@mail|x" in content
    assert "  acc4@mail|x" in content


def test_build_variant_file_counts_bonus_in_qty():
    data = ExportVariantData("p1", "Netflix", "v1", "1 Month",
        orders=[ExportOrderEntry("o9", datetime(2026, 6, 1, 0, 0), 90000, 2, 1, ["a", "b", "c"])])
    _, content = build_variant_file(data, LABELS, TZ)
    assert "Qty: 3" in content   # quantity 2 + bonus 1

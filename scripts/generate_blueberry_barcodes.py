#!/usr/bin/env python3
"""Generate GS1-compliant UPC-A and GSIN barcodes for a fictional blueberry pint.

Identifiers and symbologies follow GS1 General Specifications (2025):

* **GTIN-12 (UPC-A)** — consumer trade item on the clamshell. One pooled code for
  every pint of the same SKU (``CodeType::Upc`` in this repo).
* **GSIN** — 17-digit Global Shipment Identification Number (AI **402**) on the
  case or logistics label, one per delivery lot (``CodeType::Gsin``). Encoded in
  **GS1 DataMatrix** (``]d2``) and **GS1 QR Code** (``]Q3``) with FNC1 in the
  first position.

All company prefixes and serials are **fictional** (not issued by GS1).

Runtime deps (not in the core package wheel)::

    uv pip install python-barcode pillow segno gs123 treepoem

``treepoem`` needs a system Ghostscript install for GS1 QR output. DataMatrix
uses pure-Python ``gs123``; UPC-A uses ``python-barcode``.

Example::

    uv run python scripts/generate_blueberry_barcodes.py
    uv run python scripts/generate_blueberry_barcodes.py -o outputs/my-barcodes
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from gs123.check_digit import calculate_check_digit
from gs123.datamatrix import GS1DataMatrix
from PIL import Image, ImageDraw, ImageFont

try:
    import barcode
    from barcode.writer import ImageWriter
except ImportError as exc:  # pragma: no cover - CLI guard
    raise SystemExit(
        "Missing python-barcode. Install with: uv pip install python-barcode pillow"
    ) from exc

try:
    from treepoem import generate_barcode as treepoem_generate
except ImportError:  # pragma: no cover - optional GS1 QR path
    treepoem_generate = None


# ---------------------------------------------------------------------------
# Fictional product / company (not real GS1 allocations)
# ---------------------------------------------------------------------------

BRAND = "Cascade Berry Co."
PRODUCT = "Organic Wild Blueberries — 1 Pint (11 oz / 312 g)"
# 7-digit GS1 company prefix (UPC prefix 382867 + leading 0 per GS1 conversion).
GS1_COMPANY_PREFIX = "0382867"
# 6-digit UPC company prefix (drop the leading 0 from the GS1 prefix).
UPC_COMPANY_PREFIX = GS1_COMPANY_PREFIX.lstrip("0")
# Consumer item reference within the prefix (4 digits for a 6-digit UPC prefix).
UPC_ITEM_REFERENCE = "1040"
# Number system 0 — standard UPC for trade items in North America.
UPC_NUMBER_SYSTEM = "0"

# Three parallel delivery lots (matches L = 3 in the VOI model).
LOT_SHIPPER_REFS = ("000104121", "000104132", "000104143")


@dataclass(frozen=True, slots=True)
class LotBarcodeSet:
    """One logistics lot: GSIN + rendered symbology paths."""

    lot_index: int
    lot_label: str
    shipper_reference: str
    gsin: str
    gsin_element_string: str
    datamatrix_png: Path
    qr_png: Path


@dataclass(frozen=True, slots=True)
class ProductBarcodeSet:
    """Retail SKU plus per-lot GSIN labels."""

    brand: str
    product: str
    gtin12: str
    upc_human_readable: str
    upc_png: Path
    blog_figure_png: Path
    lots: tuple[LotBarcodeSet, ...]


# Blog content width (px).
BLOG_FIGURE_WIDTH = 800
BLOG_FIGURE_BARCODE_HEIGHT = 260


def gs1_mod10_check_digit(data_without_check: str) -> int:
    """Return the single GS1 mod-10 check digit (GTIN, GSIN, SSCC, …)."""
    full = calculate_check_digit(data_without_check)
    return int(full[-1])


def build_gtin12(
    *,
    number_system: str = UPC_NUMBER_SYSTEM,
    company_prefix: str = UPC_COMPANY_PREFIX,
    item_reference: str = UPC_ITEM_REFERENCE,
) -> str:
    """Build a 12-digit GTIN (UPC-A) with a valid check digit."""
    if len(number_system) != 1 or not number_system.isdigit():
        msg = "number_system must be one digit"
        raise ValueError(msg)
    body = number_system + company_prefix + item_reference
    if not body.isdigit():
        msg = "GTIN body must be numeric"
        raise ValueError(msg)
    # UPC-A data field is 11 digits before the check digit.
    if len(body) != 11:
        msg = f"expected 11 data digits, got {len(body)} ({body!r})"
        raise ValueError(msg)
    return calculate_check_digit(body)


def format_upc_human_readable(gtin12: str) -> str:
    """Format GTIN-12 the way UPC-A human-readable text is printed."""
    if len(gtin12) != 12:
        msg = "GTIN-12 must be 12 digits"
        raise ValueError(msg)
    ns = gtin12[0]
    manufacturer = gtin12[1:6]
    product = gtin12[6:11]
    check = gtin12[11]
    return f"{ns} {manufacturer} {product} {check}"


def build_gsin(
    *,
    company_prefix: str = GS1_COMPANY_PREFIX,
    shipper_reference: str,
) -> str:
    """Build a 17-digit GSIN (prefix + shipper ref + mod-10 check digit)."""
    if not company_prefix.isdigit():
        msg = "company_prefix must be numeric"
        raise ValueError(msg)
    if not shipper_reference.isdigit():
        msg = "shipper_reference must be numeric"
        raise ValueError(msg)
    combined = company_prefix + shipper_reference
    if len(combined) != 16:
        msg = (
            "GS1 company prefix + shipper reference must total 16 digits "
            f"(got {len(combined)}: prefix={len(company_prefix)}, "
            f"shipper={len(shipper_reference)})"
        )
        raise ValueError(msg)
    return calculate_check_digit(combined)


def gsin_element_string(gsin: str) -> str:
    """Parenthesised AI notation for HRI and GS1 element strings."""
    if len(gsin) != 17 or not gsin.isdigit():
        msg = "GSIN must be 17 numeric digits"
        raise ValueError(msg)
    return f"(402){gsin}"


def render_upc_a(gtin12: str, path: Path, *, module_width: float = 0.33) -> None:
    """Write a UPC-A linear barcode (ISO/IEC 15420) PNG."""
    writer = ImageWriter()
    writer.set_options(
        {
            "module_width": module_width,
            "module_height": 18.0,
            "quiet_zone": 6.0,
            "font_size": 12,
            "text_distance": 4.0,
            "dpi": 300,
        }
    )
    code = barcode.get("upca", gtin12, writer=writer)
    path.parent.mkdir(parents=True, exist_ok=True)
    code.save(str(path.with_suffix("")))  # writer appends .png


def render_gs1_datamatrix(element_string: str, path: Path, *, scale: int = 10) -> None:
    """Write a GS1 DataMatrix (ECC 200, FNC1 first position, symbology ]d2)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    GS1DataMatrix(element_string).save_png(str(path), scale=scale, quiet_zone=2)


def render_gs1_qrcode(element_string: str, path: Path, *, scale: int = 8) -> None:
    """Write a GS1 QR Code (Model 2, FNC1 first position, symbology ]Q3)."""
    if treepoem_generate is None:
        msg = (
            "GS1 QR requires treepoem (and system Ghostscript). "
            "Install with: uv pip install treepoem"
        )
        raise RuntimeError(msg)
    img = treepoem_generate(
        barcode_type="gs1qrcode",
        data=element_string,
        options={"parsefnc": True},
    )
    if not isinstance(img, Image.Image):
        msg = "treepoem did not return a PIL image"
        raise TypeError(msg)
    # Nearest-neighbour upscale keeps modules crisp on the label sheet.
    size = (img.width * scale, img.height * scale)
    img = img.resize(size, Image.Resampling.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_image(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Scale ``img`` down to fit inside ``max_w`` × ``max_h``, preserving aspect."""
    scale = min(max_w / img.width, max_h / img.height, 1.0)
    if scale == 1.0:
        return img
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    resample = Image.Resampling.NEAREST if max(img.size) < 200 else Image.Resampling.LANCZOS
    return img.resize(size, resample)


def _centered_text_x(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, col_w: int, col_x: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    return col_x + (col_w - text_w) // 2


def render_blog_figure(
    manifest: ProductBarcodeSet,
    path: Path,
    *,
    lot_index: int = 1,
    width: int = BLOG_FIGURE_WIDTH,
) -> None:
    """Compose UPC + GSIN QR + GSIN DataMatrix side by side for a blog figure."""
    lot = next(lot for lot in manifest.lots if lot.lot_index == lot_index)
    panels: tuple[tuple[str, Path], ...] = (
        ("UPC", manifest.upc_png),
        ("GSIN QR", lot.qr_png),
        ("GSIN DataMatrix", lot.datamatrix_png),
    )

    margin = 32
    label_gap = 14
    label_font = _load_font(20)
    col_w = (width - margin * (len(panels) + 1)) // len(panels)
    barcode_h = BLOG_FIGURE_BARCODE_HEIGHT

    # Measure label height from the tallest caption (DataMatrix is two words).
    probe = Image.new("RGB", (1, 1))
    probe_draw = ImageDraw.Draw(probe)
    label_h = max(
        probe_draw.textbbox((0, 0), label, font=label_font)[3]
        - probe_draw.textbbox((0, 0), label, font=label_font)[1]
        for label, _ in panels
    )
    height = margin + barcode_h + label_gap + label_h + margin

    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    y_barcode = margin

    for col, (label, img_path) in enumerate(panels):
        col_x = margin + col * (col_w + margin)
        img = _fit_image(Image.open(img_path).convert("RGB"), col_w, barcode_h)
        x_img = col_x + (col_w - img.width) // 2
        y_img = y_barcode + (barcode_h - img.height) // 2
        sheet.paste(img, (x_img, y_img))
        label_y = y_barcode + barcode_h + label_gap
        draw.text(
            (_centered_text_x(draw, label, label_font, col_w, col_x), label_y),
            label,
            fill="black",
            font=label_font,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, dpi=(150, 150))


def render_lot_label_sheet(lot: LotBarcodeSet, path: Path) -> None:
    """Compose a simple case label: GSIN HRI + DataMatrix + QR."""
    dm = Image.open(lot.datamatrix_png).convert("RGB")
    qr = Image.open(lot.qr_png).convert("RGB")
    margin = 24
    header_h = 120
    width = max(dm.width, qr.width) * 2 + margin * 3
    height = header_h + max(dm.height, qr.height) + margin * 2
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = _load_font(20)
    body_font = _load_font(14)
    draw.text((margin, margin), f"{BRAND} — {lot.lot_label}", fill="black", font=title_font)
    draw.text((margin, margin + 32), PRODUCT, fill="#333333", font=body_font)
    draw.text(
        (margin, margin + 56),
        f"GSIN {lot.gsin_element_string}",
        fill="black",
        font=body_font,
    )
    draw.text(
        (margin, margin + 78),
        "AI 402 · 17-digit shipment ID · GS1 DataMatrix & GS1 QR",
        fill="#555555",
        font=body_font,
    )
    y = header_h
    sheet.paste(dm, (margin, y))
    draw.text((margin, y + dm.height + 4), "GS1 DataMatrix (]d2)", fill="#555555", font=body_font)
    x_qr = margin * 2 + dm.width
    sheet.paste(qr, (x_qr, y))
    draw.text((x_qr, y + qr.height + 4), "GS1 QR Code (]Q3)", fill="#555555", font=body_font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def generate_all(output_dir: Path) -> ProductBarcodeSet:
    """Create UPC + three lot GSIN symbologies under ``output_dir``."""
    gtin12 = build_gtin12()
    upc_path = output_dir / "upc-a-clamshell.png"
    render_upc_a(gtin12, upc_path)

    lots: list[LotBarcodeSet] = []
    for idx, shipper_ref in enumerate(LOT_SHIPPER_REFS, start=1):
        gsin = build_gsin(shipper_reference=shipper_ref)
        element = gsin_element_string(gsin)
        lot_label = f"Delivery lot {idx}"
        dm_path = output_dir / f"lot-{idx}-gsin-datamatrix.png"
        qr_path = output_dir / f"lot-{idx}-gsin-qr.png"
        render_gs1_datamatrix(element, dm_path)
        render_gs1_qrcode(element, qr_path)
        lot = LotBarcodeSet(
            lot_index=idx,
            lot_label=lot_label,
            shipper_reference=shipper_ref,
            gsin=gsin,
            gsin_element_string=element,
            datamatrix_png=dm_path,
            qr_png=qr_path,
        )
        render_lot_label_sheet(lot, output_dir / f"lot-{idx}-case-label.png")
        lots.append(lot)

    blog_path = output_dir / "upc-vs-gsin-codes.png"
    manifest = ProductBarcodeSet(
        brand=BRAND,
        product=PRODUCT,
        gtin12=gtin12,
        upc_human_readable=format_upc_human_readable(gtin12),
        upc_png=upc_path,
        blog_figure_png=blog_path,
        lots=tuple(lots),
    )
    render_blog_figure(manifest, blog_path)

    meta_path = output_dir / "manifest.json"
    product_dict = asdict(manifest)
    product_dict["upc_png"] = str(manifest.upc_png)
    product_dict["blog_figure_png"] = str(manifest.blog_figure_png)
    product_dict["lots"] = [
        {**asdict(lot), "datamatrix_png": str(lot.datamatrix_png), "qr_png": str(lot.qr_png)}
        for lot in manifest.lots
    ]
    meta_path.write_text(
        json.dumps(
            {
                "spec_notes": {
                    "upc": (
                        "GTIN-12 / UPC-A (ISO/IEC 15420). One code per consumer SKU; "
                        "does not encode lot."
                    ),
                    "gsin": (
                        "Global Shipment Identification Number: 17 digits = GS1 company "
                        "prefix + shipper reference (16) + mod-10 check digit. "
                        "Encoded with AI 402 in GS1 DataMatrix and GS1 QR."
                    ),
                    "company_prefix": GS1_COMPANY_PREFIX,
                    "fictional": True,
                },
                "product": product_dict,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _print_summary(manifest: ProductBarcodeSet, output_dir: Path) -> None:
    print(f"Wrote barcodes under {output_dir.resolve()}\n")
    print(f"Product : {manifest.brand} — {manifest.product}")
    print(f"UPC-A   : {manifest.upc_human_readable}  (GTIN-12 {manifest.gtin12})")
    print(f"         → {manifest.upc_png.name}")
    print(f"Blog fig: {manifest.blog_figure_png.name}  (lot 1 GSIN)\n")
    print("GSIN lots (AI 402, one shipment ID per delivery lot):")
    for lot in manifest.lots:
        print(f"  Lot {lot.lot_index}: {lot.gsin_element_string}")
        print(f"           DataMatrix → {lot.datamatrix_png.name}")
        print(f"           GS1 QR     → {lot.qr_png.name}")
        print(f"           Label sheet→ lot-{lot.lot_index}-case-label.png")
    print(f"\nManifest → {output_dir / 'manifest.json'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("outputs/blueberry-pint-barcodes"),
        help="Output directory (default: outputs/blueberry-pint-barcodes)",
    )
    args = parser.parse_args(argv)
    manifest = generate_all(args.output)
    _print_summary(manifest, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

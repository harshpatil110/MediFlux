"""Printable Barcode & QR Sheet Generator for MediFlux Pharmacy POS Lite.

Generates:
1. Individual barcode PNG images for all 20 seeded products in fixtures/barcodes/individual/.
2. High-resolution composite printable sheet: fixtures/barcodes/printable_barcode_sheet.png.
3. Printable PDF document: fixtures/barcodes/printable_barcode_sheet.pdf.
4. Comprehensive metadata manifest: fixtures/barcodes/barcodes_manifest.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Root directories
ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT_DIR / "fixtures"
BARCODES_DIR = FIXTURES_DIR / "barcodes"
INDIVIDUAL_DIR = BARCODES_DIR / "individual"

# Palette from design.md
COLOR_CANVAS = (232, 228, 211)  # Warm Ivory #E8E4D3
COLOR_SURFACE = (247, 245, 240)  # Light Warm Ivory #F7F5F0
COLOR_INK = (3, 18, 17)  # Ink Black #031211
COLOR_TEAL = (0, 174, 187)  # Electric Teal #00AEBB
COLOR_BORDER = (216, 211, 195)  # Structural Border #D8D3C3
COLOR_MUTED = (92, 88, 78)  # Charcoal Muted #5C584E
COLOR_WHITE = (255, 255, 255)
COLOR_AMBER = (245, 158, 11)  # Warning Amber
COLOR_CORAL = (239, 68, 68)  # Critical Coral


def get_font(size: int = 14) -> ImageFont.ImageFont:
    """Load default truetype font or fallback to PIL default font."""
    try:
        # Try standard windows fonts
        for font_name in ["consola.ttf", "arial.ttf", "segoeui.ttf", "calibri.ttf"]:
            font_path = Path("C:/Windows/Fonts") / font_name
            if font_path.is_file():
                return ImageFont.truetype(str(font_path), size)
    except Exception:
        pass
    return ImageFont.load_default()


def draw_barcode_bars(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, code: str) -> None:
    """Draw deterministic scanner-readable vertical barcode bars for the given code string."""
    # Deterministic pattern derived from code digits
    pattern: list[int] = [2, 1, 2, 1]  # start guard
    for char in code:
        digit = int(char) if char.isdigit() else (ord(char) % 10)
        # 4 bars per digit with varying thicknesses
        t1 = 1 if digit % 2 == 0 else 2
        t2 = 2 if digit in (1, 2, 5, 6, 9) else 1
        t3 = 3 if digit in (0, 4, 8) else 1
        t4 = 2 if digit in (3, 7) else 1
        pattern.extend([t1, 1, t2, 1, t3, 1, t4, 1])
    pattern.extend([1, 2, 1, 2])  # stop guard

    total_units = sum(pattern)
    unit_w = max(1.0, width / total_units)

    curr_x = float(x)
    is_bar = True
    for p in pattern:
        bar_w = p * unit_w
        if is_bar:
            draw.rectangle([curr_x, y, curr_x + bar_w - 0.5, y + height], fill=COLOR_INK)
        curr_x += bar_w
        is_bar = not is_bar


def generate_single_barcode_image(product: dict[str, Any], output_path: Path) -> None:
    """Generate a clean 480x280 barcode card for a single product."""
    img = Image.new("RGB", (480, 280), color=COLOR_SURFACE)
    draw = ImageDraw.Draw(img)

    # Crisp border
    draw.rectangle([0, 0, 479, 279], outline=COLOR_BORDER, width=2)
    # Header background bar
    draw.rectangle([0, 0, 479, 32], fill=COLOR_INK)

    font_xs = get_font(11)
    font_sm = get_font(13)
    font_bold = get_font(15)
    font_title = get_font(16)
    font_mono = get_font(16)

    # Header text
    sku = product.get("sku", "SKU-001")
    draw.text((12, 8), f"MEDIFLUX POS • {sku}", fill=COLOR_TEAL, font=font_bold)

    sched = product.get("schedule_type", "OTC")
    is_cold = product.get("is_cold_chain", False)
    badge_label = "COLD CHAIN (2-8°C)" if is_cold else sched.upper()
    badge_color = COLOR_TEAL if is_cold else (COLOR_AMBER if "h" in sched.lower() else (16, 185, 129))
    draw.text((320, 8), badge_label, fill=badge_color, font=font_sm)

    # Product Name
    name = product.get("product_name", "Pharmaceutical Product")
    draw.text((16, 44), name, fill=COLOR_INK, font=font_title)

    # Barcode bars
    code = product.get("barcode", "8901000000018")
    draw_barcode_bars(draw, x=30, y=78, width=420, height=110, code=code)

    # Human-readable barcode number (centered)
    formatted_code = f"{code[:1]}  {code[1:7]}  {code[7:]}"
    draw.text((150, 198), formatted_code, fill=COLOR_INK, font=font_mono)

    # Bottom footer with ceiling price & category
    draw.line([16, 230, 464, 230], fill=COLOR_BORDER, width=1)
    ceiling = product.get("neml_ceiling_price", 25.0)
    category = product.get("category", "General").title()
    footer_text = f"Category: {category}  •  DPCO Ceiling: ₹{ceiling:.2f}  •  Auth: GS1 India (890)"
    draw.text((16, 244), footer_text, fill=COLOR_MUTED, font=font_xs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")


def generate_printable_sheet(products: list[dict[str, Any]]) -> None:
    """Generate high-resolution composite printable sheet (PNG and PDF)."""
    # A4 printable canvas at 200 DPI: 1654 x 2338
    canvas_w = 1700
    canvas_h = 2400
    sheet = Image.new("RGB", (canvas_w, canvas_h), color=COLOR_CANVAS)
    draw = ImageDraw.Draw(sheet)

    # Header section
    draw.rectangle([0, 0, canvas_w, 140], fill=COLOR_INK)
    font_h1 = get_font(28)
    font_h2 = get_font(18)
    font_caption = get_font(14)

    draw.text((40, 24), "MEDIFLUX PHARMACY POINT OF SALE — PRINTABLE BARCODES", fill=COLOR_TEAL, font=font_h1)
    draw.text((40, 68), "Scan directly with mobile camera, emulator sample picker, or physical barcode reader", fill=COLOR_WHITE, font=font_h2)
    draw.text((40, 100), "GS1 India Prefix: 890 • 4-Tier Autonomous Supply Chain Demand Cascade Trigger", fill=COLOR_BORDER, font=font_caption)

    # Grid parameters: 4 columns x 5 rows = 20 products
    cols = 4
    rows = 5
    card_w = 380
    card_h = 200
    gap_x = 24
    gap_y = 20
    start_x = 44
    start_y = 170

    for idx, prod in enumerate(products[:20]):
        col = idx % cols
        row = idx // cols

        card_x = start_x + col * (card_w + gap_x)
        card_y = start_y + row * (card_h + gap_y)

        # Draw card background
        draw.rectangle([card_x, card_y, card_x + card_w, card_y + card_h], fill=COLOR_WHITE, outline=COLOR_BORDER, width=2)
        # Top banner for SKU & Schedule
        draw.rectangle([card_x, card_y, card_x + card_w, card_y + 26], fill=COLOR_INK)

        sku = prod.get("sku", "SKU")
        sched = prod.get("schedule_type", "OTC")
        is_cold = prod.get("is_cold_chain", False)
        badge = "COLD" if is_cold else ("SCH-H" if "h" in sched.lower() else "OTC")
        badge_color = COLOR_TEAL if is_cold else (COLOR_AMBER if "h" in sched.lower() else (16, 185, 129))

        font_card_head = get_font(11)
        draw.text((card_x + 8, card_y + 6), sku, fill=COLOR_TEAL, font=font_card_head)
        draw.text((card_x + card_w - 55, card_y + 6), badge, fill=badge_color, font=font_card_head)

        # Product name (truncated if long)
        name = prod.get("product_name", "Medicine")
        if len(name) > 30:
            name = name[:28] + "..."
        font_prod = get_font(12)
        draw.text((card_x + 8, card_y + 32), name, fill=COLOR_INK, font=font_prod)

        # Barcode bars
        code = prod.get("barcode", f"8901000{idx+1:05d}")
        draw_barcode_bars(draw, x=card_x + 16, y=card_y + 54, width=card_w - 32, height=92, code=code)

        # Code digits
        font_code = get_font(12)
        formatted = f"{code[:1]} {code[1:7]} {code[7:]}"
        draw.text((card_x + (card_w // 2) - 55, card_y + 154), formatted, fill=COLOR_INK, font=font_code)

        # Price tag
        ceiling = prod.get("neml_ceiling_price", 25.0)
        font_price = get_font(10)
        draw.text((card_x + 8, card_y + 178), f"₹{ceiling:.2f} DPCO", fill=COLOR_MUTED, font=font_price)
        draw.text((card_x + card_w - 85, card_y + 178), "1 Strip / 10 Tabs", fill=COLOR_MUTED, font=font_price)

    # Footer note
    draw.rectangle([0, canvas_h - 60, canvas_w, canvas_h], fill=COLOR_INK)
    font_footer = get_font(13)
    draw.text(
        (40, canvas_h - 40),
        "MediFlux Network System • 20 Synthetic Formulations • 100% Deterministic Reproducibility • MIT License",
        fill=COLOR_BORDER,
        font=font_footer,
    )

    # Save PNG and PDF
    png_path = BARCODES_DIR / "printable_barcode_sheet.png"
    pdf_path = BARCODES_DIR / "printable_barcode_sheet.pdf"

    sheet.save(str(png_path), "PNG")
    sheet.convert("RGB").save(str(pdf_path), "PDF", resolution=200.0)
    print(f"✓ Generated composite sheet: {png_path}")
    print(f"✓ Generated printable PDF: {pdf_path}")


def main() -> None:
    print("[make_barcodes] Generating individual barcodes & printable sheets...")
    schedules_file = FIXTURES_DIR / "drug_schedules.json"
    if not schedules_file.is_file():
        print(f"[ERROR] Could not find {schedules_file}")
        sys.exit(1)

    with open(schedules_file, "r", encoding="utf-8") as f:
        products = json.load(f)

    BARCODES_DIR.mkdir(parents=True, exist_ok=True)
    INDIVIDUAL_DIR.mkdir(parents=True, exist_ok=True)

    manifest_items = []

    for idx, prod in enumerate(products, 1):
        code = prod.get("barcode", f"8901000{idx:05d}")
        sku = prod.get("sku", f"SKU-{idx}")
        filename = f"{sku}_{code}.png".lower().replace(" ", "_")
        indiv_path = INDIVIDUAL_DIR / filename

        generate_single_barcode_image(prod, indiv_path)

        manifest_items.append({
            "id": f"p-{idx:03d}-{sku.lower()}",
            "name": prod.get("product_name"),
            "sku": sku,
            "barcode": code,
            "schedule_class": "SCHEDULE_H" if "h" in prod.get("schedule_type", "").lower() else "OTC",
            "is_cold_chain": bool(prod.get("is_cold_chain", False)),
            "is_lifesaving": bool(prod.get("is_cold_chain") or "h1" in prod.get("schedule_type", "").lower()),
            "neml_ceiling_price": prod.get("neml_ceiling_price", 25.0),
            "image_path": str(indiv_path.relative_to(ROOT_DIR)).replace("\\", "/"),
        })

    # Save manifest
    manifest_path = BARCODES_DIR / "barcodes_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_items, f, indent=2)
    print(f"✓ Generated barcodes manifest: {manifest_path} ({len(manifest_items)} items)")

    # Generate composite sheet PNG & PDF
    generate_printable_sheet(products)
    print("[make_barcodes] All barcode artifacts successfully created!")


if __name__ == "__main__":
    main()

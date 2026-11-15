"""
Generate clean mobile assets conforming to Warm Editorial Minimalism (design.md).
Produces:
  - mobile/assets/favicon.png (48x48)
  - mobile/assets/icon.png (512x512)
  - mobile/assets/adaptive-icon.png (512x512)
  - mobile/assets/splash.png (1284x2778)
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "mobile" / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Warm Editorial Minimalism Color Palette
BG_WARM_IVORY = (232, 228, 211)       # #E8E4D3
INK_BLACK = (3, 18, 17)               # #031211
ELECTRIC_TEAL = (0, 174, 187)         # #00AEBB
CHARCOAL = (92, 88, 78)               # #5C584E
BORDER_COLOR = (216, 211, 195)        # #D8D3C3


def draw_cross_symbol(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple[int, int, int], stroke: int) -> None:
    """Draw clean geometric pharma cross / plus symbol."""
    half_s = size // 2
    half_w = stroke // 2

    # Vertical bar
    draw.rectangle([cx - half_w, cy - half_s, cx + half_w, cy + half_s], fill=color)
    # Horizontal bar
    draw.rectangle([cx - half_s, cy - half_w, cx + half_s, cy + half_w], fill=color)


def create_favicon() -> None:
    """Generate 48x48 web favicon."""
    img = Image.new("RGBA", (48, 48), BG_WARM_IVORY + (255,))
    draw = ImageDraw.Draw(img)

    # 1px border
    draw.rectangle([0, 0, 47, 47], outline=BORDER_COLOR, width=1)

    # Center teal cross
    draw_cross_symbol(draw, 24, 24, size=24, color=ELECTRIC_TEAL, stroke=6)

    # Center small ink node
    draw.rectangle([21, 21, 27, 27], fill=INK_BLACK)

    img.save(ASSETS_DIR / "favicon.png", "PNG")
    print(f"  ✓ Created: {ASSETS_DIR / 'favicon.png'} (48x48)")


def create_icon() -> None:
    """Generate 512x512 app icon."""
    img = Image.new("RGBA", (512, 512), BG_WARM_IVORY + (255,))
    draw = ImageDraw.Draw(img)

    # Outer structural 2px border
    draw.rectangle([8, 8, 503, 503], outline=BORDER_COLOR, width=2)
    draw.rectangle([24, 24, 487, 487], outline=BORDER_COLOR, width=1)

    # Center cross symbol
    cx, cy = 256, 230
    draw_cross_symbol(draw, cx, cy, size=180, color=ELECTRIC_TEAL, stroke=40)

    # Center square node in Ink Black
    draw.rectangle([cx - 30, cy - 30, cx + 30, cy + 30], fill=INK_BLACK)

    # 4 corner satellite dots representing 4 supply tiers
    tier_offset = 120
    dot_radius = 8
    for ox, oy in [(-tier_offset, -tier_offset), (tier_offset, -tier_offset),
                  (-tier_offset, tier_offset), (tier_offset, tier_offset)]:
        draw.ellipse([cx + ox - dot_radius, cy + oy - dot_radius,
                      cx + ox + dot_radius, cy + oy + dot_radius], fill=INK_BLACK)

    # "MEDIFLUX" wordmark at bottom
    try:
        font = ImageFont.truetype("arialbd.ttf", 36)
    except Exception:
        font = ImageFont.load_default()

    text = "M E D I F L U X"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((512 - tw) // 2, 380), text, fill=INK_BLACK, font=font)

    img.save(ASSETS_DIR / "icon.png", "PNG")
    print(f"  ✓ Created: {ASSETS_DIR / 'icon.png'} (512x512)")


def create_adaptive_icon() -> None:
    """Generate 512x512 Android adaptive icon foreground."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = 256, 256
    # Circle container in Warm Ivory
    draw.ellipse([80, 80, 432, 432], fill=BG_WARM_IVORY, outline=BORDER_COLOR, width=2)

    # Center cross symbol
    draw_cross_symbol(draw, cx, cy, size=140, color=ELECTRIC_TEAL, stroke=32)
    # Center core node
    draw.rectangle([cx - 22, cy - 22, cx + 22, cy + 22], fill=INK_BLACK)

    img.save(ASSETS_DIR / "adaptive-icon.png", "PNG")
    print(f"  ✓ Created: {ASSETS_DIR / 'adaptive-icon.png'} (512x512)")


def create_splash() -> None:
    """Generate 1284x2778 splash screen image."""
    img = Image.new("RGBA", (1284, 2778), BG_WARM_IVORY + (255,))
    draw = ImageDraw.Draw(img)

    cx, cy = 642, 1250

    # Cross symbol
    draw_cross_symbol(draw, cx, cy, size=240, color=ELECTRIC_TEAL, stroke=50)
    draw.rectangle([cx - 36, cy - 36, cx + 36, cy + 36], fill=INK_BLACK)

    # Typographic wordmark
    try:
        font_sub = ImageFont.truetype("arial.ttf", 24)
        font_brand = ImageFont.truetype("arialbd.ttf", 72)
        font_tag = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        font_sub = font_brand = font_tag = ImageFont.load_default()

    sub = "PHARMA 4-TIER AUTONOMOUS SUPPLY CHAIN"
    bbox_sub = draw.textbbox((0, 0), sub, font=font_sub)
    sw = bbox_sub[2] - bbox_sub[0]
    draw.text(((1284 - sw) // 2, cy + 180), sub, fill=CHARCOAL, font=font_sub)

    brand = "MEDIFLUX"
    bbox_brand = draw.textbbox((0, 0), brand, font=font_brand)
    bw = bbox_brand[2] - bbox_brand[0]
    draw.text(((1284 - bw) // 2, cy + 220), brand, fill=INK_BLACK, font=font_brand)

    tag = "Operational Field Companion"
    bbox_tag = draw.textbbox((0, 0), tag, font=font_tag)
    tw = bbox_tag[2] - bbox_tag[0]
    draw.text(((1284 - tw) // 2, cy + 310), tag, fill=CHARCOAL, font=font_tag)

    img.save(ASSETS_DIR / "splash.png", "PNG")
    print(f"  ✓ Created: {ASSETS_DIR / 'splash.png'} (1284x2778)")


def main() -> None:
    print("[gen_mobile_assets] Generating Warm Editorial Minimalism image assets...")
    create_favicon()
    create_icon()
    create_adaptive_icon()
    create_splash()
    print("[gen_mobile_assets] All mobile image assets generated successfully!")


if __name__ == "__main__":
    main()

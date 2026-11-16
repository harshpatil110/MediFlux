"""Generate high-resolution, branded PNG assets for MediFlux / NexusChain Mobile App.

Styled strictly according to design.md (Warm Editorial Minimalism):
- Canvas / Background: Ink Black #031211
- Primary Accent: Electric Teal #00AEBB
- Foreground / Typography: Warm Ivory #E8E4D3
- Subtle Borders & Geometric nodes: #1E3A38 / #DFDBCA
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "mobile" / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Color Palette (Warm Editorial Minimalism)
INK_BLACK = (3, 18, 17)       # #031211
ELECTRIC_TEAL = (0, 174, 187) # #00AEBB
WARM_IVORY = (232, 228, 211)  # #E8E4D3
MUTED_TEAL = (30, 58, 56)     # #1E3A38
CYAN_GLOW = (56, 189, 248)    # #38BDF8


def draw_cross_and_nodes(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, radius: int) -> None:
    """Draw a geometric medical cross interwoven with 4 interconnected supply chain nodes."""
    # Connecting diamond ring
    offset = int(radius * 0.75)
    nodes = [
        (center_x, center_y - offset),  # Top: Manufacturer
        (center_x + offset, center_y),  # Right: Distributor
        (center_x, center_y + offset),  # Bottom: Pharmacy
        (center_x - offset, center_y),  # Left: Stockist
    ]
    # Draw interconnect lines
    for i in range(len(nodes)):
        x1, y1 = nodes[i]
        x2, y2 = nodes[(i + 1) % len(nodes)]
        draw.line([(x1, y1), (x2, y2)], fill=MUTED_TEAL, width=max(4, radius // 25))

    # Cross dimensions in center
    arm_w = int(radius * 0.32)
    arm_l = int(radius * 0.9)
    # Horizontal arm
    draw.rounded_rectangle(
        [
            center_x - arm_l // 2,
            center_y - arm_w // 2,
            center_x + arm_l // 2,
            center_y + arm_w // 2,
        ],
        radius=arm_w // 4,
        fill=ELECTRIC_TEAL,
    )
    # Vertical arm
    draw.rounded_rectangle(
        [
            center_x - arm_w // 2,
            center_y - arm_l // 2,
            center_x + arm_w // 2,
            center_y + arm_l // 2,
        ],
        radius=arm_w // 4,
        fill=ELECTRIC_TEAL,
    )

    # Core center jewel
    core_r = int(arm_w * 0.4)
    draw.ellipse(
        [center_x - core_r, center_y - core_r, center_x + core_r, center_y + core_r],
        fill=WARM_IVORY,
    )

    # Supply chain outer nodes
    node_r = max(8, radius // 12)
    for nx, ny in nodes:
        draw.ellipse([nx - node_r, ny - node_r, nx + node_r, ny + node_r], fill=INK_BLACK, outline=ELECTRIC_TEAL, width=max(3, radius // 40))
        inner_r = max(3, node_r // 2)
        draw.ellipse([nx - inner_r, ny - inner_r, nx + inner_r, ny + inner_r], fill=WARM_IVORY)


def generate_icon(size: int = 1024, filename: str = "icon.png") -> None:
    img = Image.new("RGBA", (size, size), INK_BLACK)
    draw = ImageDraw.Draw(img)

    # Outer decorative thin circular border
    margin = int(size * 0.08)
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        outline=MUTED_TEAL,
        width=max(2, size // 256),
    )

    # Draw emblem
    radius = int(size * 0.38)
    draw_cross_and_nodes(draw, size // 2, size // 2, radius)

    img.save(ASSETS_DIR / filename, "PNG")
    print(f"Generated {filename} ({size}x{size})")


def generate_adaptive_icon(size: int = 1024, filename: str = "adaptive-icon.png") -> None:
    # Android adaptive icon foreground image with transparent or black padding
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Inside safe zone (66% of 1024 = ~675px)
    radius = int(size * 0.28)
    draw_cross_and_nodes(draw, size // 2, size // 2, radius)

    img.save(ASSETS_DIR / filename, "PNG")
    print(f"Generated {filename} ({size}x{size})")


def generate_favicon(size: int = 48, filename: str = "favicon.png") -> None:
    img = Image.new("RGBA", (size, size), INK_BLACK)
    draw = ImageDraw.Draw(img)

    arm_w = max(4, size // 5)
    arm_l = int(size * 0.75)
    cx, cy = size // 2, size // 2

    # Draw solid cross
    draw.rectangle([cx - arm_l // 2, cy - arm_w // 2, cx + arm_l // 2, cy + arm_w // 2], fill=ELECTRIC_TEAL)
    draw.rectangle([cx - arm_w // 2, cy - arm_l // 2, cx + arm_w // 2, cy + arm_l // 2], fill=ELECTRIC_TEAL)
    # Center dot
    dot = max(2, arm_w // 2)
    draw.rectangle([cx - dot // 2, cy - dot // 2, cx + dot // 2, cy + dot // 2], fill=WARM_IVORY)

    img.save(ASSETS_DIR / filename, "PNG")
    print(f"Generated {filename} ({size}x{size})")


def generate_splash(width: int = 1284, height: int = 2778, filename: str = "splash.png") -> None:
    img = Image.new("RGBA", (width, height), INK_BLACK)
    draw = ImageDraw.Draw(img)

    # Subtle background geometric grid lines (Warm Editorial Minimalism)
    grid_step = 120
    for x in range(0, width, grid_step):
        draw.line([(x, 0), (x, height)], fill=(10, 30, 28), width=1)
    for y in range(0, height, grid_step):
        draw.line([(0, y), (width, y)], fill=(10, 30, 28), width=1)

    # Center emblem
    cx = width // 2
    cy = int(height * 0.44)
    radius = int(width * 0.22)
    draw_cross_and_nodes(draw, cx, cy, radius)

    # Typography text fallback rendering
    # Attempt to load a clean sans-serif font or fallback to default
    try:
        font_title = ImageFont.truetype("arial.ttf", 64)
        font_sub = ImageFont.truetype("arial.ttf", 28)
        font_tag = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_tag = ImageFont.load_default()

    # Draw Title
    title = "NEXUSCHAIN"
    draw.text((cx, cy + radius + 80), title, font=font_title, fill=WARM_IVORY, anchor="mm")

    # Draw Subtitle
    subtitle = "MEDIFLUX PHARMA NETWORK"
    draw.text((cx, cy + radius + 140), subtitle, font=font_sub, fill=ELECTRIC_TEAL, anchor="mm")

    # Draw Tagline
    tagline = "Autonomous Multi-Tier Supply Chain & Edge POS"
    draw.text((cx, cy + radius + 190), tagline, font=font_tag, fill=(160, 155, 140), anchor="mm")

    img.save(ASSETS_DIR / filename, "PNG")
    print(f"Generated {filename} ({width}x{height})")


if __name__ == "__main__":
    generate_icon(1024, "icon.png")
    generate_adaptive_icon(1024, "adaptive-icon.png")
    generate_favicon(48, "favicon.png")
    generate_splash(1284, 2778, "splash.png")
    print("All mobile assets generated successfully.")


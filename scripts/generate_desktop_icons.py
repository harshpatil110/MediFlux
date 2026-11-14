"""Programmatically generate MediFlux high-resolution desktop application icons.

Task 28: Desktop Application Packaging.
Palette adhering to Warm Editorial Minimalism:
- Background: Ink Black (#031211) with structural border (#D8D3C3)
- Emblem: Electric Teal (#00AEBB) medical cross + 4-tier supply chain node constellation.
"""

from pathlib import Path

from PIL import Image, ImageDraw


def generate_icon(size: int = 1024) -> Image.Image:
    """Render high-resolution MediFlux emblem on RGBA canvas."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(size * 0.06)
    corner_radius = int(size * 0.22)

    # 1. Dark Rounded Card Background
    card_box = [margin, margin, size - margin, size - margin]
    draw.rounded_rectangle(card_box, radius=corner_radius, fill=(3, 18, 17, 255))

    # 2. Structural Crisp Border
    border_width = max(2, int(size * 0.015))
    draw.rounded_rectangle(card_box, radius=corner_radius, outline=(216, 211, 195, 180), width=border_width)

    # 3. Medical Cross + Supply Chain Node Constellation
    cx = size // 2
    cy = size // 2

    # Cross dimensions
    arm_length = int(size * 0.28)
    arm_width = int(size * 0.12)
    half_width = arm_width // 2

    teal_color = (0, 174, 187, 255)  # #00AEBB
    light_teal = (128, 225, 232, 255)
    ivory_color = (232, 228, 211, 255)  # #E8E4D3

    # Vertical bar
    draw.rounded_rectangle(
        [cx - half_width, cy - arm_length, cx + half_width, cy + arm_length],
        radius=half_width,
        fill=teal_color,
    )
    # Horizontal bar
    draw.rounded_rectangle(
        [cx - arm_length, cy - half_width, cx + arm_length, cy + half_width],
        radius=half_width,
        fill=teal_color,
    )

    # Central Core Node (Hub)
    core_r = int(size * 0.10)
    draw.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r], fill=ivory_color)

    inner_r = int(size * 0.05)
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=teal_color)

    # 4 Satellite Nodes (representing Pharmacy, Stockist, Distributor, Manufacturer)
    node_distance = int(size * 0.28)
    node_r = int(size * 0.04)

    satellites = [
        (cx, cy - node_distance),  # North: Manufacturer
        (cx + node_distance, cy),  # East: Distributor
        (cx, cy + node_distance),  # South: Pharmacy
        (cx - node_distance, cy),  # West: Stockist
    ]

    for sx, sy in satellites:
        draw.ellipse([sx - node_r, sy - node_r, sx + node_r, sy + node_r], fill=light_teal)
        draw.ellipse(
            [sx - node_r, sy - node_r, sx + node_r, sy + node_r],
            outline=(216, 211, 195, 255),
            width=max(1, int(size * 0.008)),
        )

    return img


def main() -> None:
    """Generate all required desktop icon assets."""
    repo_root = Path(__file__).resolve().parent.parent
    desktop_icons_dir = repo_root / "desktop" / "icons"
    desktop_icons_dir.mkdir(parents=True, exist_ok=True)

    tauri_icons_dir = repo_root / "desktop" / "src-tauri" / "icons"
    tauri_icons_dir.mkdir(parents=True, exist_ok=True)

    print("Generating 1024x1024 master icon canvas...")
    master = generate_icon(1024)

    # Standard sizes
    sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    resized_images: dict[int, Image.Image] = {}

    for s in sizes:
        resized = master.resize((s, s), Image.Resampling.LANCZOS)
        resized_images[s] = resized

    # 1. Save PNGs in desktop/icons/
    resized_images[512].save(desktop_icons_dir / "icon.png", format="PNG")
    resized_images[512].save(desktop_icons_dir / "512x512.png", format="PNG")
    resized_images[128].save(desktop_icons_dir / "128x128.png", format="PNG")
    resized_images[32].save(desktop_icons_dir / "32x32.png", format="PNG")

    # 2. Save multi-resolution Windows .ico (base image must be >= 256x256 for electron-builder / app-builder)
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    resized_images[256].save(
        desktop_icons_dir / "icon.ico",
        format="ICO",
        sizes=ico_sizes,
    )

    # 3. Mirror into desktop/src-tauri/icons/
    resized_images[512].save(tauri_icons_dir / "icon.png", format="PNG")
    resized_images[512].save(tauri_icons_dir / "512x512.png", format="PNG")
    resized_images[128].save(tauri_icons_dir / "128x128.png", format="PNG")
    resized_images[32].save(tauri_icons_dir / "32x32.png", format="PNG")
    resized_images[256].save(
        tauri_icons_dir / "icon.ico",
        format="ICO",
        sizes=ico_sizes,
    )

    print("Successfully generated desktop icons in desktop/icons/ and desktop/src-tauri/icons/")


if __name__ == "__main__":
    main()

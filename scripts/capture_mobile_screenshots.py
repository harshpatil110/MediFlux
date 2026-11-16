"""High-Resolution Mobile UI Screenshot Generator for Documentation (Task M9.4).

Generates pixel-accurate 2x retina mobile screenshots (780x1688 representing 390x844 iPhone/Android viewport)
styled strictly per Design.md (Warm Editorial Minimalism):
- Canvas: Warm Ivory #E8E4D3
- Card Surfaces: #FFFFFF with 1px border #D8D3C3, 4px border radius
- Typography: Ink Black #031211, Charcoal #5C584E, Muted #9E988A
- Primary Accent: Electric Teal #00AEBB
- Semantic Status: Emerald #10B981, Amber #F59E0B, Coral #EF4444

Outputs:
  docs/screenshots/mobile/01_home_dashboard.png
  docs/screenshots/mobile/02_pos_barcode_and_cascade.png
  docs/screenshots/mobile/03_hitl_approvals.png
  docs/screenshots/mobile/04_prescription_scanner.png
  docs/screenshots/mobile/05_coldchain_monitor.png
  docs/screenshots/mobile/06_copilot_and_replay.png
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "docs" / "screenshots" / "mobile"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Tokens
C_BG = (232, 228, 211)        # #E8E4D3 Warm Ivory
C_SURFACE = (255, 255, 255)   # #FFFFFF Clean White
C_ELEVATED = (244, 241, 230)  # #F4F1E6
C_BORDER = (216, 211, 195)    # #D8D3C3
C_TEXT_PRIMARY = (3, 18, 17)  # #031211 Ink Black
C_TEXT_SEC = (92, 88, 78)     # #5C584E Charcoal
C_TEXT_MUTED = (158, 152, 138)# #9E988A
C_TEAL = (0, 174, 187)        # #00AEBB Electric Teal
C_TEAL_LIGHT = (235, 250, 251)
C_EMERALD = (16, 185, 129)    # #10B981
C_AMBER = (245, 158, 11)      # #F59E0B
C_CORAL = (239, 68, 68)       # #EF4444
C_DARK = (3, 18, 17)


def get_fonts():
    try:
        f_title = ImageFont.truetype("arialbd.ttf", 36)
        f_heading = ImageFont.truetype("arialbd.ttf", 28)
        f_sub = ImageFont.truetype("arialbd.ttf", 20)
        f_body = ImageFont.truetype("arial.ttf", 22)
        f_body_bold = ImageFont.truetype("arialbd.ttf", 22)
        f_small = ImageFont.truetype("arial.ttf", 18)
        f_small_bold = ImageFont.truetype("arialbd.ttf", 18)
        f_mono = ImageFont.truetype("cour.ttf", 18)
        f_mono_bold = ImageFont.truetype("courbd.ttf", 20)
    except Exception:
        f_title = ImageFont.load_default()
        f_heading = ImageFont.load_default()
        f_sub = ImageFont.load_default()
        f_body = ImageFont.load_default()
        f_body_bold = ImageFont.load_default()
        f_small = ImageFont.load_default()
        f_small_bold = ImageFont.load_default()
        f_mono = ImageFont.load_default()
        f_mono_bold = ImageFont.load_default()
    return f_title, f_heading, f_sub, f_body, f_body_bold, f_small, f_small_bold, f_mono, f_mono_bold


def create_base_canvas(width=780, height=1688):
    img = Image.new("RGB", (width, height), C_BG)
    draw = ImageDraw.Draw(img)

    # Status Bar
    draw.rectangle([0, 0, width, 88], fill=C_BG)
    # Dynamic Island / Notch
    draw.rounded_rectangle([width // 2 - 100, 20, width // 2 + 100, 60], radius=20, fill=(0, 0, 0))
    # Time 9:41
    try:
        f_status = ImageFont.truetype("arialbd.ttf", 24)
    except Exception:
        f_status = ImageFont.load_default()
    draw.text((60, 40), "09:41", fill=C_TEXT_PRIMARY, font=f_status, anchor="lm")
    # Wifi & Battery dots
    draw.rectangle([width - 120, 36, width - 80, 52], outline=C_TEXT_PRIMARY, width=2)
    draw.rectangle([width - 116, 40, width - 88, 48], fill=C_TEXT_PRIMARY)
    draw.rectangle([width - 80, 42, width - 77, 46], fill=C_TEXT_PRIMARY)

    # Bottom Tab Navigation Bar
    tab_y = height - 140
    draw.rectangle([0, tab_y, width, height], fill=C_SURFACE, outline=C_BORDER, width=2)
    draw.line([0, tab_y, width, tab_y], fill=C_BORDER, width=2)

    return img, draw, tab_y


def draw_tab_bar(draw, active_tab_index, width=780, tab_y=1548):
    tabs = ["Home", "Sell", "Scan Rx", "Approvals", "Copilot"]
    tab_w = width // len(tabs)
    try:
        f_tab = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        f_tab = ImageFont.load_default()

    for i, t in enumerate(tabs):
        cx = i * tab_w + tab_w // 2
        cy = tab_y + 45
        color = C_TEAL if i == active_tab_index else C_TEXT_MUTED
        # Tab icon dot/circle
        draw.ellipse([cx - 10, cy - 22, cx + 10, cy - 2], fill=color)
        draw.text((cx, cy + 18), t, fill=color, font=f_tab, anchor="mm")


def draw_card(draw, x, y, w, h, fill=C_SURFACE, border=C_BORDER, radius=8):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=border, width=2)


def draw_badge(draw, x, y, text, variant="neutral", font=None):
    if font is None:
        try:
            font = ImageFont.truetype("arialbd.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

    bg_map = {
        "emerald": (230, 248, 240),
        "amber": (254, 243, 199),
        "coral": (254, 226, 226),
        "teal": C_TEAL_LIGHT,
        "neutral": C_ELEVATED,
        "dark": C_DARK,
    }
    fg_map = {
        "emerald": C_EMERALD,
        "amber": C_AMBER,
        "coral": C_CORAL,
        "teal": C_TEAL,
        "neutral": C_TEXT_SEC,
        "dark": (232, 228, 211),
    }
    bg = bg_map.get(variant, C_ELEVATED)
    fg = fg_map.get(variant, C_TEXT_SEC)

    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pw, ph = tw + 20, th + 12

    draw.rounded_rectangle([x, y, x + pw, y + ph], radius=4, fill=bg, outline=fg, width=1)
    draw.text((x + pw // 2, y + ph // 2), text, fill=fg, font=font, anchor="mm")
    return pw


# =============================================================================
# SCREEN 1: Home Dashboard
# =============================================================================
def generate_screenshot_01():
    img, draw, tab_y = create_base_canvas()
    f_title, f_heading, f_sub, f_body, f_body_bold, f_small, f_small_bold, f_mono, f_mono_bold = get_fonts()

    # Connection Status Banner
    draw_card(draw, 40, 100, 700, 56, fill=C_SURFACE)
    draw.ellipse([64, 120, 80, 136], fill=C_EMERALD)
    draw.text((96, 128), "LIVE STREAM CONNECTED • NODE SSE READY", fill=C_EMERALD, font=f_small_bold, anchor="lm")
    draw_badge(draw, 640, 114, "LIVE", "emerald", f_small_bold)

    # Operational Node Scope Card
    draw_card(draw, 40, 176, 700, 190, fill=C_SURFACE)
    draw.text((64, 204), "OPERATIONAL NODE SCOPE", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw_badge(draw, 580, 194, "PHARMACY", "teal", f_small_bold)
    draw.text((64, 256), "Apollo Pharmacy - Connaught Place", fill=C_TEXT_PRIMARY, font=f_heading, anchor="lm")
    draw.text((64, 298), "Autonomous demand cascade propagation active across 4 supply tiers.", fill=C_TEXT_SEC, font=f_small, anchor="lm")
    draw.text((64, 334), "Node ID: 11111111-1111-1111-1111-111111111111 • Tier 1 Edge", fill=C_TEXT_MUTED, font=f_mono, anchor="lm")

    # 2x2 KPI Grid
    kpi_w = 338
    # KPI 1
    draw_card(draw, 40, 386, kpi_w, 140, fill=C_SURFACE)
    draw.text((64, 436), "14", fill=C_TEXT_PRIMARY, font=f_title, anchor="lm")
    draw.text((64, 486), "EVENTS TODAY", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")

    # KPI 2
    draw_card(draw, 402, 386, kpi_w, 140, fill=C_SURFACE)
    draw.text((426, 436), "2", fill=C_CORAL, font=f_title, anchor="lm")
    draw.text((426, 486), "LOW-STOCK ALERTS", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")

    # KPI 3
    draw_card(draw, 40, 546, kpi_w, 140, fill=C_SURFACE)
    draw.text((64, 596), "3", fill=C_AMBER, font=f_title, anchor="lm")
    draw.text((64, 646), "PENDING APPROVALS →", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")

    # KPI 4
    draw_card(draw, 402, 546, kpi_w, 140, fill=C_SURFACE)
    draw.text((426, 596), "1", fill=C_CORAL, font=f_title, anchor="lm")
    draw.text((426, 646), "QUARANTINED BATCHES →", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")

    # Latest Demand Cascade Banner
    draw_card(draw, 40, 706, 700, 110, fill=C_DARK)
    draw.text((64, 736), "⚡ LATEST SINGLE-STRIP DEMAND CASCADE", fill=C_TEAL, font=f_small_bold, anchor="lm")
    draw.text((64, 774), "casc-8f92a1b4 • Propagated across 4 tiers in 184ms", fill=(232, 228, 211), font=f_body_bold, anchor="lm")
    draw.text((610, 774), "VIEW →", fill=C_TEAL, font=f_small_bold, anchor="lm")

    # Activity Feed Header
    draw.text((40, 856), "REAL-TIME ACTIVITY FEED", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw_badge(draw, 620, 842, "14 EVENTS", "neutral", f_small_bold)

    # Activity Feed Items
    items = [
        ("POS Retail Depletion", "1 strip Paracetamol 650mg dispensed. Safety buffer recalculated.", "casc-8f92a1b4", "Just now", C_EMERALD),
        ("Cold-Chain Warning", "Sensor batch BIO-INS-01 thermal spike to 8.4°C at West Hub.", "coldchain-991", "2m ago", C_CORAL),
        ("Replenishment PO Generated", "Stockist Hub generated automated PO #STK-2092 to Regional Depot.", "casc-8f92a1b4", "5m ago", C_TEAL),
        ("HITL Approval Request", "Cross-border insulin shipment queued for Raxaul ICP authorization.", "hitl-task-01", "12m ago", C_AMBER),
    ]
    curr_y = 886
    for title, desc, cid, timestamp, dot_col in items:
        draw_card(draw, 40, curr_y, 700, 136, fill=C_SURFACE)
        draw.ellipse([64, curr_y + 30, 78, curr_y + 44], fill=dot_col)
        draw.text((92, curr_y + 36), title, fill=C_TEXT_PRIMARY, font=f_body_bold, anchor="lm")
        draw.text((640, curr_y + 36), timestamp, fill=C_TEXT_MUTED, font=f_small, anchor="rm")
        draw.text((64, curr_y + 74), desc, fill=C_TEXT_SEC, font=f_small, anchor="lm")
        draw.text((64, curr_y + 108), f"Ref: {cid}", fill=C_TEXT_MUTED, font=f_mono, anchor="lm")
        curr_y += 152

    draw_tab_bar(draw, 0, tab_y=tab_y)
    img.save(OUTPUT_DIR / "01_home_dashboard.png")
    print(f"Generated {OUTPUT_DIR / '01_home_dashboard.png'}")


# =============================================================================
# SCREEN 2: POS Barcode & Cascade
# =============================================================================
def generate_screenshot_02():
    img, draw, tab_y = create_base_canvas()
    f_title, f_heading, f_sub, f_body, f_body_bold, f_small, f_small_bold, f_mono, f_mono_bold = get_fonts()

    # Header
    draw.text((40, 120), "RETAIL COUNTER DISPENSING", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw.text((40, 160), "Pharmacy POS Lite", fill=C_TEXT_PRIMARY, font=f_title, anchor="lm")
    draw_badge(draw, 600, 138, "FEFO LOCKED", "emerald", f_small_bold)

    # Barcode Viewport Card
    draw_card(draw, 40, 196, 700, 220, fill=C_DARK)
    # Scanning reticle
    reticle_w, reticle_h = 360, 120
    rx = 40 + (700 - reticle_w) // 2
    ry = 196 + (220 - reticle_h) // 2
    draw.rectangle([rx, ry, rx + reticle_w, ry + reticle_h], outline=C_TEAL, width=3)
    # Red scan laser
    draw.line([rx + 10, ry + reticle_h // 2, rx + reticle_w - 10, ry + reticle_h // 2], fill=C_CORAL, width=2)
    draw.text((width_center := 390, 386), "BARCODE DETECTED: 8901000000018", fill=(232, 228, 211), font=f_mono_bold, anchor="mm")

    # Scanned Product Card
    draw_card(draw, 40, 436, 700, 230, fill=C_SURFACE)
    draw.text((64, 468), "Paracetamol 650mg Tablets", fill=C_TEXT_PRIMARY, font=f_heading, anchor="lm")
    draw.text((64, 504), "Generic: Paracetamol • SKU: MED-PCM-650", fill=C_TEXT_SEC, font=f_body, anchor="lm")
    draw_badge(draw, 64, 530, "OTC", "neutral", f_small_bold)
    draw_badge(draw, 140, 530, "FEFO BATCH B-PCM-01", "emerald", f_small_bold)
    draw.text((64, 616), "Unit Retail Price: ₹ 1.89 / strip", fill=C_TEXT_PRIMARY, font=f_heading, anchor="lm")
    draw.text((580, 616), "Qty: 1 strip", fill=C_TEXT_SEC, font=f_body_bold, anchor="rm")

    # Dispense Action Button
    draw_card(draw, 40, 686, 700, 64, fill=C_TEAL, radius=6)
    draw.text((390, 718), "⚡ DISPENSE & PROPAGATE CASCADE", fill=C_DARK, font=f_sub, anchor="mm")

    # Live Cascade Timeline Container
    draw.text((40, 786), "INSTANTANEOUS 5-STAGE DEMAND PROPAGATION", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw_card(draw, 40, 810, 700, 690, fill=C_SURFACE)

    stages = [
        ("Supervisor Router", "Demand signal classified as retail strip depletion.", "32ms • 48 tokens", C_EMERALD),
        ("Pharmacy Edge (T1)", "Deducted 1 strip from local shelf. Crossed reorder threshold.", "45ms • 62 tokens", C_EMERALD),
        ("Stockist Hub (T2)", "Safety buffer intact. Automated replenishment PO #STK-09 dispatched.", "68ms • 95 tokens", C_EMERALD),
        ("Distributor Layer (T3)", "Regional dispatch manifest queued for vehicle DL-1RA-4092.", "52ms • 78 tokens", C_EMERALD),
        ("Manufacturer Plant (T4)", "Production schedule updated with new regional consumption rate.", "48ms • 112 tokens", C_EMERALD),
    ]

    sy = 840
    for idx, (st_name, st_desc, st_meta, col) in enumerate(stages):
        # Step node
        draw.ellipse([70, sy + 10, 94, sy + 34], fill=col)
        draw.text((82, sy + 22), str(idx + 1), fill=(255, 255, 255), font=f_small_bold, anchor="mm")
        if idx < len(stages) - 1:
            draw.line([82, sy + 36, 82, sy + 120], fill=C_BORDER, width=2)

        draw.text((116, sy + 14), st_name, fill=C_TEXT_PRIMARY, font=f_body_bold, anchor="lm")
        draw.text((680, sy + 14), "DONE", fill=C_EMERALD, font=f_small_bold, anchor="rm")
        draw.text((116, sy + 46), st_desc, fill=C_TEXT_SEC, font=f_small, anchor="lm")
        draw.text((116, sy + 80), st_meta, fill=C_TEXT_MUTED, font=f_mono, anchor="lm")
        sy += 122

    draw_tab_bar(draw, 1, tab_y=tab_y)
    img.save(OUTPUT_DIR / "02_pos_barcode_and_cascade.png")
    print(f"Generated {OUTPUT_DIR / '02_pos_barcode_and_cascade.png'}")


# =============================================================================
# SCREEN 3: HITL Approvals
# =============================================================================
def generate_screenshot_03():
    img, draw, tab_y = create_base_canvas()
    f_title, f_heading, f_sub, f_body, f_body_bold, f_small, f_small_bold, f_mono, f_mono_bold = get_fonts()

    # Header
    draw.text((40, 120), "HUMAN-IN-THE-LOOP CONTROL PLANE", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw.text((40, 160), "Escalated Approvals", fill=C_TEXT_PRIMARY, font=f_title, anchor="lm")
    draw_badge(draw, 580, 138, "DECISION RIGHTS", "teal", f_small_bold)

    # Filter Segment
    draw_card(draw, 40, 196, 700, 56, fill=C_ELEVATED)
    draw_card(draw, 44, 200, 346, 48, fill=C_SURFACE)
    draw.text((217, 224), "Pending (2)", fill=C_TEXT_PRIMARY, font=f_small_bold, anchor="mm")
    draw.text((565, 224), "Decided Archive (8)", fill=C_TEXT_SEC, font=f_small, anchor="mm")

    # Task Card 1: Cross Border Shipment
    draw_card(draw, 40, 276, 700, 530, fill=C_SURFACE)
    draw_badge(draw, 64, 304, "CROSS-BORDER SHIPMENT", "neutral", f_small_bold)
    draw_badge(draw, 340, 304, "HIGH RISK", "coral", f_small_bold)
    draw.text((680, 316), "⏳ 11h 48m left", fill=C_AMBER, font=f_small_bold, anchor="rm")

    draw.text((64, 370), "Insulin Glargine Consignment Dispatch", fill=C_TEXT_PRIMARY, font=f_heading, anchor="lm")
    draw.text((64, 410), "Route: Mumbai West Hub → Raxaul ICP Border Corridor (1,380 km)", fill=C_TEXT_SEC, font=f_body, anchor="lm")

    # Inner Details Box
    draw_card(draw, 64, 446, 652, 190, fill=C_ELEVATED)
    draw.text((88, 478), "Consignment: 250 units Insulin Glargine 100IU (₹ 4,25,000)", fill=C_TEXT_PRIMARY, font=f_body_bold, anchor="lm")
    draw.text((88, 514), "Requirements: Cold-Chain 2°C–8°C continuous log + Customs Form 14A", fill=C_TEXT_SEC, font=f_small, anchor="lm")
    draw.text((88, 550), "Agent Reasoning: Lifesaving consignment crossing state/border boundary.", fill=C_TEXT_SEC, font=f_small, anchor="lm")
    draw.text((88, 586), "Mandatory dual-custody authorization required before gate release.", fill=C_TEXT_SEC, font=f_small, anchor="lm")

    # Action Buttons
    draw_card(draw, 64, 666, 316, 56, fill=C_SURFACE, border=C_CORAL)
    draw.text((222, 694), "REJECT CONSIGNMENT", fill=C_CORAL, font=f_small_bold, anchor="mm")
    draw_card(draw, 400, 666, 316, 56, fill=C_EMERALD)
    draw.text((558, 694), "✓ BIOMETRIC AUTHORIZE", fill=(255, 255, 255), font=f_small_bold, anchor="mm")

    draw.text((64, 760), "Escalated by Distributor Fleet Agent • Correlation: casc-sim-35a9", fill=C_TEXT_MUTED, font=f_mono, anchor="lm")

    # Task Card 2: Batch Surge Upscale
    draw_card(draw, 40, 836, 700, 520, fill=C_SURFACE)
    draw_badge(draw, 64, 864, "BATCH MODIFICATION", "neutral", f_small_bold)
    draw_badge(draw, 310, 864, "SURGE DEMAND", "amber", f_small_bold)
    draw.text((680, 876), "⏳ 23h 12m left", fill=C_AMBER, font=f_small_bold, anchor="rm")

    draw.text((64, 930), "Amoxicillin 500mg Batch Upscale (+70%)", fill=C_TEXT_PRIMARY, font=f_heading, anchor="lm")
    draw.text((64, 970), "Line: Sun Pharma Baddi • Proposed: 5,000 → 8,500 units", fill=C_TEXT_SEC, font=f_body, anchor="lm")

    draw_card(draw, 64, 1006, 652, 170, fill=C_ELEVATED)
    draw.text((88, 1038), "Trigger: Real-time retail depletion surge across northern districts.", fill=C_TEXT_PRIMARY, font=f_body_bold, anchor="lm")
    draw.text((88, 1074), "Impact: Raw API stock will drop from 120 kg to 35 kg (near buffer).", fill=C_TEXT_SEC, font=f_small, anchor="lm")
    draw.text((88, 1110), "Plant manager approval required to commit raw ingredient buffer.", fill=C_TEXT_SEC, font=f_small, anchor="lm")

    draw_card(draw, 64, 1206, 316, 56, fill=C_SURFACE, border=C_CORAL)
    draw.text((222, 1234), "HOLD AT 5,000", fill=C_CORAL, font=f_small_bold, anchor="mm")
    draw_card(draw, 400, 1206, 316, 56, fill=C_EMERALD)
    draw.text((558, 1234), "✓ APPROVE UPSCALE", fill=(255, 255, 255), font=f_small_bold, anchor="mm")

    draw.text((64, 1300), "Escalated by Plant Production Agent • Baddi Formulation Unit", fill=C_TEXT_MUTED, font=f_mono, anchor="lm")

    draw_tab_bar(draw, 3, tab_y=tab_y)
    img.save(OUTPUT_DIR / "03_hitl_approvals.png")
    print(f"Generated {OUTPUT_DIR / '03_hitl_approvals.png'}")


# =============================================================================
# SCREEN 4: Prescription Scanner
# =============================================================================
def generate_screenshot_04():
    img, draw, tab_y = create_base_canvas()
    f_title, f_heading, f_sub, f_body, f_body_bold, f_small, f_small_bold, f_mono, f_mono_bold = get_fonts()

    # Header
    draw.text((40, 120), "LOCAL SOVEREIGN PIPELINE", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw.text((40, 160), "Prescription Scanner", fill=C_TEXT_PRIMARY, font=f_title, anchor="lm")
    draw_badge(draw, 560, 138, "SCHEDULE H AUDIT", "teal", f_small_bold)

    # Capture Viewfinder Box
    draw_card(draw, 40, 196, 700, 360, fill=C_DARK)
    # Viewfinder corners
    draw.rectangle([100, 240, 680, 500], outline=C_TEAL, width=2)
    # Simulated Rx Document inside
    draw_card(draw, 140, 260, 500, 220, fill=(245, 245, 242))
    draw.text((160, 285), "Dr. Rajiv Sharma, MD • Reg No: MCI-2018-94812", fill=(40, 40, 40), font=f_small_bold, anchor="lm")
    draw.line([160, 305, 620, 305], fill=(200, 200, 200), width=1)
    draw.text((160, 335), "Patient: R.K. (Male, 48y) • Date: 16-Nov-2026", fill=(70, 70, 70), font=f_small, anchor="lm")
    draw.text((160, 375), "Rx: Tab Amoxicillin 500mg - 1 TID x 5 days", fill=(20, 20, 20), font=f_body_bold, anchor="lm")
    draw.text((160, 415), "Signature: [Verified Doctor Digital Signature]", fill=(90, 90, 90), font=f_small, anchor="lm")
    draw.text((390, 530), "PRESCRIPTION DOCUMENT DETECTED & OCR VERIFIED", fill=C_TEAL, font=f_mono_bold, anchor="mm")

    # 4-Stage Extraction Pipeline Results Card
    draw_card(draw, 40, 576, 700, 470, fill=C_SURFACE)
    draw.text((64, 608), "SOVEREIGN EXTRACTION PIPELINE", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw_badge(draw, 560, 594, "STATUS: APPROVED", "emerald", f_small_bold)

    steps = [
        ("1. Optical Character Recognition", "Extracted 12 handwritten/printed fields with 96.4% confidence.", C_EMERALD),
        ("2. Doctor Credential Verification", "Dr. Rajiv Sharma verified against NMC Registry (MCI-2018-94812).", C_EMERALD),
        ("3. Schedule H Drug Identification", "Identified: Amoxicillin 500mg (Antibiotic - Schedule H lock).", C_EMERALD),
        ("4. Sovereign Privacy Compliance", "Patient initials 'R.K.' retained. Ephemeral camera cache cleared.", C_EMERALD),
    ]

    py = 648
    for title, desc, col in steps:
        draw.ellipse([68, py + 12, 88, py + 32], fill=col)
        draw.text((106, py + 14), title, fill=C_TEXT_PRIMARY, font=f_body_bold, anchor="lm")
        draw.text((106, py + 44), desc, fill=C_TEXT_SEC, font=f_small, anchor="lm")
        py += 76

    draw.text((64, 1000), "Prescription Audit ID: rx-7f41c9b2 • Ready for Schedule H POS Linking", fill=C_TEXT_MUTED, font=f_mono, anchor="lm")

    # Link to Sale Button
    draw_card(draw, 40, 1070, 700, 64, fill=C_TEAL, radius=6)
    draw.text((390, 1102), "PROCEED TO POS SALE WITH ATTACHED RX →", fill=C_DARK, font=f_sub, anchor="mm")

    draw_tab_bar(draw, 2, tab_y=tab_y)
    img.save(OUTPUT_DIR / "04_prescription_scanner.png")
    print(f"Generated {OUTPUT_DIR / '04_prescription_scanner.png'}")


# =============================================================================
# SCREEN 5: Cold-Chain Monitor
# =============================================================================
def generate_screenshot_05():
    img, draw, tab_y = create_base_canvas()
    f_title, f_heading, f_sub, f_body, f_body_bold, f_small, f_small_bold, f_mono, f_mono_bold = get_fonts()

    # Header
    draw.text((40, 120), "TELEMETRY MONITOR & AUTONOMOUS QUARANTINE", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw.text((40, 160), "Cold-Chain Biologics", fill=C_TEXT_PRIMARY, font=f_title, anchor="lm")
    draw_badge(draw, 580, 138, "2°C–8°C COMPLIANCE", "teal", f_small_bold)

    # View Mode Toggle
    draw_card(draw, 40, 196, 700, 56, fill=C_ELEVATED)
    draw_card(draw, 44, 200, 346, 48, fill=C_SURFACE)
    draw.text((217, 224), "Monitored Batches (3)", fill=C_TEXT_PRIMARY, font=f_small_bold, anchor="mm")
    draw.text((565, 224), "Quarantine History (1)", fill=C_TEXT_SEC, font=f_small, anchor="mm")

    # SVG-style Telemetry Chart Card
    draw_card(draw, 40, 276, 700, 380, fill=C_SURFACE)
    draw.text((64, 308), "BATCH BIO-INS-01 • INSULIN GLARGINE", fill=C_TEXT_PRIMARY, font=f_body_bold, anchor="lm")
    draw_badge(draw, 560, 296, "EXCURSION: 8.8°C", "coral", f_small_bold)

    # Chart Area
    cx, cy, cw, ch = 80, 350, 620, 220
    draw.rectangle([cx, cy, cx + cw, cy + ch], fill=C_ELEVATED)

    # Safe Zone Green Band (2°C to 8°C)
    # Top line = 8°C, bottom line = 2°C
    band_top = cy + 50
    band_bottom = cy + 170
    draw.rectangle([cx, band_top, cx + cw, band_bottom], fill=(235, 248, 240))
    draw.line([cx, band_top, cx + cw, band_top], fill=C_AMBER, width=2)
    draw.text((cx + 10, band_top - 18), "MAX THRESHOLD 8.0°C", fill=C_AMBER, font=f_small_bold, anchor="lm")
    draw.line([cx, band_bottom, cx + cw, band_bottom], fill=C_AMBER, width=2)
    draw.text((cx + 10, band_bottom + 18), "MIN THRESHOLD 2.0°C", fill=C_AMBER, font=f_small_bold, anchor="lm")

    # Time series points & line
    points = [
        (cx + 40, cy + 120),
        (cx + 140, cy + 110),
        (cx + 240, cy + 90),
        (cx + 340, cy + 60),
        (cx + 440, cy + 25),  # Breach! 8.8°C
        (cx + 540, cy + 30),
    ]
    for i in range(len(points) - 1):
        color = C_CORAL if points[i + 1][1] < band_top else C_TEAL
        draw.line([points[i], points[i + 1]], fill=color, width=3)

    for px, py in points:
        pt_col = C_CORAL if py < band_top else C_TEAL
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=pt_col)

    draw.text((64, 610), "Thermal Excursion Detected: 8.8°C sustained for 32 minutes at Hub West.", fill=C_CORAL, font=f_small_bold, anchor="lm")

    # Excursion Analyst Auto-Quarantine Card
    draw_card(draw, 40, 680, 700, 360, fill=C_SURFACE)
    draw_badge(draw, 64, 708, "AUTONOMOUS QUARANTINE ACTION", "coral", f_small_bold)
    draw.text((680, 720), "Action ID: qact-9102", fill=C_TEXT_MUTED, font=f_mono, anchor="rm")

    draw.text((64, 766), "Batch BIO-INS-01 Locked & Isolated", fill=C_TEXT_PRIMARY, font=f_heading, anchor="lm")
    draw.text((64, 804), "Arrhenius Degradation Model: Estimated remaining potency reduced from 98.2% to 84.1%.", fill=C_TEXT_SEC, font=f_body, anchor="lm")

    draw_card(draw, 64, 840, 652, 110, fill=C_ELEVATED)
    draw.text((88, 868), "• POS Dispense Lock: Active (Cannot dispense quarantined units)", fill=C_TEXT_PRIMARY, font=f_small_bold, anchor="lm")
    draw.text((88, 902), "• Push Notification dispatched to Logistics Manager & Quality Team", fill=C_TEXT_PRIMARY, font=f_small_bold, anchor="lm")

    # 1-Tap Trigger Rebalance Button
    draw_card(draw, 64, 966, 652, 54, fill=C_TEAL, radius=6)
    draw.text((390, 993), "⚡ TRIGGER AUTONOMOUS REBALANCE CASCADE →", fill=C_DARK, font=f_sub, anchor="mm")

    draw_tab_bar(draw, 3, tab_y=tab_y)
    img.save(OUTPUT_DIR / "05_coldchain_monitor.png")
    print(f"Generated {OUTPUT_DIR / '05_coldchain_monitor.png'}")


# =============================================================================
# SCREEN 6: Copilot & Replay
# =============================================================================
def generate_screenshot_06():
    img, draw, tab_y = create_base_canvas()
    f_title, f_heading, f_sub, f_body, f_body_bold, f_small, f_small_bold, f_mono, f_mono_bold = get_fonts()

    # Header
    draw.text((40, 120), "NATURAL LANGUAGE SUPPLY CHAIN INTELLIGENCE", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw.text((40, 160), "Network Copilot", fill=C_TEXT_PRIMARY, font=f_title, anchor="lm")
    draw_badge(draw, 600, 138, "RLS SCOPED", "teal", f_small_bold)

    # User Query Bubble
    draw_card(draw, 140, 206, 600, 100, fill=C_DARK, radius=8)
    draw.text((164, 236), "Which medicines are near stockout at my pharmacy?", fill=(232, 228, 211), font=f_body_bold, anchor="lm")
    draw.text((710, 280), "09:38 • Apollo Pharmacy Node", fill=C_TEAL, font=f_small, anchor="rm")

    # Copilot Response Bubble
    draw_card(draw, 40, 326, 700, 570, fill=C_SURFACE, radius=8)
    draw.text((64, 356), "🤖 MEDIFLUX COPILOT", fill=C_TEAL, font=f_small_bold, anchor="lm")
    draw.text((680, 356), "Just now", fill=C_TEXT_MUTED, font=f_small, anchor="rm")

    # Progressive Thinking Steps Pill
    draw_card(draw, 64, 386, 652, 60, fill=C_ELEVATED)
    draw.ellipse([84, 408, 100, 424], fill=C_EMERALD)
    draw.text((114, 416), "Evaluated 3 tools: check_inventory, get_stockout_risk, get_cascades", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")

    # Copilot Answer Content
    answer_lines = [
        "Based on real-time inventory at Apollo Pharmacy - Connaught Place:",
        "1. Paracetamol 650mg: 8 units remaining (Safety buffer: 15 units).",
        "   Stockout risk: HIGH. Autonomous replenishment PO #STK-09 already",
        "   propagated to Stockist Hub via demand cascade.",
        "2. Amoxicillin 500mg: 12 units remaining. Buffer intact.",
        "3. Insulin Glargine: 0 units available (Quarantined due to excursion).",
    ]
    ay = 470
    for line in answer_lines:
        font = f_body_bold if line.startswith("1.") or line.startswith("2.") or line.startswith("3.") else f_body
        draw.text((64, ay), line, fill=C_TEXT_PRIMARY, font=font, anchor="lm")
        ay += 32

    # Tappable Reference Chips
    draw.text((64, 700), "GROUNDED REFERENCE CHIPS (1-TAP DEEP LINK):", fill=C_TEXT_SEC, font=f_small_bold, anchor="lm")
    draw_card(draw, 64, 726, 290, 48, fill=C_ELEVATED, border=C_TEAL)
    draw.text((209, 750), "💊 Paracetamol 650mg → Sell", fill=C_TEAL, font=f_small_bold, anchor="mm")

    draw_card(draw, 370, 726, 310, 48, fill=C_ELEVATED, border=C_AMBER)
    draw.text((525, 750), "⚡ Cascade: casc-8f92a1b4 →", fill=C_AMBER, font=f_small_bold, anchor="mm")

    draw_card(draw, 64, 786, 360, 48, fill=C_ELEVATED, border=C_CORAL)
    draw.text((244, 810), "❄️ Quarantined Batch BIO-INS-01 →", fill=C_CORAL, font=f_small_bold, anchor="mm")

    # Interactive Replay Controller Card
    draw_card(draw, 40, 920, 700, 240, fill=C_DARK)
    draw.text((64, 952), "CASCADE TIMELINE REPLAY CONTROLLER", fill=C_TEAL, font=f_small_bold, anchor="lm")
    draw.text((680, 952), "casc-8f92a1b4", fill=(232, 228, 211), font=f_mono, anchor="rm")

    # Scrubber Bar
    draw.line([64, 1000, 716, 1000], fill=C_TEXT_SEC, width=6)
    draw.line([64, 1000, 520, 1000], fill=C_TEAL, width=6)
    draw.ellipse([510, 990, 530, 1010], fill=(255, 255, 255))
    draw.text((64, 1030), "Stage 4 of 5: Distributor Layer Replay (0.18s elapsed)", fill=(232, 228, 211), font=f_small, anchor="lm")

    # Playback Controls
    draw_card(draw, 64, 1060, 120, 54, fill=C_TEAL)
    draw.text((124, 1087), "⏸ PAUSE", fill=C_DARK, font=f_small_bold, anchor="mm")

    draw_card(draw, 200, 1060, 100, 54, fill=C_ELEVATED)
    draw.text((250, 1087), "1x", fill=C_TEXT_PRIMARY, font=f_small_bold, anchor="mm")

    draw_card(draw, 316, 1060, 100, 54, fill=C_TEAL)
    draw.text((366, 1087), "2x ACTIVE", fill=C_DARK, font=f_small_bold, anchor="mm")

    draw_card(draw, 432, 1060, 100, 54, fill=C_ELEVATED)
    draw.text((482, 1087), "4x", fill=C_TEXT_PRIMARY, font=f_small_bold, anchor="mm")

    draw_card(draw, 548, 1060, 168, 54, fill=C_ELEVATED)
    draw.text((632, 1087), "RESTART ↺", fill=C_TEXT_PRIMARY, font=f_small_bold, anchor="mm")

    draw_tab_bar(draw, 4, tab_y=tab_y)
    img.save(OUTPUT_DIR / "06_copilot_and_replay.png")
    print(f"Generated {OUTPUT_DIR / '06_copilot_and_replay.png'}")


def main():
    print("Generating 6 high-DPI pixel-accurate mobile UI screenshots...")
    generate_screenshot_01()
    generate_screenshot_02()
    generate_screenshot_03()
    generate_screenshot_04()
    generate_screenshot_05()
    generate_screenshot_06()
    print("All 6 mobile screenshots generated successfully.")


if __name__ == "__main__":
    main()

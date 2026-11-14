"""Script to generate realistic synthetic prescription images with clean layout and embedded metadata."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

FIXTURES_DATA = [
    {
        "filename": "valid_prescription.png",
        "clinic": "CITY HEALTH CLINIC",
        "address": "123 Healthcare Avenue, Mumbai - 400001 | Tel: +91 22 5555 0199",
        "doctor_name": "Dr. A. K. Sharma",
        "qualification": "MBBS, MD (Medicine)",
        "doctor_reg_no": "MCI-2019-88412",
        "patient_name": "R.K.",
        "patient_initials": "R.K.",
        "age_gender": "Age: 35 | Gender: Male",
        "date": "2026-11-10",
        "drugs": [
            {
                "name": "Paracetamol 500mg",
                "dose": "500mg",
                "frequency": "1 tab TDS x 5 days",
                "quantity": 15,
                "sku": "MED-PCM-500",
                "product_id": "p-paracetamol-500",
            }
        ],
        "signature": "Dr. A. K. Sharma",
    },
    {
        "filename": "missing_reg_no.png",
        "clinic": "METRO CARE CLINIC",
        "address": "22 Park Street, Kolkata - 700016 | Tel: +91 33 2222 8811",
        "doctor_name": "Dr. Ramesh Gupta",
        "qualification": "MBBS",
        "doctor_reg_no": None,  # Missing/blank
        "patient_name": "S.M.",
        "patient_initials": "S.M.",
        "age_gender": "Age: 42 | Gender: Female",
        "date": "2026-11-10",
        "drugs": [
            {
                "name": "Amoxicillin 500mg",
                "dose": "500mg",
                "frequency": "1 cap TDS x 5 days",
                "quantity": 15,
                "sku": "MED-AMX-500",
                "product_id": "p-amoxicillin-500",
            }
        ],
        "signature": "Dr. Ramesh Gupta",
    },
    {
        "filename": "unknown_doctor.png",
        "clinic": "SUNSHINE POLYCLINIC",
        "address": "88 Hill Road, Bengaluru - 560001 | Tel: +91 80 4111 2233",
        "doctor_name": "Dr. Vikram Ghost",
        "qualification": "MBBS",
        "doctor_reg_no": "FAKE-9999-00000",
        "patient_name": "A.P.",
        "patient_initials": "A.P.",
        "age_gender": "Age: 29 | Gender: Female",
        "date": "2026-11-10",
        "drugs": [
            {
                "name": "Azithromycin 500mg",
                "dose": "500mg",
                "frequency": "1 tab OD x 3 days",
                "quantity": 3,
                "sku": "MED-AZI-500",
                "product_id": "p-001-azithromycin",
            }
        ],
        "signature": "Dr. Vikram Ghost",
    },
    {
        "filename": "schedule_h_prescription.png",
        "clinic": "CITY HEALTH CLINIC",
        "address": "123 Healthcare Avenue, Mumbai - 400001 | Tel: +91 22 5555 0199",
        "doctor_name": "Dr. A. K. Sharma",
        "qualification": "MBBS, MD (Medicine)",
        "doctor_reg_no": "MCI-2019-88412",
        "patient_name": "H.P.",
        "patient_initials": "H.P.",
        "age_gender": "Age: 50 | Gender: Male",
        "date": "2026-11-10",
        "drugs": [
            {
                "name": "Amoxicillin 500mg",
                "dose": "500mg",
                "frequency": "1 cap TDS x 5 days",
                "quantity": 15,
                "sku": "MED-AMX-500",
                "product_id": "p-amoxicillin-500",
            }
        ],
        "signature": "Dr. A. K. Sharma",
    },
    {
        "filename": "unlisted_drug.png",
        "clinic": "CITY HEALTH CLINIC",
        "address": "123 Healthcare Avenue, Mumbai - 400001 | Tel: +91 22 5555 0199",
        "doctor_name": "Dr. A. K. Sharma",
        "qualification": "MBBS, MD (Medicine)",
        "doctor_reg_no": "MCI-2019-88412",
        "patient_name": "N.D.",
        "patient_initials": "N.D.",
        "age_gender": "Age: 61 | Gender: Female",
        "date": "2026-11-10",
        "drugs": [
            {
                "name": "Xenorab-ZX 999mg",
                "dose": "999mg",
                "frequency": "1 tab OD x 10 days",
                "quantity": 10,
                "sku": None,
                "product_id": None,
            }
        ],
        "signature": "Dr. A. K. Sharma",
    },
]


def render_prescription_image(data: dict) -> tuple[Image.Image, PngInfo]:
    """Render a clean, high-contrast prescription scan image and construct PngInfo."""
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Use default font
    try:
        font_title = ImageFont.truetype("arial.ttf", 24)
        font_sub = ImageFont.truetype("arial.ttf", 16)
        font_body = ImageFont.truetype("arial.ttf", 18)
        font_bold = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # Outer decorative border
    draw.rectangle([(20, 20), (width - 20, height - 20)], outline=(60, 60, 60), width=2)
    draw.line([(20, 140), (width - 20, 140)], fill=(0, 174, 187), width=3)

    # Header
    draw.text((40, 35), data["clinic"], fill=(3, 18, 17), font=font_title)
    draw.text((40, 70), f"{data['doctor_name']}, {data['qualification']}", fill=(50, 50, 50), font=font_sub)
    reg_text = f"Reg No: {data['doctor_reg_no']}" if data["doctor_reg_no"] else "Reg No: NONE"
    draw.text((40, 92), reg_text, fill=(80, 80, 80), font=font_sub)
    draw.text((40, 114), data["address"], fill=(100, 100, 100), font=font_sub)

    # Patient Details Banner
    draw.rectangle([(40, 155), (width - 40, 215)], outline=(200, 200, 200), fill=(245, 245, 240), width=1)
    draw.text((55, 168), f"Patient: {data['patient_name']}", fill=(3, 18, 17), font=font_bold)
    draw.text((55, 190), data["age_gender"], fill=(60, 60, 60), font=font_sub)
    draw.text((width - 200, 168), f"Date: {data['date']}", fill=(3, 18, 17), font=font_sub)

    # Rx Symbol
    draw.text((55, 240), "Rx", fill=(0, 174, 187), font=font_title)
    draw.line([(55, 275), (width - 40, 275)], fill=(220, 220, 220), width=1)

    # Prescribed Drugs
    y_pos = 300
    for idx, drug in enumerate(data["drugs"], 1):
        drug_line = f"{idx}. {drug['name']} — {drug['dose']}"
        draw.text((60, y_pos), drug_line, fill=(3, 18, 17), font=font_bold)
        y_pos += 30
        draw.text((85, y_pos), f"Sig: {drug['frequency']}", fill=(60, 60, 60), font=font_body)
        y_pos += 25
        draw.text((85, y_pos), f"Dispense: Qty {drug['quantity']}", fill=(90, 90, 90), font=font_sub)
        y_pos += 50

    # Clinic Notice / Footer
    draw.line([(40, height - 160), (width - 40, height - 160)], fill=(200, 200, 200), width=1)
    draw.text((55, height - 145), "Important: Substitute with generic permitted unless indicated otherwise.", fill=(120, 120, 120), font=font_sub)
    draw.text((55, height - 125), "Please follow prescribed dosage instructions carefully.", fill=(120, 120, 120), font=font_sub)

    # Doctor Signature
    draw.text((width - 280, height - 110), f"Signed: {data['signature']}", fill=(3, 18, 17), font=font_bold)
    if data["doctor_reg_no"]:
        draw.text((width - 280, height - 85), f"Reg: {data['doctor_reg_no']}", fill=(80, 80, 80), font=font_sub)

    # Assemble raw OCR text representation
    raw_lines = [
        data["clinic"],
        f"{data['doctor_name']}, {data['qualification']}",
        reg_text,
        data["address"],
        f"Patient: {data['patient_name']}",
        data["age_gender"],
        f"Date: {data['date']}",
        "Rx",
    ]
    for idx, drug in enumerate(data["drugs"], 1):
        raw_lines.append(f"{idx}. {drug['name']} {drug['dose']}")
        raw_lines.append(f"Sig: {drug['frequency']}")
        raw_lines.append(f"Dispense: Qty {drug['quantity']}")
    raw_lines.append(f"Signed: {data['signature']}")
    if data["doctor_reg_no"]:
        raw_lines.append(f"Reg: {data['doctor_reg_no']}")
    raw_text = "\n".join(raw_lines)

    # Create PngInfo chunk
    pnginfo = PngInfo()
    pnginfo.add_text("raw_text", raw_text)
    if data["doctor_name"]:
        pnginfo.add_text("doctor_name", data["doctor_name"])
    if data["doctor_reg_no"]:
        pnginfo.add_text("doctor_registration_no", data["doctor_reg_no"])
    else:
        pnginfo.add_text("doctor_registration_no", "NONE")
    pnginfo.add_text("patient_initials", data["patient_initials"])
    pnginfo.add_text("drugs_json", json.dumps(data["drugs"]))

    return img, pnginfo


def main():
    dest_dirs = [
        Path("fixtures/prescriptions"),
        Path("backend/fixtures/prescriptions"),
    ]
    for d in dest_dirs:
        d.mkdir(parents=True, exist_ok=True)

    for item in FIXTURES_DATA:
        img, pnginfo = render_prescription_image(item)
        for d in dest_dirs:
            out_file = d / item["filename"]
            img.save(out_file, "PNG", pnginfo=pnginfo)
            print(f"Generated fixture: {out_file}")


if __name__ == "__main__":
    main()

# app.py
import io
import re
from pathlib import Path
from typing import List, Dict

import streamlit as st
import pandas as pd
from PIL import Image
import numpy as np
import cv2
import pytesseract

# If tesseract not in PATH on Windows, uncomment & set your path:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

COLUMNS = [
    "Carrier", "Flight No.", "From", "To", "Departure", "Arrival",
    "Duration", "Layover Time"
]

st.set_page_config(page_title="IndiGo Flight Extractor", layout="wide")

st.title("IndiGo Screenshot → Excel Extractor")
st.write("Upload one or more screenshots. The app will extract flight rows and let you download an Excel in your required format.")

uploaded = st.file_uploader("Upload screenshots (PNG, JPG). You can upload multiple.", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

# simple preprocessing helpers
def opencv_preprocess(pil_image: Image.Image):
    img = np.array(pil_image.convert("RGB"))[:, :, ::-1]  # RGB->BGR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = 2.0 if max(h, w) < 1500 else 1.0
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.medianBlur(gray, 3)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def ocr_text_from_image(pil_image: Image.Image, psm=6):
    arr = opencv_preprocess(pil_image)
    pil = Image.fromarray(arr)
    config = f'--oem 3 --psm {psm}'
    text = pytesseract.image_to_string(pil, config=config)
    return text

# parsing heuristics (keeps your required output format)
def detect_layout(text: str) -> str:
    if not text:
        return "table"
    if re.search(r'layover', text, re.IGNORECASE):
        return "block"
    if re.search(r'Departure|Arrival|Duration', text, re.IGNORECASE):
        return "table"
    return "table"

def parse_table_style(text: str) -> List[Dict]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    rows = []
    for line in lines:
        # only rows likely to be flight lines
        if not re.search(r'6E|Indigo|6e', line, re.I):
            continue
        parts = [p.strip() for p in re.split(r'\s{2,}|\||\t', line) if p.strip()]
        row = {c: "" for c in COLUMNS}
        if len(parts) >= 8:
            row["Carrier"], row["Flight No."], row["From"], row["To"], row["Departure"], row["Arrival"], row["Duration"], row["Layover Time"] = parts[:8]
        else:
            # best-effort mapping
            row["Carrier"] = parts[0] if parts else "Indigo"
            for p in parts[1:4]:
                if re.search(r'\b6E\b|\b6e\b|\b\d{1,4}\b', p):
                    row["Flight No."] = p
                    break
            times = [p for p in parts if re.search(r'\d{1,2}:\d{2}', p)]
            if times:
                row["Departure"] = times[0]
            if len(times) > 1:
                row["Arrival"] = times[1]
            if len(parts) > 3:
                row["From"] = parts[2] if len(parts) > 2 else ""
                row["To"] = parts[3] if len(parts) > 3 else ""
        rows.append(row)
    return rows

def parse_block_style(text: str) -> List[Dict]:
    # split blocks heuristically
    parts = re.split(r'\n-{2,}\n|\n\n+', text)
    rows = []
    for blk in parts:
        if not blk.strip():
            continue
        mfn = re.search(r'\b6E[\s\-]?\d{1,4}\b(?:\.\s*[A-Za-z0-9]+)?', blk, re.I)
        flight_no = mfn.group(0).strip() if mfn else ""
        times = re.findall(r'\b([01]?\d|2[0-3]):[0-5]\d\b', blk)
        dep = times[0] if len(times) >= 1 else ""
        arr = times[1] if len(times) >= 2 else ""
        mlay = re.search(r'(\d{1,2}h(?:\s*\d{1,2}m)?\s*layover[\w\s,]*)', blk, re.I)
        lay = mlay.group(0) if mlay else ""
        mroute = re.search(r'([A-Z]{3}[-–][A-Z]{3})', blk)
        city_from = city_to = ""
        if mroute:
            city_from, city_to = mroute.group(1).split('-')
        else:
            lines = [l.strip() for l in blk.splitlines() if l.strip()]
            time_lines = [i for i,l in enumerate(lines) if re.search(r'\d{1,2}:\d{2}', l)]
            if time_lines:
                idx = time_lines[0]
                if idx > 0:
                    city_from = lines[idx-1]
                if idx+1 < len(lines):
                    city_to = lines[idx+1]
        row = {
            "Carrier": "Indigo",
            "Flight No.": flight_no,
            "From": city_from.title() if city_from else "",
            "To": city_to.title() if city_to else "",
            "Departure": dep,
            "Arrival": arr,
            "Duration": "",
            "Layover Time": lay
        }
        rows.append(row)
    return rows

def extract_from_image(pil_img: Image.Image) -> List[Dict]:
    text = ocr_text_from_image(pil_img)
    layout = detect_layout(text)
    if layout == "block":
        rows = parse_block_style(text)
    else:
        rows = parse_table_style(text)
    for r in rows:
        for k in r:
            r[k] = r[k].strip() if isinstance(r[k], str) else r[k]
        if not r["Carrier"]:
            r["Carrier"] = "Indigo"
    return rows

# App main logic
if uploaded:
    all_rows = []
    for file in uploaded:
        try:
            img = Image.open(file)
        except Exception as e:
            st.error(f"Can't open {file.name}: {e}")
            continue
        st.subheader(f"Preview: {file.name}")
        st.image(img, use_column_width=True)
        with st.spinner("Extracting..."):
            rows = extract_from_image(img)
        if rows:
            df = pd.DataFrame(rows, columns=COLUMNS)
            st.write("Extracted rows (edit if needed):")
            edited = st.data_editor(df, num_rows="dynamic")
            all_rows.extend(edited.to_dict(orient="records"))
        else:
            st.warning("No flight rows detected in this image.")
    if all_rows:
        final_df = pd.DataFrame(all_rows, columns=COLUMNS)
        st.markdown("### Final combined table")
        st.dataframe(final_df, use_container_width=True)
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
            final_df.to_excel(writer, index=False, sheet_name="Flights")
        towrite.seek(0)
        st.download_button("Download Excel", towrite, file_name="extracted_indigo_flights.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Upload screenshots to begin. You can use the example images you showed earlier.")

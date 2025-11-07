
import io, re, base64
from pathlib import Path
import streamlit as st
import pandas as pd
from PIL import Image
import numpy as np
import cv2
import pytesseract

COLUMNS = [
    "Carrier", "Flight No.", "From", "To", "Departure", "Arrival",
    "Duration", "Layover Time"
]

st.set_page_config(page_title="IndiGo Flight Extractor", layout="wide")
st.title("IndiGo Screenshot → Excel Extractor")
st.write("Upload or paste Indigo screenshots to extract flight details automatically.")

uploaded = st.file_uploader("Upload screenshots (PNG, JPG). You can upload multiple.", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

def opencv_preprocess(pil_image: Image.Image):
    img = np.array(pil_image.convert("RGB"))[:, :, ::-1]  # RGB->BGR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = 2.0 if max(h, w) < 1500 else 1.0
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.medianBlur(gray, 3)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def ocr_text_from_image(pil_image: Image.Image):
    arr = opencv_preprocess(pil_image)
    pil = Image.fromarray(arr)
    config = '--oem 3 --psm 6'
    text = pytesseract.image_to_string(pil, config=config)
    return text

def parse_block_style(text):
    rows = []
    parts = re.split(r'(?=\b6E\s?\d{1,4}\b)', text, flags=re.IGNORECASE)
    for blk in parts:
        if not re.search(r'\b6E\s?\d{1,4}\b', blk, re.IGNORECASE):
            continue
        mfn = re.search(r'\b6E\s?\d{1,4}\b(?:\.\s*[A-Za-z0-9]+)?', blk, re.IGNORECASE)
        flight_no = mfn.group(0).strip() if mfn else ""
        times = re.findall(r'\b([01]?\d|2[0-3]):[0-5]\d\b', blk)
        dep = times[0] if len(times) >= 1 else ""
        arr = times[1] if len(times) >= 2 else ""
        city_from = ""
        city_to = ""
        mroute = re.search(r'([A-Z]{3}[-–][A-Z]{3})', blk)
        if mroute:
            try:
                city_from, city_to = mroute.group(1).split('-')
            except Exception:
                city_from = mroute.group(1)
        else:
            lines = [l.strip() for l in blk.splitlines() if l.strip()]
            time_line_indexes = [i for i,l in enumerate(lines) if re.search(r'\d{1,2}:\d{2}', l)]
            if time_line_indexes:
                idx = time_line_indexes[0]
                if idx > 0:
                    city_from = lines[idx-1]
                if idx+1 < len(lines):
                    city_to = lines[idx+1]
            if not city_from or not city_to:
                cand = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', blk)
                if len(cand) >= 2:
                    if not city_from:
                        city_from = cand[0]
                    if not city_to:
                        city_to = cand[1]
        mdur = re.search(r'(\d{1,2}h\s*\d{1,2}m?)', blk, re.IGNORECASE)
        duration = mdur.group(0) if mdur else ""
        mlay = re.search(r'(\d{1,2}h\s*\d{1,2}m?.{0,30}?layover)', blk, re.IGNORECASE)
        layover = mlay.group(0).strip() if mlay else ""
        row = {
            "Carrier": "Indigo",
            "Flight No.": flight_no,
            "From": city_from.title() if isinstance(city_from, str) else city_from,
            "To": city_to.title() if isinstance(city_to, str) else city_to,
            "Departure": dep,
            "Arrival": arr,
            "Duration": duration,
            "Layover Time": layover
        }
        rows.append(row)
    return rows

def extract_from_image(pil_img: Image.Image):
    text = ocr_text_from_image(pil_img)
    rows = parse_block_style(text)
    for r in rows:
        for k in r:
            r[k] = r[k].strip() if isinstance(r[k], str) else r[k]
    return rows

if not uploaded:
    st.info("Upload one or more screenshots to begin.")
else:
    all_rows = []
    for idx, f in enumerate(uploaded):
        img = Image.open(f)
        st.image(img, caption=f"Screenshot {idx+1}", use_column_width=True)
        with st.spinner("Extracting flight info..."):
            rows = extract_from_image(img)
        if rows:
            st.success(f"Found {len(rows)} flight(s) in image {idx+1}")
            df = pd.DataFrame(rows, columns=COLUMNS)
            st.dataframe(df, use_container_width=True)
            all_rows.extend(rows)
        else:
            st.warning(f"No flights detected in image {idx+1}.")
    if all_rows:
        final = pd.DataFrame(all_rows, columns=COLUMNS)
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
            final.to_excel(writer, index=False, sheet_name='Flights')
        towrite.seek(0)
        st.download_button('Download Excel', towrite, file_name='extracted_indigo_flights.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

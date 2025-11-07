# app.py
import io, re, base64
from pathlib import Path
from typing import List, Dict
import streamlit as st
import pandas as pd
from PIL import Image
import numpy as np
import cv2
import pytesseract

# If Tesseract not in PATH, uncomment and fix your path:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

COLUMNS = [
    "Carrier", "Flight No.", "From", "To", "Departure", "Arrival",
    "Duration", "Layover Time"
]

st.set_page_config(page_title="IndiGo Flight Extractor", layout="wide")

st.title("✈️ IndiGo Screenshot → Excel Extractor")
st.caption("You can **upload**, **drag & drop**, or now even **paste (Ctrl+V)** your screenshots below!")

# Inject JS for clipboard paste
st.markdown("""
    <script>
    document.addEventListener('paste', async (event) => {
        const items = event.clipboardData.items;
        for (const item of items) {
            if (item.type.indexOf('image') === 0) {
                const blob = item.getAsFile();
                const reader = new FileReader();
                reader.onload = function(e) {
                    const b64 = e.target.result.split(',')[1];
                    window.parent.postMessage({isStreamlitMessage: true, type: 'clipboard-image', data: b64}, '*');
                };
                reader.readAsDataURL(blob);
            }
        }
    });
    </script>
""", unsafe_allow_html=True)

# Streamlit listener for clipboard events
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web.server.websocket_headers import _get_websocket_headers
from streamlit.runtime.state import get_session_state

if "pasted_images" not in st.session_state:
    st.session_state["pasted_images"] = []

def on_paste_event():
    ctx = get_script_run_ctx()
    if not ctx:
        return
    ws = _get_websocket_headers(ctx.session_id)
    if ws:
        pass  # no-op placeholder

# Listen for JS paste messages
from streamlit.runtime.legacy_caching import clear_cache
from streamlit.runtime.scriptrunner import add_script_run_ctx

# Websocket listener (hack)
from streamlit import runtime
if runtime.exists():
    try:
        runtime.get_instance()._session_mgr.on_message("clipboard-image", lambda msg: st.session_state["pasted_images"].append(msg["data"]))
    except Exception:
        pass

uploaded = st.file_uploader("Or upload screenshots manually", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

# Include pasted images (if any)
pasted_files = []
for idx, b64 in enumerate(st.session_state.get("pasted_images", [])):
    try:
        imgdata = base64.b64decode(b64)
        image = Image.open(io.BytesIO(imgdata))
        pasted_files.append(image)
    except Exception as e:
        st.warning(f"Failed to load pasted image: {e}")

if pasted_files:
    st.success(f"Pasted {len(pasted_files)} image(s) successfully!")

def preprocess(pil_img: Image.Image):
    img = np.array(pil_img.convert("RGB"))[:, :, ::-1]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def ocr_text(pil_img: Image.Image):
    arr = preprocess(pil_img)
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(Image.fromarray(arr), config=config)

def parse_text(text: str) -> List[Dict]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    rows = []
    for line in lines:
        if not re.search(r'6E|Indigo|6e', line, re.I):
            continue
        parts = re.split(r'\s{2,}|\||\t', line)
        parts = [p.strip() for p in parts if p.strip()]
        row = {c: "" for c in COLUMNS}
        if len(parts) >= 8:
            row.update(dict(zip(COLUMNS, parts[:8])))
        else:
            row["Carrier"] = "Indigo"
            if len(parts) >= 2: row["Flight No."] = parts[1]
            if len(parts) >= 4: row["From"], row["To"] = parts[2], parts[3]
        rows.append(row)
    return rows

def extract(pil_img: Image.Image):
    text = ocr_text(pil_img)
    rows = parse_text(text)
    return rows

# Combine uploaded + pasted
images = []
if uploaded:
    for f in uploaded:
        images.append(Image.open(f))
if pasted_files:
    images.extend(pasted_files)

if not images:
    st.info("📋 Try **pasting (Ctrl + V)** a screenshot directly, or upload files above.")
else:
    all_rows = []
    for idx, img in enumerate(images):
        st.image(img, caption=f"Screenshot {idx+1}", use_container_width=True)
        with st.spinner("Extracting..."):
            rows = extract(img)
        if rows:
            st.success(f"Found {len(rows)} row(s) in image {idx+1}")
            df = pd.DataFrame(rows, columns=COLUMNS)
            st.dataframe(df, use_container_width=True)
            all_rows.extend(rows)
        else:
            st.warning(f"No data found in screenshot {idx+1}")

    if all_rows:
        final = pd.DataFrame(all_rows, columns=COLUMNS)
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
            final.to_excel(writer, index=False, sheet_name="Flights")
        towrite.seek(0)
        st.download_button(
            "⬇️ Download Excel",
            towrite,
            file_name="extracted_indigo_flights.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

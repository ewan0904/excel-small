import streamlit as st

st.set_page_config(
    page_title="My App",
    page_icon="📷",
    layout="wide"
)

from streamlit import column_config
from streamlit_modal import Modal
from streamlit_extras.stylable_container import stylable_container
from streamlit_cropper import st_cropper
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import re
from PIL import Image
from utils.scraping import *
from utils.auth import *
import base64
from io import BytesIO


require_login()

if st.sidebar.button("Logout"):
    logout()

# --- Session State Initialization ---
if "product_df" not in st.session_state:
    st.session_state["product_df"] = pd.DataFrame(columns=[
        'Position', '2. Position', 'Art_Nr', 'Titel', 'Beschreibung', 'Menge',
        'Preis', 'Gesamtpreis', 'Hersteller', 'Alternative'
    ])

if "images" not in st.session_state:
    st.session_state["images"] = {}

if "clear_url_input" not in st.session_state:
    st.session_state['clear_url_input'] = False

if st.session_state['clear_url_input']:
    st.session_state['url_input'] = ""
    st.session_state['clear_url_input'] = False

def get_image_copy_html(image_bytes, art_nr):
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    html = f"""
    <div style="text-align: left;">
        <img id="img_{art_nr}" src="data:image/png;base64,{b64}" width="150" style="display:none;" />
        <button onclick="copyImageToClipboard_{art_nr}()">📋 Bild in Zwischenablage kopieren</button>
    </div>
    <script>
    async function copyImageToClipboard_{art_nr}() {{
        const img = document.getElementById("img_{art_nr}");
        const response = await fetch(img.src);
        const blob = await response.blob();
        await navigator.clipboard.write([
            new ClipboardItem({{ [blob.type]: blob }})
        ]);
        // Removed the alert to avoid showing a confirmation message
    }}
    </script>
    """
    return html

# --- Utility: URL Extraction ---
def extract_urls(text):
    text = text.replace('\r', '\n').replace('\u2028', '\n').replace('\u2029', '\n').replace('\xa0', '').strip()
    split_text = re.split(r'(https?://)', text)
    urls = []
    for i in range(1, len(split_text), 2):
        full_url = split_text[i] + split_text[i+1].split()[0]
        urls.append(full_url.strip())
    return urls

# --- Produkt-URL Eingabe + Scraping ---
def url_input_section():
    with st.expander("**Produkte hinzufügen**", expanded=True):
        with st.form("url_form"):
            urls = st.text_area("Alle Produkt-Links hier einfügen.", height=150, key="url_input")
            submitted = st.form_submit_button("Produkte hinzufügen")

        if submitted:
            extracted_urls = extract_urls(urls)
            if extracted_urls:
                st.success(f"✅ {len(extracted_urls)} Produkt(e) gefunden!")
                start_pos = len(st.session_state.product_df) + 1

                with st.spinner("🔄 Produkte werden verarbeitet..."):
                    for idx, url in enumerate(extracted_urls, start=start_pos):
                        if "gastro-hero" in url:
                            find_gastro_hero_information(url, idx)
                        elif "ggmgastro" in url:
                            find_ggm_information(url, idx)
                st.session_state.clear_url_input = True
                st.rerun() 

# --- Produkt-Tabelle Bearbeiten ---
def product_table_section():
    with st.expander("**Produkte bearbeiten**", expanded=True):
        editable_columns = ["Position", "2. Position", "Art_Nr", "Titel", "Beschreibung", "Menge", "Preis", "Gesamtpreis", "Hersteller", "Alternative"]
        edited_df = st.data_editor(
            st.session_state.product_df,
            use_container_width=True,
            num_rows="dynamic",
            column_order=editable_columns,
            column_config={
                "Titel": column_config.TextColumn("Titel", width="medium"),
                "Beschreibung": column_config.TextColumn("Beschreibung", width="large"),
                "Menge": column_config.NumberColumn("Menge"),
                "Preis": column_config.NumberColumn("Preis"),
                "Gesamtpreis": column_config.NumberColumn("Gesamtpreis", disabled=True),
                "Position": column_config.NumberColumn("Position"),
                "2. Position": column_config.NumberColumn("2. Position")
            },
            key="editable_products"
        )

        col1, col2, _ = st.columns([3, 2, 7])
        with col1:
            if st.button("💾 Änderungen speichern"):
                # Check if there are any missing columns
                required_columns = ["Position", "Art_Nr", "Titel", "Preis"]
                missing_rows = edited_df[
                    edited_df[required_columns].isnull().any(axis=1) |
                    (edited_df[required_columns].astype(str).applymap(str.strip) == "").any(axis=1)
                ]

                if not missing_rows.empty:
                    st.error("❌ Einige Pflichtfelder (Art_Nr, Titel, Menge) sind leer. Bitte ausfüllen.")
                    st.stop()
                
                # Calculate Gesamtpreis conditionally
                edited_df["Gesamtpreis"] = np.where(
                edited_df["Menge"].isna() | (edited_df["Menge"] == 0),
                edited_df["Preis"],                   # Use Preis if Menge is missing or zero
                edited_df["Menge"] * edited_df["Preis"]  # Otherwise calculate normally
                )
                for i, row in edited_df.iterrows():
                    art_nr = row.get("Art_Nr")

                    if art_nr not in st.session_state.images:
                        st.session_state.images[art_nr] = Image.open("assets/logo.png")

                st.session_state.product_df = edited_df
                st.rerun()

        with col2:
            if st.button("🔀 Tabelle sortieren"):
                sorted_df = st.session_state.product_df.sort_values(
                    by=["Position", "2. Position"], na_position="last"
                ).reset_index(drop=True)
                st.session_state.product_df = sorted_df
                st.rerun()

# --- Produktbilder Anzeigen / Hochladen ---
def image_upload_section():
    with st.expander("**Produktbilder anzeigen / ändern**", expanded=True):
        st.write("")
        for i, row in st.session_state.product_df.iterrows():
            art_nr = row.get("Art_Nr")

            cols = st.columns([1, 4])
            with cols[0]:
                if art_nr in st.session_state.images:
                    st.image(st.session_state.images[art_nr], width=150)

            with cols[1]:
                if art_nr in st.session_state.images:
                    st.markdown(f"**{row['Titel']}**")
                    img = st.session_state.images[art_nr]

                    # Get raw image bytes
                    if hasattr(img, "read"):  # UploadedFile
                        image_bytes = img.read()
                    else:  # PIL.Image
                        buffer = BytesIO()
                        img.save(buffer, format="PNG")
                        image_bytes = buffer.getvalue()

                    # Inject the HTML + JS
                    components.html(get_image_copy_html(image_bytes, art_nr), height=60)


# --- Run All Sections ---
url_input_section()
product_table_section()
image_upload_section()
import requests
from bs4 import BeautifulSoup, NavigableString
import streamlit as st
import re
import uuid
import pandas as pd
from rembg import remove
from io import BytesIO
from PIL import Image
import pillow_avif


# ---
# GastroGGM - Product Scraping
# ---

def convert_html_to_text(soup_section):
    if soup_section is None:
        return ""
    readable_text = ''
    current_heading = ''
    for element in soup_section.find_all(['p', 'ul']):
        if element.name == 'p':
            strong = element.find('strong')
            if strong:
                current_heading = strong.get_text(strip=True)
                readable_text += f"\n{current_heading}:\n"
        elif element.name == 'ul':
            for li in element.find_all('li'):
                li_text = li.get_text(strip=True)
                readable_text += f"  • {li_text}\n"
    return readable_text.strip()

def find_ggm_information(url, position):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')

    # Article
    article_div = soup.find('div', {'class': 'text-sm font-light text-[#332e2e]'})
    article_number = article_div.text if article_div else ''
    artnr_match = re.search(r'Art\.-Nr\.\s*([\S\s]+)', article_number)
    article_number = artnr_match.group(1).strip() if artnr_match else None

    # Title
    title_div = soup.find('h1')
    title = title_div.text.strip() if title_div else ''

    # Description
    desc_div = soup.find('div', class_='ggmDescription')
    description_text = convert_html_to_text(desc_div)

    # Price
    price_span = soup.find('span', class_=lambda c: c and 'product-text-shadow' in c)
    price_text = price_span.text.strip() if price_span else '0'
    price_match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', price_text)
    price = price_match.group(1) if price_match else '0'
    price_float = float(price.replace('.', '').replace(',', '.'))

    # Image
    image_tag = soup.find('img', src=lambda x: x and 'ggm.bynder.com' in x)
    image_url = image_tag.get('src') if image_tag else ''

    new_row = {
        'Position': position,
        '2. Position': '',
        'Art_Nr': article_number,
        'Titel': title,
        'Beschreibung': description_text,
        'Menge': 1,
        'Preis': price_float,
        'Gesamtpreis': price_float,
        'Hersteller': 'GGM',
        'Alternative': False
    }

    image = auto_crop_image_with_rembg(image_url)
    if image:
        st.session_state.images[new_row['Art_Nr']] = image

    # Save row
    st.session_state["product_df"] = pd.concat(
        [st.session_state["product_df"], pd.DataFrame([new_row])],
        ignore_index=True
    )

# ---
# Gastro Hero - Product Scraping
# ---

def get_soup(url):

    api_response = requests.post(
        "https://api.zyte.com/v1/extract",
        auth=(st.secrets['ZYTE_API_KEY'], ""), ######## Change to st.secrets IMPORTANT
        json={
            "url": f"{url}",
            "browserHtml": True,
        },
    )
    return api_response.json()["browserHtml"]

def extract_product_description(soup):

    desc_container = soup.find("div", {"data-tracking": "product.tab-container.description"})
    if not desc_container:
        return "Description not found"

    tab_content = desc_container.select_one(".tab-content--have-gradient")
    if not tab_content:
        return ""

    output_lines = []
    skip_next_ul = False
    found_advantages = False

    for tag in tab_content.find_all(["p", "ul"]):
        text = tag.get_text(strip=True)
        text_lower = text.lower()

        # Check for "Produktvorteile im Überblick"
        if "produktvorteile im überblick" in text_lower:
            found_advantages = True
            skip_next_ul = True  # skip the list that follows
            continue

        # If we're skipping the <ul> that immediately follows the heading
        if skip_next_ul and tag.name == "ul":
            skip_next_ul = False  # skip this one and stop skipping
            continue

        # If it's before the "Produktvorteile" section, ignore
        if not found_advantages:
            continue

        # Otherwise, keep the content
        if tag.name == "p" and text:
            output_lines.append(text)
        elif tag.name == "ul":
            items = [f"• {li.get_text(strip=True)}" for li in tag.find_all("li")]
            output_lines.extend(items)

    return "\n".join(output_lines)

def find_gastro_hero_information(url, position):
    api_soup = get_soup(url)
    soup = BeautifulSoup(api_soup, 'html.parser')

    article_div = soup.find('span', {'class': 'inner-sku'})
    article_number = article_div.text.strip() if article_div else ''

    title_div = soup.find('h1')
    title = title_div.text.strip() if title_div else ''

    description_text = extract_product_description(soup)

    price_div = soup.find('div', class_='buy-box-price__display')

    price_raw = None

    # Look for strings directly under the main div (not inside inner <div>, <span>, etc.)
    for child in price_div.children:
        if isinstance(child, NavigableString):
            text = child.strip()
            if '€' in text:
                price_raw = text
                break  # Stop at the first matching outer price

    # Extract numeric value
    if price_raw:
        match = re.search(r'[\d.,]+', price_raw)
        if match:
            price_str = match.group(0)
            price_float = float(price_str.replace('.', '').replace(',', '.'))
        else:
            price_float = None
    else:
        price_float = None

    image_tag = soup.find('img', src=lambda x: x and 'api.gastro-hero.de' in x)
    image_url = image_tag.get('src') if image_tag else ''

    new_row = {
        'Position': position,
        '2. Position': '',
        'Art_Nr': article_number,
        'Titel': title,
        'Beschreibung': description_text,
        'Menge': 1,
        'Preis': price_float,
        'Gesamtpreis': price_float,
        'Hersteller': 'GH',
        'Alternative': False
    }

    # Auto-crop and save custom image
    image = auto_crop_image_with_rembg(image_url)
    if image:
        st.session_state.images[new_row['Art_Nr']] = image

    # Save row
    st.session_state["product_df"] = pd.concat(
        [st.session_state["product_df"], pd.DataFrame([new_row])],
        ignore_index=True
    )

# ---
# Auto-Crop images
# ---
def auto_crop_image_with_rembg(image_url):
    try:
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content)).convert("RGBA")

        result = remove(img)
        bbox = result.getbbox()
        if bbox:
            cropped = result.crop(bbox)
            buffer = BytesIO()
            cropped.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer
    except Exception as e:
        print(f"AI-Cropping failed: {e}")
    return None

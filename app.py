# app.py – Enhanced Streamlit Trade Data Fetcher (Imports + Exports)

import os, time, traceback, io
from typing import List, Tuple

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import openpyxl

# ─────────────────────────────────────────────────────────────────────────────
# WebDriver Setup

def _prep_driver():
    """Enhanced driver setup with better error handling and debugging"""
    options = Options()
    options.add_argument("--headless=new")  # modern headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Add user agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        # Try system chromedriver first
        if os.path.exists("/usr/bin/chromedriver"):
            options.binary_location = "/usr/bin/chromium"
            service = Service("/usr/bin/chromedriver")
        else:
            # Fallback to webdriver-manager
            service = Service(ChromeDriverManager().install())
        
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        st.error(f"Error setting up webdriver: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Enhanced Table parsing with debugging
def _parse_results_table(page_source: str, debug_mode: bool = False) -> Tuple[List[List[str]], List[str] | None]:
    """Extract <tbody> rows and optional <tfoot> row from the HTML source with enhanced debugging."""
    soup = BeautifulSoup(page_source, "html.parser")
    
    if debug_mode:
        st.write("Looking for table with id='example1'...")
    
    table = soup.find("table", id="example1")
    if not table:
        if debug_mode:
            st.write("Table with id='example1' not found. Looking for any table...")
            tables = soup.find_all("table")
            st.write(f"Found {len(tables)} tables total")
            if tables:
                st.write("Available table classes/ids:")
                for i, t in enumerate(tables):
                    st.write(f"Table {i}: id='{t.get('id')}', class='{t.get('class')}'")
        return [], None

    if debug_mode:
        st.write("✅ Found table with id='example1'")

    rows: list[list[str]] = []
    tbody = table.find('tbody')
    if not tbody:
        if debug_mode:
            st.write("❌ No tbody found in table")
        return [], None
    
    tr_elements = tbody.find_all("tr")
    if debug_mode:
        st.write(f"Found {len(tr_elements)} rows in tbody")
    
    for i, tr in enumerate(tr_elements):
        cells = [td.get_text(strip=True).replace("\xa0", " ") for td in tr.find_all("td")]
        if cells:
            # Skip the first cell (usually contains checkboxes or row numbers)
            processed_cells = cells[1:] if len(cells) > 1 else cells
            # Pad with N/A if needed
            while len(processed_cells) < 10:
                processed_cells.append("N/A")
            rows.append(processed_cells[:10])  # Take only first 10 columns
            
            if debug_mode and i < 3:  # Show first 3 rows for debugging
                st.write(f"Row {i}: {processed_cells[:5]}...")  # Show first 5 cells

    footer: list[str] | None = None
    tfoot = table.find('tfoot')
    if tfoot and tfoot.find('tr'):
        footer_cells = [td.get_text(strip=True).replace("\xa0", " ")
                       for td in tfoot.find('tr').find_all("td")]
        if footer_cells and len(footer_cells) > 1:
            footer = footer_cells[1:]  # Skip first cell
            while len(footer) < 10:
                footer.append("N/A")
            footer = footer[:10]  # Take only first 10 columns

    if debug_mode:
        st.write(f"✅ Parsed {len(rows)} data rows")
        if footer:
            st.write("✅ Found footer row")

    return rows, footer

# ─────────────────────────────────────────────────────────────────────────────
# Enhanced Scrapers with better error handling

def fetch_trade_data_import(hsn_code: str, year: str, debug_mode: bool = False) -> Tuple[List[List[str]], List[str] | None]:
    """Enhanced import data fetcher with debugging"""
    URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_import"
    driver = _prep_driver()
    
    if not driver:
        return [], None
    
    try:
        if debug_mode:
            st.write(f"🔍 Fetching import data for HSN: {hsn_code}, Year: {year}")
            st.write(f"📍 Navigating to: {URL}")
        
        driver.get(URL)
        wait = WebDriverWait(driver, 20)  # Increased timeout

        # Wait for page to load and click radio button
        if debug_mode:
            st.write("⏳ Waiting for radio button...")
        radio_btn = wait.until(EC.element_to_be_clickable((By.ID, "radio2")))
        radio_btn.click()
        time.sleep(1)  # Give time for page to update
        
        if debug_mode:
            st.write("✅ Clicked radio button")

        # Set month to March
        if debug_mode:
            st.write("⏳ Setting month to March...")
        month_dd = wait.until(EC.presence_of_element_located((By.NAME, "imddMonth")))
        month_select = Select(month_dd)
        month_select.select_by_value("3")
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", month_dd)
        time.sleep(1)
        
        if debug_mode:
            st.write("✅ Set month to March")

        # Set year
        if debug_mode:
            st.write(f"⏳ Setting year to {year}...")
        year_dd = wait.until(EC.presence_of_element_located((By.NAME, "imddYear")))
        year_select = Select(year_dd)
        year_select.select_by_value(str(year))
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", year_dd)
        time.sleep(1)
        
        if debug_mode:
            st.write(f"✅ Set year to {year}")

        # Enter HSN code
        if debug_mode:
            st.write(f"⏳ Entering HSN code: {hsn_code}")
        hs_input = wait.until(EC.presence_of_element_located((By.ID, "sp")))
        hs_input.clear()
        hs_input.send_keys(hsn_code)
        time.sleep(0.5)
        
        if debug_mode:
            st.write(f"✅ Entered HSN code: {hsn_code}")

        # Submit form
        if debug_mode:
            st.write("⏳ Submitting form...")
        submit_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Submit')]")))
        submit_btn.click()
        
        if debug_mode:
            st.write("✅ Clicked submit button")

        # Wait for results table
        if debug_mode:
            st.write("⏳ Waiting for results table...")
        
        # Try multiple strategies to wait for the table
        try:
            wait.until(EC.presence_of_element_located((By.ID, "example1")))
        except:
            # If that fails, wait a bit more and try again
            time.sleep(3)
            if not driver.find_elements(By.ID, "example1"):
                if debug_mode:
                    st.write("❌ Table not found, checking for error messages...")
                    page_text = driver.page_source
                    if "No data found" in page_text or "No records found" in page_text:
                        st.write("ℹ️ No data found for this HSN code")
                return [], None
        
        if debug_mode:
            st.write("✅ Found results table")
        
        # Parse the results
        return _parse_results_table(driver.page_source, debug_mode)

    except Exception as e:
        if debug_mode:
            st.error(f"❌ Import scraper error: {str(e)}")
            st.code(traceback.format_exc())
        print(f"[IMPORT SCRAPER ERROR] {e}")
        traceback.print_exc()
        return [], None
    finally:
        driver.quit()

def fetch_trade_data_export(hsn_code: str, year: str, debug_mode: bool = False) -> Tuple[List[List[str]], List[str] | None]:
    """Enhanced export data fetcher with debugging"""
    URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_export"
    driver = _prep_driver()
    
    if not driver:
        return [], None
    
    try:
        if debug_mode:
            st.write(f"🔍 Fetching export data for HSN: {hsn_code}, Year: {year}")
            st.write(f"📍 Navigating to: {URL}")
        
        driver.get(URL)
        wait = WebDriverWait(driver, 20)  # Increased timeout

        # Wait for page to load and click radio button
        if debug_mode:
            st.write("⏳ Waiting for radio button...")
        radio_btn = wait.until(EC.element_to_be_clickable((By.ID, "radio2")))
        radio_btn.click()
        time.sleep(1)
        
        if debug_mode:
            st.write("✅ Clicked radio button")

        # Set month to March (note: different name for export page)
        if debug_mode:
            st.write("⏳ Setting month to March...")
        month_dd = wait.until(EC.presence_of_element_located((By.NAME, "ddMonth")))
        month_select = Select(month_dd)
        month_select.select_by_value("3")
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", month_dd)
        time.sleep(1)
        
        if debug_mode:
            st.write("✅ Set month to March")

        # Set year
        if debug_mode:
            st.write(f"⏳ Setting year to {year}...")
        year_dd = wait.until(EC.presence_of_element_located((By.NAME, "ddYear")))
        year_select = Select(year_dd)
        year_select.select_by_value(str(year))
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", year_dd)
        time.sleep(1)
        
        if debug_mode:
            st.write(f"✅ Set year to {year}")

        # Enter HSN code
        if debug_mode:
            st.write(f"⏳ Entering HSN code: {hsn_code}")
        hs_input = wait.until(EC.presence_of_element_located((By.ID, "sp")))
        hs_input.clear()
        hs_input.send_keys(hsn_code)
        time.sleep(0.5)
        
        if debug_mode:
            st.write(f"✅ Entered HSN code: {hsn_code}")

        # Submit form
        if debug_mode:
            st.write("⏳ Submitting form...")
        submit_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Submit')]")))
        submit_btn.click()
        
        if debug_mode:
            st.write("✅ Clicked submit button")

        # Wait for results table
        if debug_mode:
            st.write("⏳ Waiting for results table...")
        
        try:
            wait.until(EC.presence_of_element_located((By.ID, "example1")))
        except:
            time.sleep(3)
            if not driver.find_elements(By.ID, "example1"):
                if debug_mode:
                    st.write("❌ Table not found, checking for error messages...")
                    page_text = driver.page_source
                    if "No data found" in page_text or "No records found" in page_text:
                        st.write("ℹ️ No data found for this HSN code")
                return [], None
        
        if debug_mode:
            st.write("✅ Found results table")
        
        return _parse_results_table(driver.page_source, debug_mode)

    except Exception as e:
        if debug_mode:
            st.error(f"❌ Export scraper error: {str(e)}")
            st.code(traceback.format_exc())
        print(f"[EXPORT SCRAPER ERROR] {e}")
        traceback.print_exc()
        return [], None
    finally:
        driver.quit()

# ─────────────────────────────────────────────────────────────────────────────
# Streamlit App
st.set_page_config(page_title="Trade Data Fetcher", layout="wide")

st.title("📊 Trade Data Fetcher – Imports & Exports")
st.markdown("Fetch live trade statistics (HSN-wise) from [TradeStat Portal]"
            "(https://tradestat.commerce.gov.in)")

# Add debug mode toggle
debug_mode = st.checkbox("🐛 Enable Debug Mode", help="Shows detailed logs of the scraping process")

hsn_input = st.text_input("Enter HSN code(s) (comma or space separated):", 
                         value="", 
                         help="Example: 7008, 44111200, 44111300")

year = st.selectbox("Select Year", [str(y) for y in range(2015, 2026)], index=10)
modes = st.multiselect("Select Mode(s)", ["import", "export"], default=["import", "export"])

# Add a test button for single HSN
col1, col2 = st.columns(2)
with col1:
    run_btn = st.button("🚀 Fetch Data", type="primary")
with col2:
    test_btn = st.button("🧪 Test Single HSN", help="Test with first HSN code only")

if run_btn or test_btn:
    if not hsn_input.strip():
        st.warning("⚠️ Please enter at least one HSN code.")
    elif not modes:
        st.warning("⚠️ Please select Import and/or Export.")
    else:
        codes = [c.strip() for c in hsn_input.replace(",", " ").split() if c.strip()]
        
        # If test mode, only use first code
        if test_btn:
            codes = codes[:1]
            st.info(f"🧪 Testing with HSN code: {codes[0]}")
        
        master_imp, master_exp, totals_imp, totals_exp = [], [], [], []
        serial_imp = serial_exp = 1

        # Show progress
        total_tasks = len(codes) * len(modes)
        progress_bar = st.progress(0)
        status_text = st.empty()
        task_done = 0

        for code in codes:
            if debug_mode:
                st.write(f"\n--- Processing HSN Code: {code} ---")
            
            if "import" in modes:
                status_text.text(f"🔍 Fetching import data for {code}...")
                rows_i, footer_i = fetch_trade_data_import(code, year, debug_mode)
                
                if rows_i:
                    for r in rows_i:
                        master_imp.append([serial_imp] + r[:10])
                        serial_imp += 1
                    if footer_i:
                        nums = [float(x.replace(",", "").replace("−", "-"))
                                if any(ch.isdigit() for ch in x) else 0
                                for x in footer_i]
                        totals_imp.append(nums)
                    
                    if debug_mode:
                        st.success(f"✅ Successfully fetched {len(rows_i)} import records for {code}")
                else:
                    master_imp.append([serial_imp, code] + ["N/A"] * 9)
                    serial_imp += 1
                    if debug_mode:
                        st.warning(f"⚠️ No import data found for {code}")

                task_done += 1
                progress_bar.progress(task_done / total_tasks)

            if "export" in modes:
                status_text.text(f"🔍 Fetching export data for {code}...")
                rows_e, footer_e = fetch_trade_data_export(code, year, debug_mode)
                
                if rows_e:
                    for r in rows_e:
                        master_exp.append([serial_exp] + r[:10])
                        serial_exp += 1
                    if footer_e:
                        nums = [float(x.replace(",", "").replace("−", "-"))
                                if any(ch.isdigit() for ch in x) else 0
                                for x in footer_e]
                        totals_exp.append(nums)
                    
                    if debug_mode:
                        st.success(f"✅ Successfully fetched {len(rows_e)} export records for {code}")
                else:
                    master_exp.append([serial_exp, code] + ["N/A"] * 9)
                    serial_exp += 1
                    if debug_mode:
                        st.warning(f"⚠️ No export data found for {code}")

                task_done += 1
                progress_bar.progress(task_done / total_tasks)

        progress_bar.empty()
        status_text.text("✅ Done fetching all data!")

        headers = [
            "S.No.", "HSCode", "Commodity",
            f"Mar-{int(year)-1} (R)", f"Mar-{year} (F)", "%Growth (Mar)",
            f"Apr-Mar{int(year)-1} (R)", f"Apr-Mar{year} (F)", "%Growth (FY)",
            "Share %", "Rank"
        ]

        # Save and display results
        if master_imp:
            st.session_state["df_imp"] = pd.DataFrame(master_imp, columns=headers)
            df_imp = st.session_state["df_imp"]
            st.subheader("📥 Imports Data")
            st.dataframe(df_imp, use_container_width=True)

        if master_exp:
            st.session_state["df_exp"] = pd.DataFrame(master_exp, columns=headers)
            df_exp = st.session_state["df_exp"]
            st.subheader("📤 Exports Data")
            st.dataframe(df_exp, use_container_width=True)

# Display existing data if available
elif "df_imp" in st.session_state or "df_exp" in st.session_state:
    st.info("ℹ️ Showing previously fetched data. Click 'Fetch Data' to refresh.")
    
    if "df_imp" in st.session_state:
        st.subheader("📥 Imports Data")
        st.dataframe(st.session_state["df_imp"], use_container_width=True)
    
    if "df_exp" in st.session_state:
        st.subheader("📤 Exports Data")
        st.dataframe(st.session_state["df_exp"], use_container_width=True)

st.markdown("""
### 💡 Tips:
- **Multiple HSN codes**: Separate with comma or space (e.g., `7008, 44111200, 44111300`)
- **Debug mode**: Enable to see detailed logs of the scraping process
- **Test mode**: Use "Test Single HSN" to test with just the first HSN code
- **Valid HSN codes**: Ensure your HSN codes are correct and exist in the database
""")

st.markdown("---")
st.markdown("*Data sourced from [TradeStat Commerce Portal](https://tradestat.commerce.gov.in)*")

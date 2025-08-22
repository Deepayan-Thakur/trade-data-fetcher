# app.py – Streamlit Trade Data Fetcher (Imports + Exports)

import os, time, traceback
from typing import List, Tuple

import numpy as np
import io
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

# ─────────────────────────────────────────────────────────────────────────────
# WebDriver Setup
def _prep_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--headless=new")   # headless for server/cloud deploy
    opts.add_argument("--window-size=1500,768")

    # NOTE: On Streamlit Cloud, ChromeDriver path must be handled dynamically
    chromedriver_path = "E:\\softwares used\\chromedriver-win64\\chromedriver.exe"
    return webdriver.Chrome(service=Service(chromedriver_path), options=opts)


# ─────────────────────────────────────────────────────────────────────────────
# Table parsing
def _parse_results_table(page_source: str) -> Tuple[List[List[str]], List[str] | None]:
    """Extract <tbody> rows and optional <tfoot> row from the HTML source."""
    soup = BeautifulSoup(page_source, "html.parser")
    table = soup.find("table", id="example1")
    if not table:
        return [], None

    rows: list[list[str]] = []
    for tr in table.tbody.find_all("tr"):
        cells = [td.get_text(strip=True).replace("\xa0", " ") for td in tr.find_all("td")]
        if cells:
            rows.append(cells[1:] + ["N/A"] * (10 - len(cells) + 1))

    footer: list[str] | None = None
    if table.tfoot and table.tfoot.tr:
        footer = [td.get_text(strip=True).replace("\xa0", " ")
                  for td in table.tfoot.tr.find_all("td")][1:]
        footer += ["N/A"] * (10 - len(footer))

    return rows, footer


# ─────────────────────────────────────────────────────────────────────────────
# Scrapers
def fetch_trade_data_import(hsn_code: str, year: str) -> Tuple[List[List[str]], List[str] | None]:
    URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_import"
    driver = _prep_driver()
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 15)

        wait.until(EC.element_to_be_clickable((By.ID, "radio2"))).click()
        # Month → March
        month_dd = wait.until(EC.presence_of_element_located((By.NAME, "imddMonth")))
        Select(month_dd).select_by_value("3")
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", month_dd)
        time.sleep(0.5)

        # Year
        year_dd = wait.until(EC.presence_of_element_located((By.NAME, "imddYear")))
        Select(year_dd).select_by_value(str(year))
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", year_dd)
        time.sleep(0.5)

        # HSN
        hs_in = wait.until(EC.presence_of_element_located((By.ID, "sp")))
        hs_in.clear(); hs_in.send_keys(hsn_code)

        wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Submit')]"))).click()

        wait.until(EC.presence_of_element_located((By.ID, "example1")))
        return _parse_results_table(driver.page_source)

    except Exception as e:
        print("[IMPORT SCRAPER ERROR]", e); traceback.print_exc()
        return [], None
    finally:
        driver.quit()


def fetch_trade_data_export(hsn_code: str, year: str) -> Tuple[List[List[str]], List[str] | None]:
    URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_export"
    driver = _prep_driver()
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 15)

        wait.until(EC.element_to_be_clickable((By.ID, "radio2"))).click()
        month_dd = wait.until(EC.presence_of_element_located((By.NAME, "ddMonth")))
        Select(month_dd).select_by_value("3")
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", month_dd)
        time.sleep(0.5)

        year_dd = wait.until(EC.presence_of_element_located((By.NAME, "ddYear")))
        Select(year_dd).select_by_value(str(year))
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", year_dd)
        time.sleep(0.5)

        hs_in = wait.until(EC.presence_of_element_located((By.ID, "sp")))
        hs_in.clear(); hs_in.send_keys(hsn_code)

        wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Submit')]"))).click()

        wait.until(EC.presence_of_element_located((By.ID, "example1")))
        return _parse_results_table(driver.page_source)

    except Exception as e:
        print("[EXPORT SCRAPER ERROR]", e); traceback.print_exc()
        return [], None
    finally:
        driver.quit()


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit App
st.set_page_config(page_title="Trade Data Fetcher", layout="wide")

st.title("📊 Trade Data Fetcher – Imports & Exports")
st.markdown("Fetch live trade statistics (HSN-wise) from [TradeStat Portal]"
            "(https://tradestat.commerce.gov.in)")

hsn_input = st.text_input("Enter HSN code(s) (comma or space separated):", "")
year = st.selectbox("Select Year", [str(y) for y in range(2015, 2026)], index=10)
modes = st.multiselect("Select Mode(s)", ["import", "export"], default=["import", "export"])
run_btn = st.button("Fetch Data")

if run_btn:
    if not hsn_input.strip():
        st.warning("Please enter at least one HSN code.")
    elif not modes:
        st.warning("Please select Import and/or Export.")
    else:
        codes = [c.strip() for c in hsn_input.replace(",", " ").split() if c.strip()]
        master_imp, master_exp, totals_imp, totals_exp = [], [], [], []
        serial_imp = serial_exp = 1

        with st.spinner("Fetching data, please wait..."):
            total_tasks = len(codes) * len(modes)  # total number of fetch operations
            progress_bar = st.progress(0)
            status_text = st.empty()   # to show what’s happening
            task_done = 0

            for code in codes:
                if "import" in modes:
                    rows_i, footer_i = fetch_trade_data_import(code, year)
                    if rows_i:
                        for r in rows_i:
                            master_imp.append([serial_imp] + r[:10])
                            serial_imp += 1
                        if footer_i:
                            nums = [float(x.replace(",", "").replace("−", "-"))
                                    if any(ch.isdigit() for ch in x) else 0
                                    for x in footer_i]
                            totals_imp.append(nums)
                    else:
                        master_imp.append([serial_imp, code] + ["N/A"] * 9)
                        serial_imp += 1

                    task_done += 1
                    progress_bar.progress(task_done / total_tasks)
                    status_text.text(f"Fetching {task_done}/{total_tasks} completed...")


                if "export" in modes:
                    rows_e, footer_e = fetch_trade_data_export(code, year)
                    if rows_e:
                        for r in rows_e:
                            master_exp.append([serial_exp] + r[:10])
                            serial_exp += 1
                        if footer_e:
                            nums = [float(x.replace(",", "").replace("−", "-"))
                                    if any(ch.isdigit() for ch in x) else 0
                                    for x in footer_e]
                            totals_exp.append(nums)
                    else:
                        master_exp.append([serial_exp, code] + ["N/A"] * 9)
                        serial_exp += 1

                    task_done += 1
                    progress_bar.progress(task_done / total_tasks)
                    status_text.text(f"Fetching {task_done}/{total_tasks} completed...")

            progress_bar.empty()
            status_text.text("✅ Done fetching all data!")


        headers = [
            "S.No.", "HSCode", "Commodity",
            f"Mar-{int(year)-1} (R)", f"Mar-{year} (F)", "%Growth (Mar)",
            f"Apr-Mar{int(year)-1} (R)", f"Apr-Mar{year} (F)", "%Growth (FY)",
            "Share %", "Rank"
        ]

        # Save results to session_state so they persist across reruns
        if run_btn:
            if master_imp:
                st.session_state["df_imp"] = pd.DataFrame(master_imp, columns=headers)
            if master_exp:
                st.session_state["df_exp"] = pd.DataFrame(master_exp, columns=headers)

        # Show Imports if already in session_state
        if "df_imp" in st.session_state:
            df_imp = st.session_state["df_imp"]
            st.subheader("📥 Imports Data")
            st.dataframe(df_imp, use_container_width=True)

            buffer_imp = io.BytesIO()
            with pd.ExcelWriter(buffer_imp, engine="openpyxl") as writer:
                df_imp.to_excel(writer, index=False, sheet_name="Imports")
            buffer_imp.seek(0)

            # st.download_button(
            #     label="Download Imports Excel",
            #     data=buffer_imp,
            #     file_name=f"imports_{year}.xlsx",
            #     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            # )

        # Show Exports if already in session_state
        if "df_exp" in st.session_state:
            df_exp = st.session_state["df_exp"]
            st.subheader("📤 Exports Data")
            st.dataframe(df_exp, use_container_width=True)

            buffer_exp = io.BytesIO()
            with pd.ExcelWriter(buffer_exp, engine="openpyxl") as writer:
                df_exp.to_excel(writer, index=False, sheet_name="Exports")
            buffer_exp.seek(0)

            # st.download_button(
            #     label="Download Exports Excel",
            #     data=buffer_exp,
            #     file_name=f"exports_{year}.xlsx",
            #     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            # )


st.info("Tip: You can enter multiple HSN codes separated by comma or space.")

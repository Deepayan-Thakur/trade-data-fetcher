# app.py  – Trade Data Fetcher (Imports + Exports)
import os, time, traceback
from typing import List, Tuple

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


app = Flask(__name__)


def _prep_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1500,768")

    chromedriver_path = "E:\\softwares used\\chromedriver-win64\\chromedriver.exe"

    return webdriver.Chrome(service=Service(chromedriver_path), options=opts)


def _parse_results_table(page_source: str) -> Tuple[List[List[str]], List[str] | None]:
    """Extract <tbody> rows and optional <tfoot> row from the HTML source."""
    soup  = BeautifulSoup(page_source, "html.parser")
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


def fetch_trade_data_import(hsn_code: str, year: str
                            ) -> Tuple[List[List[str]], List[str] | None]:
    """Scrape the *imports* commodity‑wise page (month fixed at March)."""
    URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_import"
    driver = _prep_driver()
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 15)

        wait.until(EC.element_to_be_clickable((By.ID, "radio2"))).click()     
        # Month → March ---------------------------------------------------------
        month_dd = wait.until(EC.presence_of_element_located((By.NAME, "imddMonth")))
        Select(month_dd).select_by_value("3")
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", month_dd)
        time.sleep(0.5)
        # Year ------------------------------------------------------------------
        year_dd = wait.until(EC.presence_of_element_located((By.NAME, "imddYear")))
        Select(year_dd).select_by_value(str(year))
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", year_dd)
        time.sleep(0.5)
        # HSN -------------------------------------------------------------------
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


def fetch_trade_data_export(hsn_code: str, year: str
                            ) -> Tuple[List[List[str]], List[str] | None]:
    """Scrape the *exports* commodity‑wise page (month fixed at March)."""
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

@app.route("/", methods=["GET", "POST"])
def index():
    hsn_input = ""
    year      = "2025"

    # containers for each flow
    import_rows: list[tuple[str, list[list[str]]]] = []
    export_rows: list[tuple[str, list[list[str]]]] = []
    master_imp:  list[list[str]] = []
    master_exp:  list[list[str]] = []
    totals_imp:  list[list[float]] = []
    totals_exp:  list[list[float]] = []

    # serial counters per table
    serial_imp = serial_exp = 1

    if request.method == "POST":
        hsn_input = request.form["hsn_code"].strip()
        year      = request.form["year"]
        modes     = request.form.getlist("mode")   

        if not modes:
            flash("Please tick Import and/or Export!", "warning")
            return redirect(url_for("index"))

        codes = [c.strip() for c in hsn_input.replace(",", " ").split() if c.strip()]

        for code in codes:
            # ─── IMPORTS ──────────────────────────────────────────────────
            if "import" in modes:
                rows_i, footer_i = fetch_trade_data_import(code, year)
                if rows_i:
                    for r in rows_i:
                        master_imp.append([serial_imp] + r[:10])
                        serial_imp += 1
                    import_rows.append((code, rows_i))
                    if footer_i:
                        nums = [float(x.replace(",", "").replace("−", "-"))
                                if any(ch.isdigit() for ch in x) else 0
                                for x in footer_i]
                        totals_imp.append(nums)
                else:
                    master_imp.append([serial_imp, code] + ["N/A"] * 9)
                    serial_imp += 1

            # ─── EXPORTS ────────────────────────────────────────────────────
            if "export" in modes:
                rows_e, footer_e = fetch_trade_data_export(code, year)
                if rows_e:
                    for r in rows_e:
                        master_exp.append([serial_exp] + r[:10])
                        serial_exp += 1
                    export_rows.append((code, rows_e))
                    if footer_e:
                        nums = [float(x.replace(",", "").replace("−", "-"))
                                if any(ch.isdigit() for ch in x) else 0
                                for x in footer_e]
                        totals_exp.append(nums)
                else:
                    master_exp.append([serial_exp, code] + ["N/A"] * 9)
                    serial_exp += 1

        # ─── combined totals for strip(s) ──────────────────────────────────
        def calc_totals(arr: list[list[float]]):
            if not arr: return None
            sums = np.sum(np.asarray(arr), axis=0)
            mar_r, mar_f = sums[2], sums[3]
            apr_r, apr_f = sums[5], sums[6]
            growth_mar = ((mar_f - mar_r) / mar_r * 100) if mar_r else 0
            growth_fy  = ((apr_f - apr_r) / apr_r * 100) if apr_r else 0
            return [
                "ALL",
                f"{mar_r:,.2f}", f"{mar_f:,.2f}", f"{growth_mar:.2f}",
                f"{apr_r:,.2f}", f"{apr_f:,.2f}", f"{growth_fy:.2f}",
            ]

        total_imp = calc_totals(totals_imp)
        total_exp = calc_totals(totals_exp)

        # ─── Excel files (one per flow) ───────────────────────────────────
        headers = [
            "S.No.", "HSCode", "Commodity",
            f"Mar-{int(year)-1} (R)", f"Mar-{year} (F)", "%Growth (Mar)",
            f"Apr-Mar{int(year)-1} (R)", f"Apr-Mar{year} (F)", "%Growth (FY)",
            "Share %", "Rank"
        ]

        import_fname = export_fname = None

        if master_imp:
            import_fname = f"imports_{year}.xlsx"
            imp_path = os.path.join(app.root_path, import_fname)
            pd.DataFrame(master_imp, columns=headers).to_excel(imp_path, index=False)

        if master_exp:
            export_fname = f"exports_{year}.xlsx"
            exp_path = os.path.join(app.root_path, export_fname)
            pd.DataFrame(master_exp, columns=headers).to_excel(exp_path, index=False)

        return render_template(
            "index.html",
            hsn_code=hsn_input,
            year=year,
            import_data=import_rows if master_imp else None,
            export_data=export_rows if master_exp else None,
            total_imp=total_imp,
            total_exp=total_exp,
            import_filename=import_fname,
            export_filename=export_fname,
        )


    # ─── GET  – first load ────────────────────────────────────────────────
    return render_template(
        "index.html",
        hsn_code=hsn_input,
        year=year,
        import_data=None,
        export_data=None,
        total_imp=None,
        total_exp=None,
        excel_filename=None,
    )


@app.route("/download/<filename>")
def download(filename: str):
    fpath = os.path.join(app.root_path, filename)
    return send_file(fpath, as_attachment=True) if os.path.exists(fpath) \
           else ("file not found", 404)


# ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)

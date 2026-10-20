"""PGDH Invoice Extractor - Streamlit UI.

UI saja: semua logika parsing/format ada di pgdh_invoice_extractor.py.
Jalankan lokal:  streamlit run app.py
"""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import pgdh_invoice_extractor as pgdh

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
LAYOUTS = {
    "2 sheet terpisah (Sheet 1 & Sheet 2)": pgdh.LAYOUT_SEPARATE,
    "1 sheet, dua tabel berdampingan": pgdh.LAYOUT_SIDE_BY_SIDE,
}

st.set_page_config(page_title="PGDH Invoice Extractor", page_icon="📄", layout="wide")


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def sidebar_options() -> dict:
    with st.sidebar:
        st.header("Pengaturan output")
        layout_label = st.radio("Format Excel", list(LAYOUTS))
        with_inv = st.checkbox(
            "Tambah kolom Invoice_Number di Sheet 1",
            value=False,
            help="Format contoh tidak punya kolom ini. Aktifkan bila memproses banyak invoice "
                 "dan perlu tahu item berasal dari invoice mana.",
        )
        extra = st.checkbox(
            "Sertakan sheet tambahan",
            value=False,
            help="Header, Size_Breakdown, HTS, Totals, Validation, Issues, Adjustments_Detail.",
        )
        st.divider()
        st.caption("Invoice dengan nomor sama hanya dihitung sekali. File rusak dilewati dan dicatat di tab Masalah. "
                   "Bila invoice lebih dari satu, sheet Summary (jumlah adjustment per invoice) ditambahkan otomatis.")
    return {"layout": LAYOUTS[layout_label], "with_invoice_no": with_inv, "extra_sheets": extra}


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
def run_pipeline(uploads: list) -> None:
    payload = [(f.name, f.getvalue()) for f in uploads]
    bar = st.progress(0.0, text="Menyiapkan file...")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            pdfs = pgdh.save_uploads(payload, Path(tmp))
            if not pdfs:
                bar.empty()
                st.error("Tidak ada file PDF yang ditemukan di upload.")
                return
            invoices, issues = pgdh.process_files(
                pdfs,
                workers=1,  # satu proses: stabil di Streamlit Cloud
                progress=False,
                on_progress=lambda k, n, name: bar.progress(k / n, text=f"Memproses {k}/{n}: {name}"),
            )
    except Exception as exc:  # noqa: BLE001
        bar.empty()
        st.error(f"Gagal memproses upload: {exc}")
        return
    bar.empty()
    st.session_state["result"] = {"invoices": invoices, "issues": issues}


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
def show_results(opts: dict) -> None:
    res = st.session_state.get("result")
    if res is None:
        return
    invoices, issues = res["invoices"], res["issues"]
    if not invoices:
        st.error("Tidak ada invoice yang berhasil dibaca.")
        if issues:
            st.dataframe(pd.DataFrame(issues), hide_index=True)
        return

    sheet1, sheet2 = pgdh.build_report_frames(invoices, opts["with_invoice_no"])
    checks = pd.DataFrame([c for inv in invoices for c in inv.checks])
    bad = checks[checks["Status"] != "OK"]
    n_dup = sum(i["Type"] == "DUPLICATE" for i in issues)
    n_err = sum(i["Type"] == "ERROR" for i in issues)

    c = st.columns(5)
    c[0].metric("Invoice unik", len(invoices))
    c[1].metric("Baris PO (Sheet 1)", len(sheet1))
    c[2].metric("Baris adjustment (Sheet 2)", len(sheet2))
    c[3].metric("Validasi tidak cocok", len(bad))
    c[4].metric("Duplikat / error", f"{n_dup} / {n_err}")

    if len(bad):
        st.warning(f"{len(bad)} pengecekan tidak cocok. Buka tab Validasi sebelum memakai angkanya.")
    else:
        st.success(f"Semua {len(checks)} pengecekan validasi cocok.")

    data = pgdh.report_excel_bytes(invoices, issues, **opts)
    st.download_button(
        "⬇️ Download Excel",
        data=data,
        file_name=f"PGDH_Report_{datetime.now():%Y%m%d_%H%M}.xlsx",
        mime=XLSX_MIME,
        type="primary",
    )

    multi = len(invoices) > 1
    labels = ["Sheet 1 - Item", "Sheet 2 - Adjustment"] + (["Summary"] if multi else []) + ["Validasi", f"Masalah ({len(issues)})"]
    tabs = st.tabs(labels)
    t1, t2, t3, t4 = tabs[0], tabs[1], tabs[-2], tabs[-1]
    with t1:
        st.dataframe(sheet1, hide_index=True)
    with t2:
        st.dataframe(sheet2, hide_index=True)
    if multi:
        with tabs[2]:
            st.caption("Jumlah adjustment per invoice. Sheet ini otomatis ada di Excel karena invoice lebih dari satu.")
            st.dataframe(pgdh.adjustment_summary_frame(invoices), hide_index=True)
    with t3:
        if len(bad):
            st.dataframe(bad, hide_index=True)
        else:
            st.info("Tidak ada mismatch.")
        with st.expander("Semua pengecekan"):
            st.dataframe(checks, hide_index=True)
    with t4:
        if issues:
            st.dataframe(pd.DataFrame(issues), hide_index=True)
        else:
            st.info("Tidak ada masalah.")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    st.title("📄 PGDH Invoice Extractor")
    st.caption("Upload invoice PGDH (PDF atau ZIP berisi banyak PDF), hasilnya Excel siap pakai.")
    opts = sidebar_options()

    uploads = st.file_uploader(
        "Upload invoice", type=["pdf", "zip"], accept_multiple_files=True,
        help="Boleh banyak file sekaligus, atau satu ZIP berisi semua PDF.",
    )
    if st.button("Proses", type="primary", disabled=not uploads):
        run_pipeline(uploads)
    show_results(opts)


main()

# PGDH Invoice Extractor (Streamlit)

Upload invoice PGDH (PDF / ZIP) -> Excel dengan Sheet 1 (item per PO line) dan Sheet 2 (adjustment).
Bila invoice lebih dari satu, ditambah sheet `Summary` (jumlah adjustment per invoice: SHAS, MOS quantity flat/PROMO, Total).
Pengelompokan Summary diatur di `ADJUSTMENT_SUMMARY_GROUPS` (pgdh_invoice_extractor.py).

## Struktur
- `app.py` - tampilan Streamlit
- `pgdh_invoice_extractor.py` - parser, validasi, format Excel (bisa dipakai tanpa Streamlit: `python pgdh_invoice_extractor.py --input folder`)
- `requirements.txt`, `.streamlit/config.toml`

## Jalankan lokal
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy ke Streamlit Community Cloud
1. Upload isi folder ini ke repo GitHub (`app.py` di root repo).
2. https://share.streamlit.io -> New app -> pilih repo, branch, Main file path: `app.py`.
3. Deploy. Tidak perlu secret atau pengaturan tambahan.

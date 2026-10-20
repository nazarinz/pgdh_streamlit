"""
Patch untuk pgdh_invoice_extractor.py. Ganti / tambahkan bagian berikut.
(re, Any, NUM, TOTAL_LABELS sudah ada di skrip asli)
"""

# --------------------------------------------------------------------------- #
# 1) to_num: dukung angka negatif gaya akuntansi "(1,330.99)"
# --------------------------------------------------------------------------- #
def to_num(value):
    if value is None:
        return None
    v = value.strip()
    neg = (v.startswith("(") and v.endswith(")")) or v.startswith("-")
    try:
        n = float(v.strip("()-").replace(",", ""))
    except ValueError:
        return None
    return -n if neg else n


# --------------------------------------------------------------------------- #
# 2) parse_item_line: kolom Retailer / Preference opsional -> parse dari BELAKANG
#    [Pref Y/N]? Qty -> sisa: DESC... GENDER CATEGORY [RETAILER]?
#    GENDER = token 1 huruf, ada di posisi -3 (ada retailer) atau -2 (tanpa retailer)
# --------------------------------------------------------------------------- #
def parse_item_line(ln):
    t = ln.split()
    if len(t) < 8 or not (re.fullmatch(r"\d{10}", t[0]) and t[1].isdigit()):
        return None
    i = 2
    refs = []
    while i < len(t) and t[i].isdigit():
        refs.append(t[i])
        i += 1
    if not refs or i >= len(t) - 3:
        return None
    article, rest = t[i], t[i + 1:]
    pref = None
    if rest[-1] in ("Y", "N"):
        pref = rest.pop()
    if not rest or not re.fullmatch(r"[\d,]+", rest[-1]):
        return None
    qty = rest.pop()
    g = next((k for k in (len(rest) - 3, len(rest) - 2)
              if k > 0 and re.fullmatch(r"[A-Z]", rest[k])), None)
    if g is None or g + 1 >= len(rest):
        return None
    desc, gender, cat = rest[:g], rest[g], rest[g + 1]
    retailer = rest[g + 2] if g + 2 < len(rest) else None
    market_po = sales_order = None
    if len(refs) >= 3:
        market_po, sales_order = refs[-3], refs[-2]
    elif len(refs) == 2:
        sales_order = refs[0]
    return {
        "PO_No": t[0], "PO_Line": int(t[1]),
        "Market_PO_Number": market_po, "Sales_Order_No": sales_order,
        "Working_No": refs[-1], "Article_No": article,
        "Article_Description": " ".join(desc), "Gender": gender, "Category": cat,
        "Retailer_Order_No": retailer, "Total_Qty": to_num(qty),
        "Preference_Indicator": pref,
    }


# --------------------------------------------------------------------------- #
# 3) Buang header/footer halaman >= 2 supaya tidak mengotori buffer adjustment
# --------------------------------------------------------------------------- #
PAGE_NOISE = re.compile(
    r"^(THE LOOK \(MACAO COMMERCIAL|OFFSHORE\) COMPANY LIMITED|UNIT 1703-1704|AIA TOWER|"
    r"NOS 251A|MACAU,999999|MACAO$|Phone: 853-|Invoice Number$|PGDH\d+$|Page \d+ of \d+$)"
)


def strip_page_noise(page_text: str) -> str:
    return "\n".join(l for l in page_text.splitlines() if not PAGE_NOISE.match(l.strip()))

# di read_pdf():
#   pages = [p.extract_text() or "" for p in pdf.pages]
#   text = "\n".join([pages[0]] + [strip_page_noise(p) for p in pages[1:]])


# --------------------------------------------------------------------------- #
# 4) Total: tambah Agreed Discount, dan sertakan di validasi Invoice Total
# --------------------------------------------------------------------------- #
# TOTAL_LABELS["Agreed_Discount"] = rf"Agreed Discount\s+(\(?-?{NUM}\)?)"
# di validate():
#   check("PO Net + Additional + Discount + VAT = Invoice Total", t.get("Invoice_Total"),
#         round((t.get("Total_PO_Net_Amount") or 0) + (t.get("Additional_Charge") or 0)
#               + (t.get("Agreed_Discount") or 0) + (t.get("Total_VAT") or 0), 2))


# --------------------------------------------------------------------------- #
# 5) Header: regex yang terlalu sempit
# --------------------------------------------------------------------------- #
# (letakkan SETELAH blok Company Code / GPS Customer Number di parse_header)
def header_fixes(h, text, parties):
    h["Consignee_Tax_ID"] = (
        search(r"(?:Customer VAT nr\.|RUC:|TAX Id:|VAT(?: No\.?)?:)\s*(\w+)",
               parties.get("Consignee", ""), flags=re.I | re.M)
        or h.get("Customer_VAT_No")
    )
    m = re.search(r"Customer Number Brand\n(\S+)\s+(\w+)$", text, re.M)
    if m:
        h["Customer_Number"] = None if m.group(1) == "--" else m.group(1)
        h["Brand"] = m.group(2)
    raw = search(r"Shipment Country Destination To[^\n]*\n([^\n]+)", text) or ""
    origin = h.get("Origin_From") or ""
    ship = origin if origin and raw.startswith(origin) else (raw.split() or [""])[0]
    h["Shipment_Country"] = ship or None
    h["Destination_Country"] = raw[len(ship):].strip() or None


# --------------------------------------------------------------------------- #
# 6) Jangan diam-diam: tandai invoice yang perlu direview
# --------------------------------------------------------------------------- #
def review_reason(inv):
    if not inv.items:
        return "tidak ada item terbaca"
    bad = sum(c["Status"] != "OK" for c in inv.checks)
    return f"{bad} validasi gagal" if bad else None

# di parse_invoice(), sebelum return:
#   reason = review_reason(inv)
#   inv.header["Status"] = "REVIEW" if reason else "OK"
#   inv.header["Status_Detail"] = reason
# di process_files(), pada cabang sukses:
#   if inv.header.get("Status") == "REVIEW":
#       issues.append({"Source_File": path.name, "Type": "REVIEW", "Detail": inv.header["Status_Detail"]})

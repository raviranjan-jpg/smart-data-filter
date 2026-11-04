import io
import re
import json
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path("app_data")
FILES_DIR = APP_DIR / "uploads"
INDEX_FILE = APP_DIR / "file_index.json"
CATEGORIES = ["List Downloaded", "Call Data Export", "Bulk Data"]

st.set_page_config(page_title="Nexgen Data Hub", page_icon="📊", layout="wide")

# ---------- Storage and data helpers ----------
def ensure_storage():
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text("[]", encoding="utf-8")

def load_index():
    ensure_storage()
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_index(items):
    ensure_storage()
    INDEX_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name) or "uploaded_file"

def safe_export_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()) or "nexgen_export"

def read_text_file(raw_bytes, delimiter_choice="Auto-detect", has_header=True):
    decoded = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            decoded = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise ValueError("Could not decode this TXT/CSV file.")
    delimiters = {"Comma": ",", "Pipe (|)": "|", "Tab": "\t", "Semicolon": ";", "Space(s)": r"\s+"}
    if delimiter_choice in delimiters:
        sep = delimiters[delimiter_choice]
    else:
        sample = "\n".join(line for line in decoded.splitlines()[:10] if line.strip())
        counts = {d: sample.count(d) for d in [",", "|", "\t", ";"]}
        sep = max(counts, key=counts.get) if max(counts.values(), default=0) else r"\s+"
    df = pd.read_csv(io.StringIO(decoded), sep=sep, engine="python", dtype=str,
                     keep_default_na=False, header=0 if has_header else None, on_bad_lines="warn")
    if not has_header:
        df.columns = [f"Column_{i+1}" for i in range(len(df.columns))]
    return df

def read_file(path, delimiter_choice="Auto-detect", has_header=True):
    suffix = Path(path).suffix.lower()
    if suffix in {".txt", ".csv"}:
        return read_text_file(Path(path).read_bytes(), delimiter_choice, has_header)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    raise ValueError(f"Unsupported file type: {suffix}")

def unique_headers(df):
    cols, seen = [], {}
    for i, col in enumerate(df.columns):
        label = str(col).strip() or f"Unnamed_{i+1}"
        seen[label] = seen.get(label, 0) + 1
        cols.append(label if seen[label] == 1 else f"{label}_{seen[label]}")
    df.columns = cols
    return df

def excel_bytes(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered Data")
    return out.getvalue()

def download_buttons_inline(df, filename, key):
    xlsx, csv, txt = st.columns(3, gap="small")
    xlsx.download_button("Excel", data=excel_bytes(df), file_name=safe_export_name(filename)+".xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True, key=f"{key}_xlsx")
    csv.download_button("CSV", data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=safe_export_name(filename)+".csv", mime="text/csv",
        use_container_width=True, key=f"{key}_csv")
    txt.download_button("TXT", data=df.to_csv(index=False, sep="|").encode("utf-8"),
        file_name=safe_export_name(filename)+".txt", mime="text/plain",
        use_container_width=True, key=f"{key}_txt")

def apply_condition(frame, col, operator, value):
    s = frame[col].astype(str)
    if operator == "Contains":
        return frame[s.str.contains(value, case=False, na=False, regex=False)]
    if operator == "Does not contain":
        return frame[~s.str.contains(value, case=False, na=False, regex=False)]
    if operator == "Equals":
        return frame[s.str.casefold() == value.casefold()]
    if operator == "Starts with":
        return frame[s.str.lower().str.startswith(value.lower())]
    if operator == "Is blank":
        return frame[s.str.strip() == ""]
    if operator == "Is not blank":
        return frame[s.str.strip() != ""]
    if operator in ("Greater than", "Less than"):
        nums = pd.to_numeric(s.str.replace(",", "", regex=False), errors="coerce")
        return frame[nums > float(value)] if operator == "Greater than" else frame[nums < float(value)]
    return frame

# ---------- Styling ----------
st.markdown("""
<style>
    .stApp { background: linear-gradient(180deg, #f4f7fb 0%, #f8fafc 42%, #eef3f9 100%); }
    .block-container { padding-top: 1.6rem; padding-bottom: 2.5rem; max-width: 1450px; }
    .hero {
        padding: 28px 32px; border-radius: 22px; color: white;
        background: linear-gradient(115deg, #101d3a 0%, #173d68 55%, #167d89 100%);
        box-shadow: 0 12px 30px rgba(17, 44, 77, .16); margin-bottom: 22px;
    }
    .hero-kicker { color: #a9e5e5; font-size: 12px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; }
    .hero h1 { color: white; font-size: 34px; margin: 7px 0 6px 0; letter-spacing: -.8px; }
    .hero p { color: #dceaf5; font-size: 15px; margin: 0; max-width: 760px; }
    .metric-card {
        background: white; border: 1px solid #e3eaf2; border-radius: 16px;
        padding: 18px 20px; min-height: 118px; box-shadow: 0 5px 18px rgba(20, 45, 75, .05);
    }
    .metric-label { color: #64748b; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; }
    .metric-value { color: #10233f; font-size: 29px; font-weight: 800; margin-top: 7px; line-height: 1.15; }
    .metric-note { color: #8290a3; font-size: 12px; margin-top: 5px; }
    .section-heading { color: #142943; font-size: 19px; font-weight: 800; margin: 22px 0 10px 0; }
    .category-card {
        background: white; border: 1px solid #e3eaf2; border-radius: 16px;
        padding: 18px; box-shadow: 0 5px 18px rgba(20, 45, 75, .04);
    }
    .category-title { color: #52647a; font-size: 13px; font-weight: 700; }
    .category-count { color: #142943; font-size: 25px; font-weight: 800; margin-top: 5px; }
    .category-sub { color: #8492a5; font-size: 12px; }
    div[data-testid="stTabs"] button { font-weight: 700; }
    div.stButton > button[kind="primary"] { border-radius: 10px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

ensure_storage()
items = load_index()
total_files = len(items)
total_rows = sum(int(x.get("rows", 0) or 0) for x in items)
total_columns = sum(int(x.get("columns", 0) or 0) for x in items)
category_stats = {
    cat: {
        "files": sum(1 for x in items if x.get("category") == cat),
        "rows": sum(int(x.get("rows", 0) or 0) for x in items if x.get("category") == cat)
    } for cat in CATEGORIES
}

st.markdown("""
<div class="hero">
  <div class="hero-kicker">Nexgen BPS · Data Operations Workspace</div>
  <h1>Welcome to Nexgen Data Hub</h1>
  <p>Your central workspace to organise lead files, explore call dispositions, remove duplicates and export the exact data your team needs.</p>
</div>
""", unsafe_allow_html=True)

# KPI cards
kpis = [
    ("TOTAL FILES", f"{total_files:,}", "Files saved in the current app library", "📁"),
    ("TOTAL RECORDS", f"{total_rows:,}", "Rows across all uploaded files", "🧾"),
    ("CATEGORIES", f"{sum(1 for v in category_stats.values() if v['files']):,}/3", "Categories currently in use", "🗂️"),
    ("TOTAL COLUMNS", f"{total_columns:,}", "Column count summed across files", "▦"),
]
cols = st.columns(4, gap="medium")
for col, (label, value, note, icon) in zip(cols, kpis):
    with col:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-label">{icon} &nbsp; {label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-note">{note}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<div class="section-heading">Your data categories</div>', unsafe_allow_html=True)
cat_cols = st.columns(3, gap="medium")
cat_icons = ["📥", "📞", "📦"]
for col, cat, icon in zip(cat_cols, CATEGORIES, cat_icons):
    stats = category_stats[cat]
    with col:
        st.markdown(f"""
        <div class="category-card">
          <div class="category-title">{icon} &nbsp; {cat}</div>
          <div class="category-count">{stats['rows']:,} <span style="font-size:13px;font-weight:600;color:#718096">records</span></div>
          <div class="category-sub">{stats['files']:,} uploaded files</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<div class="section-heading">Quick actions</div>', unsafe_allow_html=True)
qa1, qa2, qa3 = st.columns(3, gap="medium")
with qa1:
    st.info("**⬆️ Upload new data**\n\nAdd TXT, CSV or Excel files and assign a category.")
with qa2:
    st.info("**🗂️ Manage your library**\n\nReview uploaded files by category and remove files you no longer need.")
with qa3:
    st.info("**🔎 Filter & export**\n\nSelect files, choose dispositions, remove duplicates and download results.")

st.caption(f"Dashboard summary · Updated on {datetime.now().strftime('%d %b %Y, %I:%M %p')} · Counts reflect files currently present in this app's local library.")

tab_upload, tab_library, tab_export = st.tabs(["⬆️ Upload File", "🗂️ File Library", "🔎 Filter & Download"])

with tab_upload:
    st.subheader("Upload files one at a time")
    category = st.selectbox("Choose category", CATEGORIES)
    uploaded = st.file_uploader("Upload Notepad, CSV or Excel", type=["txt", "csv", "xlsx", "xls"])
    left, right = st.columns(2)
    delimiter = left.selectbox("TXT/CSV delimiter", ["Auto-detect", "Comma", "Pipe (|)", "Tab", "Semicolon", "Space(s)"])
    has_header = right.checkbox("First row contains headers", True)
    if uploaded and st.button("Save file to library", type="primary"):
        current_items = load_index()
        fid = uuid.uuid4().hex
        stored = f"{fid}_{safe_name(uploaded.name)}"
        path = FILES_DIR / stored
        path.write_bytes(uploaded.getvalue())
        try:
            frame = unique_headers(read_file(path, delimiter, has_header))
            current_items.append({"id": fid, "original_name": uploaded.name, "stored_name": stored, "category": category,
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "rows": len(frame),
                "columns": len(frame.columns), "delimiter": delimiter, "has_header": has_header})
            save_index(current_items)
            st.success(f"Saved {uploaded.name} in {category}: {len(frame):,} rows.")
            st.info("Refresh the page to update the dashboard counts.")
        except Exception as exc:
            path.unlink(missing_ok=True)
            st.error(f"Unable to read file: {exc}")

with tab_library:
    st.subheader("Uploaded file library")
    current_items = load_index()
    cat_filter = st.selectbox("Category", ["All categories"] + CATEGORIES)
    shown = current_items if cat_filter == "All categories" else [x for x in current_items if x["category"] == cat_filter]
    st.metric("Files", len(shown))
    if shown:
        st.dataframe(pd.DataFrame([{"File": x["original_name"], "Category": x["category"],
            "Uploaded": x["uploaded_at"], "Rows": x["rows"], "Columns": x["columns"]} for x in shown]),
            use_container_width=True, hide_index=True)
        delete_map = {f'{x["original_name"]} · {x["category"]} · {x["uploaded_at"]}': x["id"] for x in shown}
        delete_choice = st.selectbox("Delete file (optional)", ["— None —"] + list(delete_map))
        if delete_choice != "— None —" and st.button("Delete selected file"):
            fid = delete_map[delete_choice]
            record = next(x for x in current_items if x["id"] == fid)
            (FILES_DIR / record["stored_name"]).unlink(missing_ok=True)
            save_index([x for x in current_items if x["id"] != fid])
            st.success("Deleted. Refresh the page to update dashboard counts.")
            st.rerun()
    else:
        st.info("No files uploaded in this category yet.")

with tab_export:
    st.subheader("Filter and download")
    current_items = load_index()
    if not current_items:
        st.info("Upload files first.")
    else:
        chosen_categories = st.multiselect("Choose categories", CATEGORIES, default=CATEGORIES)
        candidates = [x for x in current_items if x["category"] in chosen_categories]
        file_map = {f'{x["original_name"]} · {x["category"]} · {x["uploaded_at"]}': x for x in candidates}
        chosen_files = st.multiselect("Select files to combine", list(file_map))
        if chosen_files:
            frames = []
            for label in chosen_files:
                record = file_map[label]
                file_path = FILES_DIR / record["stored_name"]
                if file_path.exists():
                    frames.append(unique_headers(read_file(file_path, record["delimiter"], record["has_header"])))
                else:
                    st.error(f'Stored file missing: {record["original_name"]}')
            if frames:
                data = pd.concat(frames, ignore_index=True, sort=False).fillna("")
                st.success(f"{len(frames)} files loaded · {len(data):,} records · {len(data.columns)} columns")
                all_cols = list(data.columns)
                output_cols = st.multiselect("Select headers for download", all_cols, default=all_cols)

                st.markdown("### Disposition / Status")
                status_col = st.selectbox("Choose status/disposition column", ["— No disposition filter —"] + all_cols)
                filtered = data.copy()
                all_dispositions = []
                if status_col != "— No disposition filter —":
                    all_dispositions = sorted([str(v) for v in data[status_col].unique() if str(v).strip()])
                    st.caption(f"{len(all_dispositions)} distinct values found. Each disposition has its own download buttons.")
                    select_all = st.checkbox("Select all dispositions", value=False)
                    selected_dispositions = []
                    for idx, disposition in enumerate(all_dispositions):
                        subset = data[data[status_col].astype(str) == disposition].copy()
                        check_col, name_col, count_col, button_col = st.columns([0.55, 2.2, 1.0, 4.5], vertical_alignment="center")
                        checked = check_col.checkbox(" ", value=select_all, key=f"disp_select_{idx}_{status_col}")
                        name_col.markdown(f"**{disposition}**")
                        count_col.caption(f"{len(subset):,} rows")
                        if checked:
                            selected_dispositions.append(disposition)
                        with button_col:
                            if output_cols:
                                download_buttons_inline(subset[output_cols], f"nexgen_{disposition}", f"disp_{idx}")
                    filtered = data[data[status_col].astype(str).isin(selected_dispositions)].copy() if selected_dispositions else data.iloc[0:0].copy()
                    st.info(f"Selected {len(selected_dispositions)} of {len(all_dispositions)} dispositions.")

                with st.expander("Additional filter (optional)"):
                    extra_col = st.selectbox("Column", ["— None —"] + all_cols)
                    if extra_col != "— None —":
                        op = st.selectbox("Condition", ["Contains", "Does not contain", "Equals", "Starts with", "Is blank", "Is not blank", "Greater than", "Less than"])
                        val = st.text_input("Value")
                        if st.button("Apply additional filter"):
                            filtered = apply_condition(filtered, extra_col, op, val)

                st.markdown("### Duplicate filtration")
                remove_dupes = st.checkbox("Remove duplicate records", value=False)
                dup_cols = st.multiselect("Duplicate check column(s)", all_cols,
                    help="Select phone_number/mobile column to keep one record per phone number. Leave empty to compare full rows.")
                if remove_dupes:
                    filtered = filtered.drop_duplicates(subset=dup_cols or None, keep="first")

                st.markdown("### Combined selected download")
                st.caption("This export combines only the dispositions ticked above.")
                if len(filtered):
                    a, b = st.columns(2)
                    start = a.number_input("Start row", min_value=1, max_value=len(filtered), value=1)
                    end = b.number_input("End row", min_value=int(start), max_value=len(filtered), value=len(filtered))
                    combined = filtered.iloc[int(start)-1:int(end)].copy()
                else:
                    combined = filtered.copy()
                    st.info("Select one or more dispositions above to enable combined download.")
                if output_cols:
                    combined = combined[[c for c in output_cols if c in combined.columns]]
                st.metric("Combined selected records", f"{len(combined):,}")
                export_name = st.text_input("Combined export filename", "nexgen_selected_dispositions")
                if output_cols and len(combined):
                    download_buttons_inline(combined, export_name, "combined_selected")
                st.markdown("### Preview")
                st.dataframe(combined.head(300), use_container_width=True, hide_index=True)

st.divider()
st.caption("Nexgen Data Hub · Executive-style dashboard · Category totals · Inline disposition downloads")

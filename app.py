import io
import os
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
ALLOWED_EXTENSIONS = {".txt", ".csv", ".xlsx", ".xls"}

st.set_page_config(page_title="Nexgen Data Hub", page_icon="📊", layout="wide")

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
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
    return cleaned or "uploaded_file"

def read_text_file(raw_bytes, delimiter_choice="Auto-detect", has_header=True):
    # Try common encodings.
    decoded = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            decoded = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise ValueError("Could not decode this TXT/CSV file.")

    if delimiter_choice == "Comma":
        sep = ","
    elif delimiter_choice == "Pipe (|)":
        sep = "|"
    elif delimiter_choice == "Tab":
        sep = "\t"
    elif delimiter_choice == "Semicolon":
        sep = ";"
    elif delimiter_choice == "Space(s)":
        sep = r"\s+"
    else:
        # Detect common delimiters from the first non-empty lines.
        sample = "\n".join([line for line in decoded.splitlines()[:10] if line.strip()])
        candidates = [",", "|", "\t", ";"]
        counts = {d: sample.count(d) for d in candidates}
        sep = max(counts, key=counts.get) if max(counts.values(), default=0) > 0 else r"\s+"

    header = 0 if has_header else None
    df = pd.read_csv(
        io.StringIO(decoded),
        sep=sep,
        engine="python",
        dtype=str,
        keep_default_na=False,
        header=header,
        on_bad_lines="warn",
    )
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

def make_unique_headers(df):
    cols, counts = [], {}
    for i, col in enumerate(df.columns):
        label = str(col).strip() or f"Unnamed_{i+1}"
        counts[label] = counts.get(label, 0) + 1
        cols.append(label if counts[label] == 1 else f"{label}_{counts[label]}")
    df.columns = cols
    return df

def excel_bytes(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Filtered Data")
    return out.getvalue()

def safe_export_name(name):
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return name or "filtered_data"

ensure_storage()
st.title("📊 Nexgen Data Hub")
st.caption("Upload and organise files by category. Combine selected files, remove duplicates, filter records and export the result.")

with st.sidebar:
    st.header("📁 File Library")
    st.caption("Files are organised into the categories below.")
    st.markdown("**1. List Downloaded**")
    st.markdown("**2. Call Data Export**")
    st.markdown("**3. Bulk Data**")
    st.divider()
    st.warning(
        "Storage note: this first version stores files on the app's local disk. "
        "Streamlit Community Cloud does not guarantee that local files survive app restarts or redeployments. "
        "For reliable long-term storage, connect persistent cloud storage before using this as your only archive."
    )

tab_upload, tab_library, tab_extract = st.tabs(["⬆️ Upload File", "🗂️ File Library", "🔎 Filter & Download"])

with tab_upload:
    st.subheader("Upload files one at a time")
    category = st.selectbox("Choose category", CATEGORIES, key="upload_category")
    uploaded = st.file_uploader(
        "Choose a Notepad, CSV or Excel file",
        type=["txt", "csv", "xlsx", "xls"],
        accept_multiple_files=False,
        key="single_file_upload",
        help="Upload one file, save it under a category, then upload the next file."
    )
    c1, c2 = st.columns(2)
    delimiter_choice = c1.selectbox("TXT/CSV delimiter", ["Auto-detect", "Comma", "Pipe (|)", "Tab", "Semicolon", "Space(s)"])
    has_header = c2.checkbox("First row contains column headers", value=True)
    if uploaded:
        st.write(f"Selected: **{uploaded.name}** ({uploaded.size:,} bytes)")
        if st.button("Save file to library", type="primary"):
            suffix = Path(uploaded.name).suffix.lower()
            if suffix not in ALLOWED_EXTENSIONS:
                st.error("Unsupported file type.")
            else:
                items = load_index()
                file_id = uuid.uuid4().hex
                stored_name = f"{file_id}_{safe_name(uploaded.name)}"
                stored_path = FILES_DIR / stored_name
                stored_path.write_bytes(uploaded.getvalue())
                try:
                    # Validate/read before recording it in the library.
                    test_df = read_file(stored_path, delimiter_choice, has_header)
                    item = {
                        "id": file_id,
                        "original_name": uploaded.name,
                        "stored_name": stored_name,
                        "category": category,
                        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "rows": int(len(test_df)),
                        "columns": int(len(test_df.columns)),
                        "delimiter": delimiter_choice,
                        "has_header": bool(has_header),
                    }
                    items.append(item)
                    save_index(items)
                    st.success(f"Saved **{uploaded.name}** under **{category}** ({len(test_df):,} rows, {len(test_df.columns):,} columns).")
                except Exception as exc:
                    stored_path.unlink(missing_ok=True)
                    st.error(f"Could not read this file: {exc}")

with tab_library:
    st.subheader("Your uploaded files")
    items = load_index()
    if not items:
        st.info("No files uploaded yet. Use the Upload File tab to add your first file.")
    else:
        selected_category = st.selectbox("View category", ["All categories"] + CATEGORIES, key="library_category")
        visible = items if selected_category == "All categories" else [x for x in items if x["category"] == selected_category]
        st.metric("Files in library", len(visible))
        library_rows = [{
            "File name": x["original_name"],
            "Category": x["category"],
            "Uploaded": x["uploaded_at"],
            "Rows": x.get("rows", 0),
            "Columns": x.get("columns", 0),
        } for x in visible]
        st.dataframe(pd.DataFrame(library_rows), use_container_width=True, hide_index=True)
        delete_options = {f'{x["original_name"]} | {x["category"]} | {x["uploaded_at"]}': x["id"] for x in visible}
        to_delete = st.selectbox("Select a file to delete (optional)", ["— None —"] + list(delete_options.keys()))
        if to_delete != "— None —" and st.button("Delete selected file", type="secondary"):
            target_id = delete_options[to_delete]
            target = next((x for x in items if x["id"] == target_id), None)
            if target:
                (FILES_DIR / target["stored_name"]).unlink(missing_ok=True)
                save_index([x for x in items if x["id"] != target_id])
                st.success("File deleted from this app's local library.")
                st.rerun()

with tab_extract:
    st.subheader("Select files and build your export")
    items = load_index()
    if not items:
        st.info("Upload files first.")
    else:
        categories_to_use = st.multiselect("Filter library by category", CATEGORIES, default=CATEGORIES)
        candidates = [x for x in items if x["category"] in categories_to_use]
        labels = {f'{x["original_name"]}  ·  {x["category"]}  ·  {x["uploaded_at"]}': x for x in candidates}
        selected_labels = st.multiselect("Select one or more files to combine", list(labels.keys()))
        if selected_labels:
            frames = []
            errors = []
            for label in selected_labels:
                item = labels[label]
                path = FILES_DIR / item["stored_name"]
                if not path.exists():
                    errors.append(f'{item["original_name"]}: stored file is missing (local app storage may have reset).')
                    continue
                try:
                    frame = read_file(path, item.get("delimiter", "Auto-detect"), item.get("has_header", True))
                    frame = make_unique_headers(frame)
                    frame["_source_file"] = item["original_name"]
                    frame["_source_category"] = item["category"]
                    frames.append(frame)
                except Exception as exc:
                    errors.append(f'{item["original_name"]}: {exc}')
            for err in errors:
                st.warning(err)

            if frames:
                # Union columns across files; missing columns are blank.
                data = pd.concat(frames, ignore_index=True, sort=False).fillna("")
                st.success(f"Combined {len(frames)} file(s): **{len(data):,} rows** and **{len(data.columns):,} columns**.")
                all_columns = list(data.columns)
                default_cols = [c for c in all_columns if not c.startswith("_source_")]
                selected_columns = st.multiselect("Choose output headers", all_columns, default=default_cols)

                st.markdown("#### Duplicate filtration")
                duplicate_enabled = st.checkbox("Remove duplicate records", value=False)
                duplicate_cols = st.multiselect(
                    "Identify duplicates using these column(s)",
                    options=all_columns,
                    default=[],
                    help="For duplicate mobile numbers, select only the mobile-number column. For exact duplicate rows, leave this empty and choose all columns below."
                )
                if duplicate_enabled:
                    if duplicate_cols:
                        deduped = data.drop_duplicates(subset=duplicate_cols, keep="first")
                        st.caption("Duplicate check uses: " + ", ".join(duplicate_cols))
                    else:
                        deduped = data.drop_duplicates(keep="first")
                        st.caption("Duplicate check uses the complete row.")
                else:
                    deduped = data.copy()

                st.markdown("#### Optional filter")
                filter_col = st.selectbox("Filter column", ["— No filter —"] + all_columns)
                filtered = deduped
                if filter_col != "— No filter —":
                    operator = st.selectbox("Condition", ["Contains", "Equals", "Starts with", "Is blank", "Is not blank"])
                    if operator in ["Is blank", "Is not blank"]:
                        filter_value = ""
                    else:
                        filter_value = st.text_input("Match value")
                    if st.button("Apply filter"):
                        series = filtered[filter_col].astype(str)
                        if operator == "Contains":
                            filtered = filtered[series.str.contains(filter_value, case=False, na=False, regex=False)]
                        elif operator == "Equals":
                            filtered = filtered[series.str.casefold() == filter_value.casefold()]
                        elif operator == "Starts with":
                            filtered = filtered[series.str.lower().str.startswith(filter_value.lower())]
                        elif operator == "Is blank":
                            filtered = filtered[series.str.strip() == ""]
                        elif operator == "Is not blank":
                            filtered = filtered[series.str.strip() != ""]
                        st.session_state["filtered_extract"] = filtered
                        st.rerun()
                # If the user has applied a filter in this session, use it.
                if "filtered_extract" in st.session_state and st.session_state["filtered_extract"] is not None:
                    filtered = st.session_state["filtered_extract"]
                else:
                    filtered = deduped

                st.markdown("#### Row range")
                st.caption("Row range is applied after duplicate removal and filtering. Start/end are inclusive.")
                total = len(filtered)
                if total:
                    r1, r2 = st.columns(2)
                    start = r1.number_input("Start row", min_value=1, max_value=total, value=1, step=1)
                    end = r2.number_input("End row", min_value=int(start), max_value=total, value=total, step=1)
                    output = filtered.iloc[int(start)-1:int(end)].copy()
                else:
                    output = filtered.copy()
                    st.warning("No records match the selected conditions.")

                if selected_columns:
                    output = output[[c for c in selected_columns if c in output.columns]]
                elif len(output.columns):
                    st.warning("Select at least one output header to export.")

                m1, m2, m3 = st.columns(3)
                m1.metric("Combined rows", f"{len(data):,}")
                m2.metric("After duplicate removal", f"{len(deduped):,}")
                m3.metric("Rows to export", f"{len(output):,}")

                st.markdown("#### Preview")
                st.dataframe(output.head(300), use_container_width=True, hide_index=True)
                export_name = st.text_input("Export file name", value="smart_data_export")
                if selected_columns:
                    e1, e2, e3 = st.columns(3)
                    e1.download_button("Download Excel", data=excel_bytes(output), file_name=safe_export_name(export_name)+".xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    e2.download_button("Download CSV", data=output.to_csv(index=False).encode("utf-8-sig"), file_name=safe_export_name(export_name)+".csv", mime="text/csv", use_container_width=True)
                    e3.download_button("Download TXT", data=output.to_csv(index=False, sep="|").encode("utf-8"), file_name=safe_export_name(export_name)+".txt", mime="text/plain", use_container_width=True)

st.divider()
st.caption("Nexgen Data Hub · Category-based file library · Duplicate filtration · Multi-file export")

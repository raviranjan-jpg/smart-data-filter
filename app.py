import io
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Smart Data Filter", page_icon="📊", layout="wide")

st.title("📊 Smart Data Filter")
st.caption("Upload Excel or CSV files, choose columns, filter records, and export exactly what you need.")

with st.sidebar:
    st.header("Settings")
    st.info("Files are processed in this app session. Avoid uploading sensitive customer data to a public deployment unless access and privacy controls are appropriate.")
    remove_duplicates = st.checkbox("Remove duplicate rows", value=False)
    duplicate_subset_mode = st.radio("Duplicate check", ["All columns", "Selected columns"], disabled=not remove_duplicates)

uploaded = st.file_uploader("Upload an Excel or CSV file", type=["xlsx", "xls", "csv"])

def read_upload(file):
    name = file.name.lower()
    if name.endswith(".csv"):
        file.seek(0)
        try:
            return pd.read_csv(file, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            file.seek(0)
            return pd.read_csv(file, dtype=str, keep_default_na=False, encoding="latin-1")
    file.seek(0)
    return pd.read_excel(file, dtype=str, keep_default_na=False)

def to_excel_bytes(frame):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="Filtered Data")
    return output.getvalue()

def safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value or "filtered_data"

if uploaded:
    try:
        original = read_upload(uploaded)
        if original.empty and len(original.columns) == 0:
            st.error("The uploaded file appears to be empty or has no readable headers.")
            st.stop()

        # Make duplicate/blank headers distinguishable without changing cell values.
        cols = []
        seen = {}
        for i, col in enumerate(original.columns):
            label = str(col).strip() or f"Unnamed_{i+1}"
            seen[label] = seen.get(label, 0) + 1
            cols.append(label if seen[label] == 1 else f"{label}_{seen[label]}")
        original.columns = cols

        st.success(f"Loaded **{len(original):,} rows** and **{len(original.columns):,} columns**.")
        st.subheader("1. Choose columns")
        chosen = st.multiselect("Select the headers to keep in the exported file", options=list(original.columns), default=list(original.columns))
        if not chosen:
            st.warning("Select at least one column to continue.")
            st.stop()

        st.subheader("2. Filter records")
        filtered = original.copy()
        with st.expander("Add filters", expanded=True):
            filter_col = st.selectbox("Column to filter", ["— Select a column —"] + list(original.columns))
            if filter_col != "— Select a column —":
                mode = st.selectbox("Filter type", ["Contains", "Does not contain", "Equals", "Starts with", "Is blank", "Is not blank", "Greater than", "Less than", "Between"])
                if mode in ["Is blank", "Is not blank"]:
                    value = None
                elif mode == "Between":
                    c1, c2 = st.columns(2)
                    value = c1.text_input("From (inclusive)")
                    value2 = c2.text_input("To (inclusive)")
                else:
                    value = st.text_input("Value")
                if st.button("Apply filter", type="primary"):
                    series = filtered[filter_col].astype(str)
                    if mode == "Contains":
                        filtered = filtered[series.str.contains(str(value), case=False, na=False, regex=False)]
                    elif mode == "Does not contain":
                        filtered = filtered[~series.str.contains(str(value), case=False, na=False, regex=False)]
                    elif mode == "Equals":
                        filtered = filtered[series.str.casefold() == str(value).casefold()]
                    elif mode == "Starts with":
                        filtered = filtered[series.str.lower().str.startswith(str(value).lower())]
                    elif mode == "Is blank":
                        filtered = filtered[series.str.strip() == ""]
                    elif mode == "Is not blank":
                        filtered = filtered[series.str.strip() != ""]
                    elif mode in ["Greater than", "Less than", "Between"]:
                        numeric = pd.to_numeric(series.str.replace(",", "", regex=False), errors="coerce")
                        if mode == "Greater than":
                            filtered = filtered[numeric > float(value)]
                        elif mode == "Less than":
                            filtered = filtered[numeric < float(value)]
                        else:
                            lo = float(value) if value.strip() else float("-inf")
                            hi = float(value2) if value2.strip() else float("inf")
                            filtered = filtered[(numeric >= lo) & (numeric <= hi)]
                    st.session_state["active_filtered"] = filtered
                    st.rerun()

        if "active_filtered" in st.session_state:
            # Keep filtering result for this upload; clear if a different file is uploaded.
            filtered = st.session_state["active_filtered"]
        if remove_duplicates:
            subset = chosen if duplicate_subset_mode == "Selected columns" else None
            filtered = filtered.drop_duplicates(subset=subset)

        st.subheader("3. Select row range")
        st.caption("The range is applied after filtering. Row numbers start at 1.")
        total = len(filtered)
        if total:
            c1, c2 = st.columns(2)
            start = c1.number_input("Start row", min_value=1, max_value=total, value=1, step=1)
            end = c2.number_input("End row", min_value=int(start), max_value=total, value=total, step=1)
            result = filtered.iloc[int(start)-1:int(end)][chosen].copy()
        else:
            result = filtered[chosen].copy()
            st.warning("No records match the current filter.")

        a, b, c = st.columns(3)
        a.metric("Uploaded rows", f"{len(original):,}")
        b.metric("Matching rows", f"{len(filtered):,}")
        c.metric("Rows to export", f"{len(result):,}")

        st.subheader("4. Preview")
        st.dataframe(result.head(500), use_container_width=True, hide_index=True)
        if len(result) > 500:
            st.caption("Preview shows the first 500 rows. The download includes the full selected range.")

        st.subheader("5. Download")
        default_name = safe_filename(uploaded.name.rsplit(".", 1)[0]) + "_filtered"
        filename = st.text_input("Export file name (without extension)", value=default_name)
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Download Excel", data=to_excel_bytes(result), file_name=safe_filename(filename) + ".xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        csv_data = result.to_csv(index=False).encode("utf-8-sig")
        d2.download_button("⬇️ Download CSV", data=csv_data, file_name=safe_filename(filename) + ".csv", mime="text/csv", use_container_width=True)
    except Exception as exc:
        st.error(f"Could not process this file: {exc}")
        st.info("Check that the file is a valid Excel/CSV file with a header row.")
else:
    st.info("Start by uploading an Excel (.xlsx/.xls) or CSV file.")
    st.markdown("**Included:** column selection, text and numeric filters, blank checks, duplicate removal, row-range export, preview, Excel and CSV downloads.")

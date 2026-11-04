# Nexgen Data Hub V13

V13 builds on the supplied V12 app.py.

## Updates
- Cached file parsing using Streamlit data cache, keyed by file path and modification metadata.
- Faster disposition counts using one value-count aggregation instead of rescanning the full data for each disposition.
- Cached export payloads.
- Global customer search on the dashboard across all three categories.
- Displays every matching row, all uploaded columns, source category and source filename.
- Phone normalization removes spaces, punctuation and country-code formatting; also checks last 10 digits for numbers of 10+ digits.
- Improved navigation button text visibility.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important
The app continues to use local `app_data/` storage. Streamlit Community Cloud local storage is not guaranteed to persist across restarts or redeployments. Do not upload real customer personal data until authentication, access controls and secure persistent storage are configured. Search scans uploaded files and relies on phone/mobile/contact-like column names.

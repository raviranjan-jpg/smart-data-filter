# Nexgen Data Hub

Features:
- Upload one file at a time: TXT, CSV, XLSX, XLS
- Categorise uploads: List Downloaded, Call Data Export, Bulk Data
- Browse and delete files in the library
- Combine selected files across categories
- Select output headers
- Remove duplicate rows or duplicates based on selected columns (e.g. mobile number)
- Filter records, select an inclusive row range, and export Excel/CSV/TXT

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy
Upload `app.py`, `requirements.txt`, and `README.md` to the root of your GitHub repository. In Streamlit Community Cloud use branch `main` and main file path `app.py`.

## Important storage limitation
This version saves uploaded files in the app's local `app_data/` directory. Streamlit Community Cloud local filesystem is not a guaranteed permanent data store and can be reset during rebuilds/restarts. Do not use it as the only archive for important customer data. For durable storage, integrate a persistent service such as Supabase Storage or an appropriately secured cloud object store before relying on long-term retention.

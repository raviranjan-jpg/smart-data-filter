# Nexgen Data Hub V10

Category-first Streamlit data workspace. The dashboard shows three large category cards. Open a category to upload original TXT/CSV/Excel files, view the originals, download the automatically compiled category dataset, and filter/export within that category.

Run locally: `pip install -r requirements.txt` then `streamlit run app.py`.

Note: this version retains the existing local `app_data` storage approach. Streamlit Community Cloud local storage is not guaranteed to persist across restarts/redeployments. Do not upload real customer data until secure persistent storage and access controls are configured.

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

def category_frame(category, records=None):
    records = load_index() if records is None else records
    frames = []
    for record in records:
        if record.get("category") != category:
            continue
        file_path = FILES_DIR / record.get("stored_name", "")
        if file_path.exists():
            try:
                frames.append(unique_headers(read_file(file_path, record.get("delimiter", "Auto-detect"), record.get("has_header", True))))
            except Exception:
                pass
    return pd.concat(frames, ignore_index=True, sort=False).fillna("") if frames else pd.DataFrame()

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

# ---------- Styling: category-first premium interface ----------
st.markdown("""
<style>
:root{color-scheme:light}
.stApp{background:linear-gradient(135deg,#f4f6f2 0%,#edf2f7 55%,#f4eff7 100%)!important;color:#263548!important}
[data-testid="stAppViewContainer"]{background:transparent!important}
[data-testid="stHeader"]{background:rgba(244,246,242,.9)!important}
.block-container{max-width:1450px;padding-top:1.35rem;padding-bottom:3rem}
p,label,.stMarkdown{color:#35465a!important} h1,h2,h3,h4{color:#1c2d40!important}
.hero{padding:30px 34px;border-radius:25px;color:#fff;background:linear-gradient(115deg,#182f46,#315b72 55%,#668c86);box-shadow:0 15px 38px #1d35451c;margin-bottom:22px}
.hero small{color:#c8e1df;font-weight:800;letter-spacing:2px}.hero h1{color:white!important;font-size:36px;margin:8px 0}.hero p{color:#e6f0f1!important;margin:0}
.metric-card,.cat-card{background:rgba(255,255,255,.88);border:1px solid #dce5e5;border-radius:20px;padding:19px 21px;min-height:120px;box-shadow:0 8px 25px #203b4a0c}
.metric-label,.cat-label{font-size:12px;font-weight:850;letter-spacing:1px;color:#70818a!important;text-transform:uppercase}.metric-value{font-size:30px;font-weight:850;color:#203d50!important;margin-top:7px}.metric-note{font-size:12px;color:#829098!important}
.cat-card{min-height:175px;border-top:5px solid #5b9b91}.cat-card h3{margin:10px 0 4px}.cat-card .big{font-size:32px;font-weight:850;color:#24485a}.cat-card .sub{font-size:13px;color:#73858d}.section-title{font-size:21px;font-weight:850;color:#233f50!important;margin:25px 0 12px}
div.stButton>button,div.stDownloadButton>button{border-radius:12px!important;font-weight:750!important;border:1px solid #c7d8d7!important;background:#e6efed!important;color:#234e51!important;min-height:42px}
div.stButton>button:hover,div.stDownloadButton>button:hover{background:#d6e7e3!important;border-color:#80aaa2!important}
div.stButton>button[kind="primary"]{background:#286d69!important;color:white!important;border-color:#286d69!important}
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,textarea{background:white!important;border:1px solid #d0dddf!important;color:#263548!important;border-radius:10px!important}
div[data-baseweb="select"] *,div[data-baseweb="input"] *,textarea{color:#263548!important}
div[data-testid="stFileUploader"] section{background:#fff!important;border:1px dashed #9bb9b4!important;border-radius:14px!important}
div[data-testid="stFileUploader"] *{color:#35465a!important}
[data-testid="stAlert"]{border-radius:13px!important} hr{border-color:#dce5e5!important}
</style>
""",unsafe_allow_html=True)

ensure_storage()
items=load_index()

def stats_for(cat):
    arr=[x for x in items if x.get('category')==cat]
    return len(arr),sum(int(x.get('rows',0) or 0) for x in arr)

def render_filter_tools(category, records):
    st.markdown('<div class="section-title">🔎 Filter, clean & export</div>',unsafe_allow_html=True)
    if not records:
        st.info('Upload files in this category to unlock filtering and downloads.'); return
    file_map={f"{x['original_name']} · {x['uploaded_at']}":x for x in records}
    chosen=st.multiselect('Choose files to process',list(file_map),default=list(file_map),key=f'files_{category}')
    if not chosen: st.info('Select at least one file.'); return
    frames=[]
    for label in chosen:
        r=file_map[label]; fp=FILES_DIR/r['stored_name']
        if fp.exists(): frames.append(unique_headers(read_file(fp,r.get('delimiter','Auto-detect'),r.get('has_header',True))))
    if not frames: st.warning('Selected files could not be read.'); return
    data=pd.concat(frames,ignore_index=True,sort=False).fillna('')
    st.success(f"{len(frames)} files · {len(data):,} records · {len(data.columns)} columns")
    cols=list(data.columns); output_cols=st.multiselect('Output headers',cols,default=cols,key=f'headers_{category}')
    st.markdown('**Disposition / status filter**')
    status=st.selectbox('Select status column',['— No filter —']+cols,key=f'status_{category}')
    filtered=data.copy()
    if status!='— No filter —':
        values=sorted(str(v) for v in data[status].unique() if str(v).strip())
        st.caption(f'{len(values)} distinct values detected automatically')
        selected=st.multiselect('Choose dispositions',values,default=values,key=f'disps_{category}')
        for value in values:
            subset=data[data[status].astype(str)==value]
            st.caption(f'{value}  ·  {len(subset):,} records')
        filtered=data[data[status].astype(str).isin(selected)].copy()
    with st.expander('Additional filters'):
        extra=st.selectbox('Column',['— None —']+cols,key=f'extra_{category}')
        if extra!='— None —':
            op=st.selectbox('Condition',['Contains','Does not contain','Equals','Starts with','Is blank','Is not blank','Greater than','Less than'],key=f'op_{category}')
            val=st.text_input('Value',key=f'val_{category}')
            if st.button('Apply filter',key=f'apply_{category}'):
                filtered=apply_condition(filtered,extra,op,val)
                st.session_state[f'applied_{category}']=filtered
        if f'applied_{category}' in st.session_state: filtered=st.session_state[f'applied_{category}']
    st.markdown('**Duplicate removal**')
    dedupe=st.checkbox('Remove duplicate records',key=f'dedupe_{category}')
    dupcols=st.multiselect('Duplicate check column(s)',cols,key=f'dupcols_{category}')
    if dedupe: filtered=filtered.drop_duplicates(subset=dupcols or None,keep='first')
    if output_cols: filtered=filtered[[c for c in output_cols if c in filtered.columns]]
    st.metric('Records ready to export',f'{len(filtered):,}')
    if len(filtered):
        a,b=st.columns(2); start=a.number_input('Start row',1,len(filtered),1,key=f'start_{category}'); end=b.number_input('End row',int(start),len(filtered),len(filtered),key=f'end_{category}')
        result=filtered.iloc[int(start)-1:int(end)].copy()
        download_buttons_inline(result,f'nexgen_{category}_filtered',f'filtered_{category}')
        st.dataframe(result.head(200),use_container_width=True,hide_index=True)

# Navigation is intentionally category-first: click a large tile to enter its private workspace.
if 'page' not in st.session_state: st.session_state.page='home'
if 'active_category' not in st.session_state: st.session_state.active_category=CATEGORIES[0]

nav1,nav2,nav3=st.columns([1,1,5])
with nav1:
    if st.button('⌂  Dashboard',use_container_width=True): st.session_state.page='home'; st.rerun()
with nav2:
    if st.button('📚  All files',use_container_width=True): st.session_state.page='library'; st.rerun()

if st.session_state.page=='home':
    items=load_index(); total_files=len(items); total_rows=sum(int(x.get('rows',0) or 0) for x in items)
    st.markdown('<div class="hero"><small>NEXGEN BPS · DATA OPERATIONS</small><h1>Nexgen Data Hub</h1><p>One organised workspace for every data category. Open a category to upload, compile, filter and export its files.</p></div>',unsafe_allow_html=True)
    kpis=[('TOTAL FILES',f'{total_files:,}','Original files stored'),('TOTAL RECORDS',f'{total_rows:,}','Across all categories'),('ACTIVE CATEGORIES',f'{sum(1 for c in CATEGORIES if stats_for(c)[0]):,} / 3','Categories containing data')]
    cc=st.columns(3)
    for c,(lab,val,note) in zip(cc,kpis):
        with c: st.markdown(f'<div class="metric-card"><div class="metric-label">{lab}</div><div class="metric-value">{val}</div><div class="metric-note">{note}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="section-title">Your workspaces · Select a category to open</div>',unsafe_allow_html=True)
    icons=['📥','📞','📦']; accents=['#5b9b91','#7895c5','#bd9364']
    cc=st.columns(3,gap='large')
    for c,cat,icon,accent in zip(cc,CATEGORIES,icons,accents):
        n,rows=stats_for(cat)
        with c:
            st.markdown(f'<div class="cat-card" style="border-top-color:{accent}"><div class="cat-label">{icon} DATA WORKSPACE</div><h3>{cat}</h3><div class="big">{rows:,}</div><div class="sub">TOTAL RECORDS</div><div class="sub" style="margin-top:8px">{n:,} individual files · compilation updated automatically</div></div>',unsafe_allow_html=True)
            if st.button(f'Open {cat}  →',key=f'open_{cat}',type='primary',use_container_width=True):
                st.session_state.active_category=cat; st.session_state.page='workspace'; st.rerun()
    st.caption('Each uploaded original file is retained separately. A combined category compilation is rebuilt automatically from the saved originals.')

elif st.session_state.page=='workspace':
    cat=st.session_state.active_category; n,rows=stats_for(cat); records=[x for x in load_index() if x.get('category')==cat]
    if st.button('← Back to categories'): st.session_state.page='home'; st.rerun()
    st.markdown(f'<div class="hero"><small>NEXGEN DATA HUB · CATEGORY WORKSPACE</small><h1>{cat}</h1><p>Upload original files, view the automatic compilation, then filter and export data for this category.</p></div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    with a: st.metric('Individual files',f'{n:,}')
    with b: st.metric('Total compiled records',f'{rows:,}')
    upload_tab,compile_tab,filter_tab=st.tabs(['⬆️ Upload files','🗂️ Files & compilation','🔎 Filter & download'])
    with upload_tab:
        st.subheader(f'Add files to {cat}')
        uploaded=st.file_uploader('Choose TXT, CSV, XLSX or XLS files',type=['txt','csv','xlsx','xls'],accept_multiple_files=True,key=f'uploader_{cat}')
        x,y=st.columns(2); delimiter=x.selectbox('TXT/CSV delimiter',['Auto-detect','Comma','Pipe (|)','Tab','Semicolon','Space(s)'],key=f'delim_{cat}'); header=y.checkbox('First row contains headers',True,key=f'header_{cat}')
        if uploaded and st.button(f'Save {len(uploaded)} file(s) to {cat}',type='primary',use_container_width=True,key=f'save_{cat}'):
            current=load_index(); saved=[]; errors=[]
            for f in uploaded:
                fid=uuid.uuid4().hex; stored=f'{fid}_{safe_name(f.name)}'; fp=FILES_DIR/stored; fp.write_bytes(f.getvalue())
                try:
                    df=unique_headers(read_file(fp,delimiter,header)); current.append({'id':fid,'original_name':f.name,'stored_name':stored,'category':cat,'uploaded_at':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'rows':len(df),'columns':len(df.columns),'delimiter':delimiter,'has_header':header}); saved.append(f'{f.name} · {len(df):,} records')
                except Exception as e: fp.unlink(missing_ok=True); errors.append(f'{f.name}: {e}')
            save_index(current)
            if saved: st.success(f'{len(saved)} original file(s) saved. Category compilation has been refreshed automatically.'); [st.write('✓',z) for z in saved]
            for e in errors: st.error(e)
            st.rerun()
    with compile_tab:
        records=[x for x in load_index() if x.get('category')==cat]; compiled=category_frame(cat,load_index())
        if records:
            st.subheader('Original uploaded files')
            st.dataframe(pd.DataFrame([{'File name':r['original_name'],'Uploaded':r['uploaded_at'],'Records':r['rows'],'Columns':r['columns']} for r in records]),use_container_width=True,hide_index=True)
            st.markdown('### Automatic compilation')
            st.success(f'{len(records)} original files combined · {len(compiled):,} total records · {len(compiled.columns)} columns')
            download_buttons_inline(compiled,f'{cat}_compiled',f'compiled_{cat}')
            st.dataframe(compiled.head(100),use_container_width=True,hide_index=True)
        else: st.info('No files yet. Open Upload files to add your first file.')
    with filter_tab: render_filter_tools(cat,records)

elif st.session_state.page=='library':
    st.markdown('<div class="hero"><small>NEXGEN DATA HUB</small><h1>All uploaded files</h1><p>Browse and remove original files from any category.</p></div>',unsafe_allow_html=True)
    records=load_index(); cat=st.selectbox('Filter category',['All categories']+CATEGORIES); shown=records if cat=='All categories' else [r for r in records if r.get('category')==cat]
    st.metric('Files shown',len(shown))
    if shown:
        st.dataframe(pd.DataFrame([{'File':r['original_name'],'Category':r['category'],'Uploaded':r['uploaded_at'],'Records':r['rows'],'Columns':r['columns']} for r in shown]),use_container_width=True,hide_index=True)
        choices={f"{r['original_name']} · {r['category']} · {r['uploaded_at']}":r['id'] for r in shown}; choice=st.selectbox('Select original file to delete',['— None —']+list(choices))
        if choice!='— None —' and st.button('Delete selected file',type='primary'):
            fid=choices[choice]; rec=next(r for r in records if r['id']==fid); (FILES_DIR/rec['stored_name']).unlink(missing_ok=True); save_index([r for r in records if r['id']!=fid]); st.success('File deleted; category compilation will update automatically.'); st.rerun()
    else: st.info('No files in this view.')

st.divider(); st.caption('Nexgen Data Hub · Category-first workspaces · Original files preserved · Automatic compilation')

import streamlit as st
import os
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="SESTEK IVR EDITOR", layout="wide")
st.title("SESTEK IVR EDITOR")
st.markdown("#### Select files below to start:")

base_folder = st.text_input("Select base folder (paste the path):")
excel_path = st.text_input("Full path to Excel file (no upload, just path):")

def get_folder_options(base_folder):
    try:
        subfolders = [f.name for f in Path(base_folder).iterdir() if f.is_dir()]
    except Exception:
        subfolders = []
    if "default" not in subfolders:
        subfolders.append("default")
    return ["All"] + sorted(subfolders)

def wav_exists(base_folder, folder, filename):
    folder = "default" if not folder or str(folder).lower() == "nan" else str(folder)
    wav_path = Path(base_folder) / folder / (str(filename) + ".wav")
    return wav_path.exists(), wav_path

def sfk_path_for(base_folder, folder, filename):
    folder = "default" if not folder or str(folder).lower() == "nan" else str(folder)
    return Path(base_folder) / folder / (str(filename) + ".sfk")

def save_df(df, excel_path):
    df.to_excel(excel_path, index=False, engine="openpyxl")

def reload_df(excel_path):
    df = pd.read_excel(excel_path, engine="openpyxl")
    for col in ['IsCompleted', 'IsDeleted']:
        if col not in df.columns:
            df[col] = False
        df[col] = df[col].map(lambda x: str(x).strip().lower() in ['1', 'true', 'yes'])
    return df.fillna("")

if base_folder and excel_path and Path(excel_path).exists():
    # Always reload fresh to show current state after every turn!
    df = reload_df(excel_path)
    
    # --- PLACE THIS HERE: Add word count column before any filtering! ---
    def count_words(s):
        if not isinstance(s, str):
            return 0
        return len([w for w in str(s).split() if w.strip()])
    df['WordCount'] = df['SestekText'].apply(count_words)
    # --------------------------------------------------------------------

    folder_options = get_folder_options(base_folder)
    selected_folder = st.selectbox("Select folder to focus", folder_options, key="folder_select")

    active = df[df["IsDeleted"] == False].copy()

    def folder_match(row, folder):
        if folder == "default":
            return not row.get("FolderName") or str(row.get("FolderName")).lower() == "nan"
        return str(row.get("FolderName")) == folder

    if selected_folder == "All":
        folder_df = active
    else:
        folder_df = active[active.apply(lambda r: folder_match(r, selected_folder), axis=1)]

    total_files = len(df)
    completed = df["IsCompleted"].sum()
    not_deleted_files = df[df["IsDeleted"] == False]
    total_active = len(not_deleted_files)
    completed_active = not_deleted_files["IsCompleted"].sum()
    st.markdown(f"#### Total Progress: {completed_active}/{total_active} completed")
    st.progress(completed_active / total_active if total_active else 1.0)

    folder_total = len(folder_df)
    folder_completed = folder_df["IsCompleted"].sum()
    st.markdown(f"**{selected_folder} Progress:** {folder_completed}/{folder_total}")
    st.progress(folder_completed / folder_total if folder_total else 1.0)

    # --- Word Count Progress Section (remains unchanged now) ---
    # Overall
    not_deleted = df[df["IsDeleted"] == False]
    total_words = not_deleted['WordCount'].sum()
    completed_words = not_deleted[not_deleted["IsCompleted"] == True]['WordCount'].sum()
    deleted_words = df[df["IsDeleted"] == True]['WordCount'].sum()
    progressed_words = completed_words + deleted_words
    total_words_including_deleted = total_words + deleted_words

    st.markdown(
        f"**Total word progress:** {progressed_words:,} / {total_words_including_deleted:,} words "
        f"({progressed_words/total_words_including_deleted*100 if total_words_including_deleted else 0:.1f}%)"
    )
    st.progress(progressed_words/total_words_including_deleted if total_words_including_deleted else 1.0)

    # Per folder
    folder_word_total = folder_df['WordCount'].sum()
    folder_completed_words = folder_df[folder_df["IsCompleted"] == True]['WordCount'].sum()
    folder_deleted_words = df[(df["IsDeleted"] == True) & (df.apply(lambda r: folder_match(r, selected_folder), axis=1))]['WordCount'].sum()
    folder_progressed_words = folder_completed_words + folder_deleted_words
    folder_total_words = folder_word_total + folder_deleted_words

    st.markdown(
        f"**{selected_folder} word progress:** {folder_progressed_words:,} / {folder_total_words:,} words "
        f"({folder_progressed_words/folder_total_words*100 if folder_total_words else 0:.1f}%)"
    )
    st.progress(folder_progressed_words/folder_total_words if folder_total_words else 1.0)


    # NAVIGATION
    if folder_total > 0:
        folder_indices = folder_df.index.tolist()
        # Navigation session
        if ("nav_index" not in st.session_state or
            st.session_state.get("last_folder") != selected_folder or
            st.session_state.nav_index not in folder_indices):
            incompletes = folder_df[folder_df['IsCompleted'] == False]
            st.session_state.nav_index = incompletes.index[0] if not incompletes.empty else folder_indices[0]
            st.session_state.last_folder = selected_folder

        idx_pos = folder_indices.index(st.session_state.nav_index)
        nav_cols = st.columns([1,1,6,1,1])
        with nav_cols[0]:
            if st.button("⬅️ Back", key="back_btn") and idx_pos > 0:
                st.session_state.nav_index = folder_indices[idx_pos-1]
        with nav_cols[-1]:
            if st.button("Next ➡️", key="next_btn") and idx_pos < len(folder_indices)-1:
                st.session_state.nav_index = folder_indices[idx_pos+1]
        with nav_cols[2]:
            st.markdown(f"<center><b>{idx_pos+1} / {folder_total}</b></center>", unsafe_allow_html=True)

        # Current file info
        i = st.session_state.nav_index
        row = df.loc[i]
        folder = row.get('FolderName', "")
        display_folder = "default" if not folder or str(folder).lower() == "nan" else str(folder)
        filename = str(row["Filename"])
        sestek_text = row.get("SestekText", "")
        sestek_comment = row.get("Sestek Comment", "")

        st.markdown("---")
        st.subheader(f"Editing: {display_folder}/{filename}.wav")
        sestek_text_in = st.text_area("Text", sestek_text, key=f"text_{i}")
        sestek_comment_in = st.text_area("Comment", sestek_comment, key=f"comm_{i}")

        exists, fpath = wav_exists(base_folder, folder, filename)
        if not exists:
            st.warning("File does not exist in the selected folder. (Not marked as deleted)")

        # Buttons
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            if st.button("Edit (Ctrl+Enter)"):
                if exists:
                    os.startfile(str(fpath))
                else:
                    st.error("File does not exist!")

        with bc2:
            if st.button("Delete"):
                if exists:
                    try:
                        os.remove(fpath)
                    except Exception as e:
                        st.warning(f"Error deleting file: {e}")
                df.at[i, "IsDeleted"] = True
                save_df(df, excel_path)
                st.success("Deleted. File and Excel updated.")
                st.session_state.nav_index = folder_indices[min(idx_pos+1, len(folder_indices)-1)]
                st.rerun()

        with bc3:
            if st.button("Save"):
                df.at[i, "SestekText"] = sestek_text_in
                df.at[i, "Sestek Comment"] = sestek_comment_in
                df.at[i, "IsCompleted"] = True
                sfkfile = sfk_path_for(base_folder, folder, filename)
                if sfkfile.exists():
                    try:
                        os.remove(sfkfile)
                    except Exception as e:
                        st.warning(f"Could not delete .sfk: {e}")
                save_df(df, excel_path)
                st.success("Changes saved!")
                if idx_pos < len(folder_indices)-1:
                    st.session_state.nav_index = folder_indices[idx_pos+1]
                st.rerun()

    st.info(f"All changes are immediately written to: `{excel_path}`.")

else:
    st.info("Please select both a base folder and a valid Excel file path.")

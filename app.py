import base64
import io
import os
import shutil
import zipfile
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="IVR projects", layout="wide")
st.set_page_config(page_title="IVR Wave Editor", layout="wide")

DATA_ROOT = Path("data")
PROJECT_ROOT = DATA_ROOT / "projects"
PROJECT_ROOT.mkdir(parents=True, exist_ok=True)


def ensure_project(project_name: str) -> Path:
    project_dir = PROJECT_ROOT / project_name
    raw_dir = project_dir / "raw"
    corrected_dir = project_dir / "corrected"
    bad_input_dir = project_dir / "bad_input"
    for path in (raw_dir, corrected_dir, bad_input_dir):
        path.mkdir(parents=True, exist_ok=True)
    return project_dir


def ingest_zip(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile, project_name: str) -> Path:
    project_dir = ensure_project(project_name)
    raw_dir = project_dir / "raw"

    with zipfile.ZipFile(uploaded_file) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        wav_members = {}
        txt_members = {}
        for member in members:
            suffix = Path(member.filename).suffix.lower()
            base = Path(member.filename).stem
            if suffix == ".wav":
                wav_members[base] = member
            if suffix == ".txt":
                txt_members[base] = member

        for base, wav_member in wav_members.items():
            target_wav = raw_dir / f"{base}.wav"
            with zf.open(wav_member) as source_fp, open(target_wav, "wb") as target_fp:
                shutil.copyfileobj(source_fp, target_fp)
            if base in txt_members:
                txt_member = txt_members[base]
                target_txt = raw_dir / f"{base}.txt"
                with zf.open(txt_member) as source_fp, open(target_txt, "wb") as target_fp:
                    shutil.copyfileobj(source_fp, target_fp)

    return project_dir


def export_project_zip(project_name: str) -> bytes:
    project_dir = PROJECT_ROOT / project_name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in project_dir.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(project_dir))
    buffer.seek(0)
    return buffer.read()


def save_zip_to_project(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile, project_name: str) -> Path:
    project_dir = PROJECT_ROOT / project_name
    source_dir = project_dir / "source"
    corrected_dir = project_dir / "corrected"
    bad_input_dir = project_dir / "bad_input"
    for path in (source_dir, corrected_dir, bad_input_dir):
        path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(uploaded_file) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target_path = source_dir / Path(member.filename).name
            if target_path.suffix.lower() == ".wav":
                with zf.open(member) as source_fp, open(target_path, "wb") as target_fp:
                    shutil.copyfileobj(source_fp, target_fp)
    return project_dir


def list_projects():
    return sorted([p.name for p in PROJECT_ROOT.iterdir() if p.is_dir()])


def load_audio_b64(path: Path) -> str:
    audio_bytes = path.read_bytes()
    return base64.b64encode(audio_bytes).decode("utf-8")


def write_bytes_to_file(target: Path, raw_bytes: bytes):
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as fp:
        fp.write(raw_bytes)


def copy_original_to_bad_input(source_path: Path, bad_dir: Path):
    bad_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, bad_dir / source_path.name)


def delete_project(project_name: str):
    project_dir = PROJECT_ROOT / project_name
    if project_dir.exists():
        shutil.rmtree(project_dir)


def get_project_state(project_name: str):
    project_dir = ensure_project(project_name)
    raw_dir = project_dir / "raw"
    corrected_dir = project_dir / "corrected"
    bad_dir = project_dir / "bad_input"
    raw_files = sorted(raw_dir.glob("*.wav"))
    processed = {
        p.name for p in corrected_dir.glob("*.wav")
    } | {p.name for p in bad_dir.glob("*.wav")}
    return project_dir, raw_dir, corrected_dir, bad_dir, raw_files, processed


def next_file_name(raw_files, current_name):
    names = [p.name for p in raw_files]
    if current_name in names:
        pos = names.index(current_name)
        if pos < len(names) - 1:
            return names[pos + 1]
    return None


st.title("IVR projects")
st.caption("Manage IVR audio projects, then launch the embedded WAV editor to clean recordings.")

st.subheader("Manage projects")
project_cols = st.columns([3, 1, 1])
project_cols[0].markdown("**Project**")
project_cols[1].markdown("**Export**")
project_cols[2].markdown("**Delete**")

projects = list_projects()
pending_delete = st.session_state.get("pending_delete")
selected_project = st.selectbox("Choose a project to edit", options=["--"] + projects, index=0)

for name in projects:
    col_name, col_export, col_delete = st.columns([3, 1, 1])
    col_name.write(name)

    if col_export.button("Export", key=f"export_{name}"):
        zip_bytes = export_project_zip(name)
        col_export.download_button(
            label="Download",
            data=zip_bytes,
            file_name=f"{name}.zip",
            mime="application/zip",
            key=f"export_file_{name}",
        )

    delete_clicked = col_delete.button("Delete", key=f"delete_{name}")
    if delete_clicked:
        st.session_state["pending_delete"] = name
        pending_delete = name

    if pending_delete == name:
        confirm = st.text_input(
            f"Type DELETE to remove '{name}'", key=f"confirm_{name}"
        )
        if st.button(f"Confirm delete {name}", key=f"confirm_btn_{name}"):
            if confirm.strip().upper() == "DELETE":
                delete_project(name)
                st.success(f"Deleted project {name}.")
                st.session_state.pop("pending_delete", None)
                st.experimental_rerun()
            else:
                st.warning("Confirmation text mismatch. Project not deleted.")

st.markdown("---")

st.subheader("Add project")
upload_col, name_col = st.columns([2, 1])
uploaded_zip = upload_col.file_uploader("Upload project zip", type=["zip"], key="proj_zip")
default_name = uploaded_zip.name.replace(".zip", "") if uploaded_zip else ""
project_name_input = name_col.text_input("Project name", value=default_name)

if uploaded_zip and project_name_input:
    project_dir = ingest_zip(uploaded_zip, project_name_input)
    st.success(f"Added project at {project_dir}")
    st.experimental_rerun()

st.markdown("---")

if selected_project != "--":
    project_dir, raw_dir, corrected_dir, bad_dir, raw_files, processed_files = get_project_state(selected_project)

    st.subheader("Wav Editor")
    if not raw_files:
        st.info("This project has no WAV files yet.")
    else:
        nav_key = f"nav_{selected_project}"
        default_name = next((p.name for p in raw_files if p.name not in processed_files), raw_files[0].name)
        current_name = st.session_state.get(nav_key, default_name)
        if current_name not in [p.name for p in raw_files]:
            current_name = default_name
            st.session_state[nav_key] = current_name

        total = len(raw_files)
        completed = len(processed_files & {p.name for p in raw_files})
        current_idx = [p.name for p in raw_files].index(current_name)

        nav_cols = st.columns([1, 1, 5, 2])
        if nav_cols[0].button("⬅️ Back", disabled=current_idx == 0):
            st.session_state[nav_key] = raw_files[current_idx - 1].name
            st.experimental_rerun()
        if nav_cols[1].button("Next ➡️", disabled=current_idx == total - 1):
            st.session_state[nav_key] = raw_files[current_idx + 1].name
            st.experimental_rerun()
        nav_cols[2].markdown(
            f"**{current_name}** — {current_idx + 1}/{total} files"
        )
        percent_complete = (completed / total * 100) if total else 0
        nav_cols[3].markdown(f"{percent_complete:.1f}% completed")
        st.progress(percent_complete / 100 if total else 0)

        selected_file = raw_dir / current_name
        audio_b64 = load_audio_b64(selected_file)
        component = st.components.v1.declare_component(
            "wave_editor",
            path=str(Path(__file__).parent / "wave_editor"),
        )

        editor_value = component(
            key=f"editor_{selected_file.name}",
            audioBase64=audio_b64,
            fileName=selected_file.name,
        )

        edited_bytes = None
        bad_flag = False
        if editor_value:
            if editor_value.get("audioBase64"):
                edited_bytes = base64.b64decode(editor_value["audioBase64"])
            bad_flag = editor_value.get("badInput", False)

        st.markdown("---")
        c1, c2, c3 = st.columns(3)

        def move_next():
            nxt = next_file_name(raw_files, current_name)
            if nxt:
                st.session_state[nav_key] = nxt
            st.experimental_rerun()

        with c1:
            if st.button("Save Corrected"):
                data_to_save = edited_bytes or selected_file.read_bytes()
                write_bytes_to_file(corrected_dir / selected_file.name, data_to_save)
                st.success("Saved to corrected folder.")
                move_next()
        with c2:
            if st.button("Mark as Bad Input"):
                copy_original_to_bad_input(selected_file, bad_dir)
                st.warning("Original copied to bad_input folder.")
                move_next()
        with c3:
            if st.button("Skip"):
                move_next()

        if bad_flag:
            st.info("Editor flagged this audio as bad input. Use the button above to record it.")
else:
    st.info("Select or add a project to start editing WAV files.")
st.title("SESTEK IVR Wave Editor")
st.markdown("Upload IVR zip archives and edit audio with a modern waveform editor.")

st.sidebar.header("Project")
existing_projects = list_projects()
project_name = st.sidebar.text_input("Project name", value=existing_projects[0] if existing_projects else "")
uploaded_zip = st.sidebar.file_uploader("Upload project zip", type=["zip"])

if uploaded_zip and project_name:
    project_dir = save_zip_to_project(uploaded_zip, project_name)
    st.sidebar.success(f"Uploaded to {project_dir}")

if project_name and (PROJECT_ROOT / project_name).exists():
    project_dir = PROJECT_ROOT / project_name
    source_dir = project_dir / "source"
    corrected_dir = project_dir / "corrected"
    bad_dir = project_dir / "bad_input"

    wav_files = sorted(source_dir.glob("*.wav"))
    if wav_files:
        st.sidebar.subheader("Files")
        file_names = [p.name for p in wav_files]
        idx = st.sidebar.selectbox("Choose a file", range(len(file_names)), format_func=lambda i: file_names[i])
        selected_file = wav_files[idx]
    else:
        selected_file = None
        st.info("No wav files in this project yet. Upload a zip to get started.")
else:
    selected_file = None
    if not project_name:
        st.info("Enter a project name to begin.")

if selected_file:
    st.subheader(f"Editing: {selected_file.name}")
    audio_b64 = load_audio_b64(selected_file)
    component = st.components.v1.declare_component(
        "wave_editor",
        path=str(Path(__file__).parent / "wave_editor"),
    )

    editor_value = component(
        key=f"editor_{selected_file.name}",
        audioBase64=audio_b64,
        fileName=selected_file.name,
    )

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    def next_index(current):
        files = sorted((project_dir / "source").glob("*.wav"))
        names = [p.name for p in files]
        try:
            pos = names.index(current)
            return names[min(len(names) - 1, pos + 1)]
        except ValueError:
            return None

    edited_bytes = None
    if editor_value and editor_value.get("audioBase64"):
        edited_bytes = base64.b64decode(editor_value["audioBase64"])

    with col1:
        if st.button("Save Corrected", disabled=edited_bytes is None):
            if edited_bytes:
                write_bytes_to_file(corrected_dir / selected_file.name, edited_bytes)
                st.success("Saved edited audio to corrected folder.")
    with col2:
        if st.button("Mark as Bad Input"):
            copy_original_to_bad_input(selected_file, bad_dir)
            st.warning("Original copied to bad_input folder.")
    with col3:
        if st.button("Skip"):
            st.session_state[f"editor_{selected_file.name}"] = None
            nxt = next_index(selected_file.name)
            if nxt:
                st.experimental_set_query_params(file=nxt)
            st.info("Skipped. Use the file picker to continue.")

else:
    st.markdown("### Upload a zip and select a project to start editing.")

import base64
import io
import os
import shutil
import zipfile
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="IVR Wave Editor", layout="wide")

DATA_ROOT = Path("data")
PROJECT_ROOT = DATA_ROOT / "projects"
PROJECT_ROOT.mkdir(parents=True, exist_ok=True)


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

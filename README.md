# IVR Wave Editor

Modern Streamlit-based IVR editing tool with a built-in web waveform editor powered by WaveSurfer.js.

## Features
- Upload IVR zip archives and automatically unpack paired `.wav`/`.txt` files into project folders.
- Manage projects with **raw**, **corrected**, and **bad_input** subfolders.
- Real-time waveform editor (React/JS) supporting selection, delete, trim, insert silence, and bad-input tagging with keyboard shortcuts.
- Export edited audio back to Streamlit for saving into the corrected folder.
- Quick actions for marking original audio as bad input or skipping to the next file.

## Getting Started
1. Install dependencies: `pip install -r requirements.txt`.
2. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```
3. Use the **IVR projects** page to import a zip, export/delete projects, and launch the WAV editor.


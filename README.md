# Video Contact Sheet

Generate contact sheet preview images for multiple videos with a simple Windows interface.

## Features

- Select one folder or multiple individual video files.
- Optionally include videos from subfolders.
- Choose exactly where generated images are saved.
- Track progress and cancel videos that have not started yet.
- Process up to four videos in parallel.
- Review a generation report in the selected output folder.

## Run From Source

```powershell
py -m pip install -r requirements.txt
py .\main.py
```

Choose the video input and output folder in the app, then select **Generate**. Contact sheets are saved as JPEG files, and `generation_report.txt` contains the run summary.

## Build the Windows Executable

```powershell
py -m pip install -r requirements.txt
py -m PyInstaller --clean --noconfirm --onefile --windowed --name video-contact-sheet .\main.py
```

The executable is created at:

```text
dist/video-contact-sheet.exe
```

End users only need the executable. Python and the project dependencies are not required.

## Download

Windows users can download the existing prebuilt executable here:

[video-contact-sheet.exe](https://drive.google.com/file/d/10fkW-TlA1aRykcu9S89yvwxfMvky-bzO/view?usp=drive_link)

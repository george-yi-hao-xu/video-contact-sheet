# video-contact-sheet

批量为当前文件夹下的视频生成 contact sheet 预览图。  
Generate contact sheet preview images for videos in the current folder.

## 运行源码 / Run From Source

```powershell
py -m pip install -r requirements.txt
py .\gen_video_sheet.py
```

生成的图片会放在 / Images will be saved to:

```text
screenshots_gened/
```

## 打包成 exe / Build exe

```powershell
py -m pip install -r requirements.txt
py -m PyInstaller --onefile --name video-contact-sheet .\gen_video_sheet.py
```

打包完成后，exe 在 / The built exe will be at:

```text
dist/video-contact-sheet.exe
```

普通用户只需要运行 exe，不需要安装 Python 或依赖库。  
End users only need the exe. Python and dependencies are not required.

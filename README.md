# video-contact-sheet

批量为当前文件夹下的视频生成 contact sheet 预览图。

## 直接运行源码

```powershell
py -m pip install opencv-python Pillow
py .\gen_video_sheet.py
```

生成的图片会放在：

```text
screenshots_gened/
```

## 打包成 exe

先安装打包工具：

```powershell
py -m pip install pyinstaller
```

然后打包：

```powershell
py -m PyInstaller --onefile --name video-contact-sheet .\gen_video_sheet.py
```

打包完成后，exe 在：

```text
dist/video-contact-sheet.exe
```

把这个 exe 放到视频文件夹里运行即可。

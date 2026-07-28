# py -m pip install -r requirements.txt

from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from format_util import format_duration, format_file_size, format_output_name

# 简单配置：需要调整时只改这里
COLS = 10
ROWS = 5
THUMB_WIDTH = 240
HEADER_HEIGHT = 96
HEADER_PADDING = 18

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
    ".mts", ".m2ts", ".ts",
}


def resize_frame(frame, width, height):
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(frame)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def load_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]

    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue

    return ImageFont.load_default()


def fit_text(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return text

    suffix = "..."
    low = 0
    high = len(text)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = text[:middle] + suffix
        if draw.textlength(candidate, font=font) <= max_width:
            low = middle
        else:
            high = middle - 1

    return text[:low] + suffix


def draw_video_info(sheet, video_path, frame_count, source_width, source_height, fps):
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(28, bold=True)
    info_font = load_font(20)
    sheet_width = sheet.width
    max_text_width = sheet_width - HEADER_PADDING * 2

    duration = frame_count / fps if fps > 0 else 0
    try:
        file_size = format_file_size(video_path.stat().st_size)
    except OSError:
        file_size = "未知大小"

    fps_text = f"{fps:.2f} fps" if fps > 0 else "未知 fps"
    title = fit_text(draw, video_path.name, title_font, max_text_width)
    info = fit_text(
        draw,
        (
            f"{source_width}x{source_height} | "
            f"{format_duration(duration)} | "
            f"{fps_text} | "
            f"{frame_count} frames | "
            f"{file_size}"
        ),
        info_font,
        max_text_width,
    )

    draw.rectangle((0, 0, sheet_width, HEADER_HEIGHT), fill=(18, 18, 18))
    draw.text((HEADER_PADDING, 18), title, font=title_font, fill=(245, 245, 245))
    draw.text((HEADER_PADDING, 57), info, font=info_font, fill=(185, 185, 185))


def make_contact_sheet(video_path, output_path):
    video = cv2.VideoCapture(str(video_path))

    if not video.isOpened():
        print(f"无法打开 / Cannot open: {video_path}")
        return

    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    source_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(video.get(cv2.CAP_PROP_FPS))

    if frame_count <= 0 or source_width <= 0 or source_height <= 0:
        print(f"无法读取视频信息 / Cannot read video info: {video_path}")
        video.release()
        return

    total = COLS * ROWS
    thumb_height = round(THUMB_WIDTH * source_height / source_width)

    sheet = Image.new(
        "RGB",
        (COLS * THUMB_WIDTH, HEADER_HEIGHT + ROWS * thumb_height),
        "black",
    )
    draw_video_info(sheet, video_path, frame_count, source_width, source_height, fps)

    # 均匀抽取 50 帧，并稍微避开开头和结尾
    start_fr_idx = int(frame_count * 0.02)
    end_fr_idx = int(frame_count * 0.98)

    for index in range(total):
        curr_frame_index = round(
            start_fr_idx + index * (end_fr_idx - start_fr_idx) / max(total - 1, 1)
        )

        video.set(cv2.CAP_PROP_POS_FRAMES, curr_frame_index)
        success, frame = video.read()

        if not success:
            continue

        thumbnail = resize_frame(frame, THUMB_WIDTH, thumb_height)

        x = (index % COLS) * THUMB_WIDTH
        y = HEADER_HEIGHT + (index // COLS) * thumb_height
        sheet.paste(thumbnail, (x, y))

    video.release()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)

    print(f"已生成 / Generated: {output_path}")


def get_output_path(current_folder, output_folder, video_path):
    relative_path = video_path.relative_to(current_folder)
    output_name = format_output_name(relative_path)
    return output_folder / f"{output_name}.jpg"


def main():
    current_folder = Path.cwd()
    output_folder = current_folder / "screenshots_gened"

    videos = [
        path
        for path in current_folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
        and output_folder not in path.parents #defensive: in case a video is in output folder
    ]

    if not videos:
        print("当前目录下没有找到视频文件。/ No video files found in current folder.")
        return

    print(f"找到 {len(videos)} 个视频。/ Found {len(videos)} video(s).")

    for video_path in videos:
        output_path = get_output_path(current_folder, output_folder, video_path)
        make_contact_sheet(video_path, output_path)

    print("全部完成。/ All done.")


if __name__ == "__main__":
    main()

# py -m pip install -r requirements.txt

from datetime import datetime
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from .format_util import format_duration, format_file_size
from .path_util import find_video_paths, get_output_path

THUMB_WIDTH = 240
HEADER_HEIGHT = 96
HEADER_PADDING = 18
REPORT_FILENAME = "generation_report.txt"


def get_sheet_grid(duration):
    if duration <= 0:
        return 6, 5

    if duration < 15 * 60:
        return 4, 3

    if duration <= 60 * 60:
        return 6, 5

    return 8, 7


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
        file_size = "unknown size"

    fps_text = f"{fps:.2f} fps" if fps > 0 else "unknown fps"
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
        print(f"Cannot open: {video_path}")
        return

    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    source_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(video.get(cv2.CAP_PROP_FPS))

    if frame_count <= 0 or source_width <= 0 or source_height <= 0:
        print(f"Cannot read video info: {video_path}")
        video.release()
        return

    duration = frame_count / fps if fps > 0 else 0
    cols, rows = get_sheet_grid(duration)
    total = cols * rows
    thumb_height = round(THUMB_WIDTH * source_height / source_width)

    sheet = Image.new(
        "RGB",
        (cols * THUMB_WIDTH, HEADER_HEIGHT + rows * thumb_height),
        "black",
    )
    draw_video_info(sheet, video_path, frame_count, source_width, source_height, fps)

    # Sample frames evenly and avoid the very beginning/end.
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

        x = (index % cols) * THUMB_WIDTH
        y = HEADER_HEIGHT + (index // cols) * thumb_height
        sheet.paste(thumbnail, (x, y))

    video.release()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)

    print(f"Generated: {output_path}")


def write_generation_report(current_folder, output_folder, videos):
    output_folder.mkdir(parents=True, exist_ok=True)
    report_path = output_folder / REPORT_FILENAME
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    lines = [
        "Video Contact Sheet Generation Report",
        f"Generated at: {generated_at}",
        f"Video count: {len(videos)}",
        "",
        "Videos:",
    ]

    if videos:
        lines.extend(
            f"- {video_path.relative_to(current_folder)}" for video_path in videos
        )
    else:
        lines.append("- No video files found.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written: {report_path}")


def main():
    current_folder = Path.cwd()
    output_folder = current_folder / "screenshots_gened"

    videos = find_video_paths(current_folder, output_folder)
    write_generation_report(current_folder, output_folder, videos)

    if not videos:
        print("No video files found in current folder.")
        return

    print(f"Found {len(videos)} video(s).")

    for video_path in videos:
        output_path = get_output_path(current_folder, output_folder, video_path)
        make_contact_sheet(video_path, output_path)

    print("All done.")

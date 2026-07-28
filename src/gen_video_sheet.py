# py -m pip install -r requirements.txt

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from time import perf_counter

import cv2
from PIL import Image, ImageDraw, ImageFont

from .format_util import format_duration, format_file_size, format_timestamp
from .path_util import find_video_paths, get_output_path

THUMB_WIDTH = 240
HEADER_HEIGHT = 96
HEADER_PADDING = 18
THUMB_GAP = 2
TIMESTAMP_FONT_SIZE = 18
TIMESTAMP_MARGIN = 4
TIMESTAMP_PADDING_X = 5
TIMESTAMP_PADDING_Y = 3
TIMESTAMP_BG = (70, 70, 70, 180)
REPORT_FILENAME = "generation_report.txt"
MAX_WORKERS = min(4, os.cpu_count() or 1)


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


def add_thumbnail_timestamp(thumbnail, timestamp):
    base = thumbnail.convert("RGBA")
    overlay = Image.new("RGBA", thumbnail.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(TIMESTAMP_FONT_SIZE, bold=True)
    bbox = draw.textbbox((0, 0), timestamp, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    box_width = text_width + TIMESTAMP_PADDING_X * 2
    box_height = text_height + TIMESTAMP_PADDING_Y * 2
    box_x = TIMESTAMP_MARGIN
    box_y = thumbnail.height - box_height - TIMESTAMP_MARGIN

    draw.rectangle(
        (box_x, box_y, box_x + box_width, box_y + box_height),
        fill=TIMESTAMP_BG,
    )
    draw.text(
        (
            box_x + TIMESTAMP_PADDING_X - bbox[0],
            box_y + TIMESTAMP_PADDING_Y - bbox[1],
        ),
        timestamp,
        font=font,
        fill=(255, 255, 255, 255),
    )

    return Image.alpha_composite(base, overlay).convert("RGB")


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
        return False, f"Cannot open: {video_path}"

    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    source_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(video.get(cv2.CAP_PROP_FPS))

    if frame_count <= 0 or source_width <= 0 or source_height <= 0:
        video.release()
        return False, f"Cannot read video info: {video_path}"

    duration = frame_count / fps if fps > 0 else 0
    cols, rows = get_sheet_grid(duration)
    total = cols * rows
    thumb_height = round(THUMB_WIDTH * source_height / source_width)

    sheet = Image.new(
        "RGB",
        (
            cols * THUMB_WIDTH + (cols + 1) * THUMB_GAP,
            HEADER_HEIGHT + rows * thumb_height + (rows + 1) * THUMB_GAP,
        ),
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
        timestamp = format_timestamp(curr_frame_index / fps if fps > 0 else None)
        thumbnail = add_thumbnail_timestamp(thumbnail, timestamp)

        x = THUMB_GAP + (index % cols) * (THUMB_WIDTH + THUMB_GAP)
        y = HEADER_HEIGHT + THUMB_GAP + (index // cols) * (thumb_height + THUMB_GAP)
        sheet.paste(thumbnail, (x, y))

    video.release()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)

    return True, f"Generated: {output_path}"


def process_video(args):
    current_folder, output_folder, video_path = args

    try:
        cv2.setNumThreads(1)
    except AttributeError:
        pass

    try:
        output_path = get_output_path(current_folder, output_folder, video_path)
        return make_contact_sheet(video_path, output_path)
    except Exception as exc:
        return False, f"Failed: {video_path} ({exc})"


def get_worker_count(task_count):
    return max(1, min(MAX_WORKERS, task_count))


def run_tasks_sequentially(tasks):
    success_count = 0

    for task in tasks:
        success, message = process_video(task)
        if success:
            success_count += 1
        print(message)

    return success_count


def generate_contact_sheets(current_folder, output_folder, videos):
    worker_count = get_worker_count(len(videos))
    print(f"Using {worker_count} worker(s).")

    tasks = [(current_folder, output_folder, video_path) for video_path in videos]
    success_count = 0

    if worker_count == 1:
        return run_tasks_sequentially(tasks)

    try:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(process_video, task) for task in tasks]

            for future in as_completed(futures):
                success, message = future.result()
                if success:
                    success_count += 1
                print(message)
    except OSError as exc:
        print(f"Multiprocessing unavailable ({exc}); falling back to sequential mode.")
        return run_tasks_sequentially(tasks)


    return success_count


def format_elapsed(seconds):
    seconds = max(0, round(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def write_generation_report(
    output_folder,
    completed_at,
    elapsed_seconds,
    total_count,
    success_count,
):
    output_folder.mkdir(parents=True, exist_ok=True)
    report_path = output_folder / REPORT_FILENAME
    failure_count = total_count - success_count

    lines = [
        "Video Contact Sheet Generation Report",
        f"Completed at: {completed_at.isoformat(timespec='seconds')}",
        f"Elapsed time: {format_elapsed(elapsed_seconds)}",
        f"Total videos: {total_count}",
        f"Succeeded: {success_count}",
        f"Failed: {failure_count}",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written: {report_path}")


def main():
    started_at = perf_counter()
    current_folder = Path.cwd()
    output_folder = current_folder / "screenshots_gened"

    videos = find_video_paths(current_folder, output_folder)

    if not videos:
        print("No video files found in current folder.")
        completed_at = datetime.now().astimezone()
        elapsed_seconds = perf_counter() - started_at
        write_generation_report(output_folder, completed_at, elapsed_seconds, 0, 0)
        return

    print(f"Found {len(videos)} video(s).")

    success_count = generate_contact_sheets(current_folder, output_folder, videos)
    completed_at = datetime.now().astimezone()
    elapsed_seconds = perf_counter() - started_at
    write_generation_report(
        output_folder,
        completed_at,
        elapsed_seconds,
        len(videos),
        success_count,
    )

    print(f"All done. Generated {success_count}/{len(videos)} sheet(s).")

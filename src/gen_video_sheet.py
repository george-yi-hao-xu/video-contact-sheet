# py -m pip install -r requirements.txt

import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass

import cv2
from PIL import Image, ImageDraw, ImageFont

from .format_util import format_duration, format_file_size, format_timestamp

THUMB_WIDTH = 240
HEADER_HEIGHT = 96
HEADER_PADDING = 18
THUMB_GAP = 2
TIMESTAMP_FONT_SIZE = 18
TIMESTAMP_MARGIN = 4
TIMESTAMP_PADDING_X = 5
TIMESTAMP_PADDING_Y = 3
TIMESTAMP_BG = (70, 70, 70, 180)
MAX_WORKERS = min(4, os.cpu_count() or 1)


@dataclass(frozen=True)
class GenerationResult:
    total_count: int
    success_count: int
    failure_count: int
    canceled_count: int
    failed_video_names: tuple[str, ...] = ()


def get_sheet_grid(duration):
    """Choose the thumbnail grid size based on video duration in seconds."""
    if duration <= 0:
        return 6, 5

    if duration < 15 * 60:
        return 4, 3

    if duration <= 60 * 60:
        return 6, 5

    return 8, 7


def resize_frame(frame, width, height):
    """Convert an OpenCV BGR frame to RGB and resize it as a PIL image."""
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(frame)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def load_font(size, bold=False):
    """Load a Windows font at the requested size, falling back safely."""
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
    """Shorten text with an ellipsis until it fits within the given width."""
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
    """Draw a readable timestamp badge in the lower-left of a thumbnail."""
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
    """Draw the video name and technical details in the sheet header."""
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
    """Create and save one contact sheet from evenly sampled video frames.

    The function returns a success flag and a user-facing result message rather
    than raising errors for videos that cannot be opened or inspected.
    """
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

    start_frame_index = int(frame_count * 0.02)
    end_frame_index = int(frame_count * 0.98)

    for index in range(total):
        current_frame_index = round(
            start_frame_index
            + index * (end_frame_index - start_frame_index) / max(total - 1, 1)
        )

        video.set(cv2.CAP_PROP_POS_FRAMES, current_frame_index)
        success, frame = video.read()

        if not success:
            continue

        thumbnail = resize_frame(frame, THUMB_WIDTH, thumb_height)
        timestamp = format_timestamp(current_frame_index / fps if fps > 0 else None)
        thumbnail = add_thumbnail_timestamp(thumbnail, timestamp)

        x = THUMB_GAP + (index % cols) * (THUMB_WIDTH + THUMB_GAP)
        y = HEADER_HEIGHT + THUMB_GAP + (index // cols) * (thumb_height + THUMB_GAP)
        sheet.paste(thumbnail, (x, y))

    video.release()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)

    return True, f"Generated: {output_path}"


def process_video(task):
    """Process one source/output task and convert unexpected errors to failures."""
    video_path, output_path = task

    try:
        cv2.setNumThreads(1)
    except AttributeError:
        pass

    try:
        return make_contact_sheet(video_path, output_path)
    except Exception as exc:
        return False, f"Failed: {video_path} ({exc})"


def get_worker_count(task_count):
    """Choose a safe worker count without exceeding tasks or the global limit."""
    return max(1, min(MAX_WORKERS, task_count))


def _report_progress(progress_callback, completed_count, total_count, success, message):
    """Send a progress update when the caller supplied a callback."""
    if progress_callback:
        progress_callback(completed_count, total_count, success, message)


def _generate_sequentially(tasks, cancel_event, progress_callback):
    """Process tasks one at a time until all finish or cancellation is requested."""
    success_count = 0
    failure_count = 0
    completed_count = 0
    failed_video_names = []

    for task in tasks:
        if cancel_event.is_set():
            break

        success, message = process_video(task)
        completed_count += 1
        if success:
            success_count += 1
        else:
            failure_count += 1
            failed_video_names.append(task[0].name)
        _report_progress(
            progress_callback,
            completed_count,
            len(tasks),
            success,
            message,
        )

    return GenerationResult(
        len(tasks),
        success_count,
        failure_count,
        len(tasks) - completed_count,
        tuple(failed_video_names),
    )


def generate_contact_sheets(tasks, cancel_event, progress_callback=None):
    """Generate contact sheets with bounded parallelism and safe cancellation.

    Only enough tasks to fill the worker pool are submitted at once. After a
    cancellation request, active tasks finish but no additional tasks start.
    """
    tasks = list(tasks)
    if not tasks:
        return GenerationResult(0, 0, 0, 0)

    worker_count = get_worker_count(len(tasks))
    if worker_count == 1:
        return _generate_sequentially(tasks, cancel_event, progress_callback)

    success_count = 0
    failure_count = 0
    completed_count = 0
    next_task_index = 0
    failed_video_names = []

    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        active_futures = {}

        while (
            not cancel_event.is_set()
            and next_task_index < len(tasks)
            and len(active_futures) < worker_count
        ):
            future = executor.submit(process_video, tasks[next_task_index])
            active_futures[future] = tasks[next_task_index]
            next_task_index += 1

        while active_futures:
            completed_futures, _ = wait(active_futures, return_when=FIRST_COMPLETED)

            for future in completed_futures:
                video_path, _ = active_futures.pop(future)
                try:
                    success, message = future.result()
                except Exception as exc:
                    success = False
                    message = f"Failed: {video_path} ({exc})"

                completed_count += 1
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    failed_video_names.append(video_path.name)
                _report_progress(
                    progress_callback,
                    completed_count,
                    len(tasks),
                    success,
                    message,
                )

            while (
                not cancel_event.is_set()
                and next_task_index < len(tasks)
                and len(active_futures) < worker_count
            ):
                future = executor.submit(process_video, tasks[next_task_index])
                active_futures[future] = tasks[next_task_index]
                next_task_index += 1

    return GenerationResult(
        len(tasks),
        success_count,
        failure_count,
        len(tasks) - completed_count,
        tuple(failed_video_names),
    )


def format_elapsed(seconds):
    """Format elapsed seconds as MM:SS or HH:MM:SS."""
    seconds = max(0, round(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def format_generation_summary(
    completed_at,
    elapsed_seconds,
    selected_count,
    result,
    skipped_count=0,
):
    """Format the completed generation results for display in the app."""
    lines = [
        "Generation Summary",
        f"Completed at: {completed_at.isoformat(timespec='seconds')}",
        f"Elapsed time: {format_elapsed(elapsed_seconds)}",
        f"Selected videos: {selected_count}",
        f"Succeeded: {result.success_count}",
        f"Failed: {result.failure_count}",
        f"Skipped: {skipped_count}",
        f"Canceled: {result.canceled_count}",
    ]

    if result.failed_video_names:
        lines.extend(["", "Failed videos:"])
        lines.extend(f"- {name}" for name in result.failed_video_names)

    return "\n".join(lines)

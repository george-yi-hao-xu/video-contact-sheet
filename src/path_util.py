from collections.abc import Iterable
from os import PathLike
from pathlib import Path


PathInput = str | PathLike[str]


VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
    ".mts", ".m2ts", ".ts",
}


def is_video_file(path: Path) -> bool:
    """Return whether a path points to a supported video file."""
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def find_video_paths(
    input_folder: PathInput,
    output_folder: PathInput | None = None,
    recursive: bool = True,
) -> list[Path]:
    """Find supported videos in a folder, optionally searching subfolders.

    Videos located inside the output folder are excluded so generated files or
    copied source videos are not accidentally processed again.
    """
    input_folder = Path(input_folder)
    output_folder = Path(output_folder).resolve() if output_folder else None
    candidates = input_folder.rglob("*") if recursive else input_folder.iterdir()

    videos = []
    for path in candidates:
        if not is_video_file(path):
            continue

        if output_folder is not None:
            try:
                path.resolve().relative_to(output_folder)
                continue
            except ValueError:
                pass

        videos.append(path)

    return sorted(videos, key=lambda path: str(path).lower())


def format_output_name(relative_path: Path) -> str:
    """Flatten a relative source path into a safe contact-sheet filename stem."""
    return "__".join(relative_path.parts).replace(".", "_")


def plan_output_tasks(
    video_paths: Iterable[PathInput],
    output_folder: PathInput,
    input_folder: PathInput | None = None,
) -> list[tuple[Path, Path]]:
    """Pair each source video with a unique JPEG path in the output folder.

    Folder selections retain their relative path in flattened form. Individual
    file selections use only the source filename. Numeric suffixes prevent two
    selected videos from being assigned the same output path.
    """
    output_folder = Path(output_folder)
    input_folder = Path(input_folder) if input_folder else None
    reserved_names = set()
    tasks = []

    for video_path in video_paths:
        video_path = Path(video_path)
        if input_folder is None:
            source_name = Path(video_path.name)
        else:
            source_name = video_path.relative_to(input_folder)

        base_name = format_output_name(source_name)
        output_name = f"{base_name}.jpg"
        suffix = 2

        while output_name.lower() in reserved_names:
            output_name = f"{base_name}_{suffix}.jpg"
            suffix += 1

        reserved_names.add(output_name.lower())
        tasks.append((video_path, output_folder / output_name))

    return tasks

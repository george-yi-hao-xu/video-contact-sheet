from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
    ".mts", ".m2ts", ".ts",
}


def is_video_file(path):
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def find_video_paths(input_folder, output_folder=None, recursive=True):
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


def format_output_name(relative_path):
    return "__".join(relative_path.parts).replace(".", "_")


def plan_output_tasks(video_paths, output_folder, input_folder=None):
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

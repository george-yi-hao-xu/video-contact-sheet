VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
    ".mts", ".m2ts", ".ts",
}


def is_video_file(path):
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def find_video_paths(current_folder, output_folder):
    return sorted(
        [
            path
            for path in current_folder.rglob("*")
            if is_video_file(path)
            and output_folder not in path.parents  # defensive: in case a video is in output folder
        ],
        key=lambda path: str(path).lower(),
    )


def format_output_name(relative_path):
    return "__".join(relative_path.parts).replace(".", "_")


def get_output_path(current_folder, output_folder, video_path):
    relative_path = video_path.relative_to(current_folder)
    output_name = format_output_name(relative_path)
    return output_folder / f"{output_name}.jpg"

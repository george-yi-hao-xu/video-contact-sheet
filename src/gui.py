import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from time import perf_counter
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .gen_video_sheet import (
    GenerationResult,
    generate_contact_sheets,
    write_generation_report,
)
from .path_util import VIDEO_EXTENSIONS, find_video_paths, plan_output_tasks


class VideoContactSheetApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Contact Sheet")
        self.root.minsize(680, 520)
        self.root.geometry("760x600")

        self.mode = tk.StringVar(value="folder")
        self.folder_path = tk.StringVar()
        self.files_summary = tk.StringVar(value="No files selected")
        self.output_path = tk.StringVar()
        self.include_subfolders = tk.BooleanVar(value=True)
        self.progress_text = tk.StringVar(value="Ready")
        self.selected_files = []
        self.running = False
        self.close_requested = False
        self.cancel_event = None
        self.event_queue = queue.Queue()
        self.input_controls = []

        self._configure_style()
        self._build_ui()
        self._update_mode()
        self._update_generate_state()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_events)

    def _configure_style(self):
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Hint.TLabel", foreground="#606060")

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=22)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(5, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        ttk.Label(container, text="Video Contact Sheet", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            container,
            text="Select videos, choose an output folder, and generate preview sheets.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 18))

        input_group = ttk.LabelFrame(container, text="1. Choose videos", padding=14)
        input_group.grid(row=2, column=0, sticky="ew")
        input_group.columnconfigure(1, weight=1)

        folder_radio = ttk.Radiobutton(
            input_group,
            text="Folder",
            value="folder",
            variable=self.mode,
            command=self._update_mode,
        )
        folder_radio.grid(row=0, column=0, sticky="w", padx=(0, 18))
        files_radio = ttk.Radiobutton(
            input_group,
            text="Multiple files",
            value="files",
            variable=self.mode,
            command=self._update_mode,
        )
        files_radio.grid(row=0, column=1, sticky="w")

        self.folder_frame = ttk.Frame(input_group)
        self.folder_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.folder_frame.columnconfigure(0, weight=1)
        self.folder_entry = ttk.Entry(
            self.folder_frame, textvariable=self.folder_path, state="readonly"
        )
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.folder_button = ttk.Button(
            self.folder_frame, text="Browse...", command=self._choose_folder
        )
        self.folder_button.grid(row=0, column=1)
        self.recursive_check = ttk.Checkbutton(
            self.folder_frame,
            text="Include subfolders",
            variable=self.include_subfolders,
        )
        self.recursive_check.grid(row=1, column=0, sticky="w", pady=(9, 0))

        self.files_frame = ttk.Frame(input_group)
        self.files_frame.columnconfigure(0, weight=1)
        self.files_entry = ttk.Entry(
            self.files_frame, textvariable=self.files_summary, state="readonly"
        )
        self.files_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.files_button = ttk.Button(
            self.files_frame, text="Browse...", command=self._choose_files
        )
        self.files_button.grid(row=0, column=1)

        output_group = ttk.LabelFrame(container, text="2. Choose output folder", padding=14)
        output_group.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        output_group.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(
            output_group, textvariable=self.output_path, state="readonly"
        )
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.output_button = ttk.Button(
            output_group, text="Browse...", command=self._choose_output
        )
        self.output_button.grid(row=0, column=1)

        progress_group = ttk.LabelFrame(container, text="3. Generate", padding=14)
        progress_group.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        progress_group.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(progress_group, mode="determinate")
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(progress_group, textvariable=self.progress_text).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        button_frame = ttk.Frame(progress_group)
        button_frame.grid(row=1, column=1, sticky="e", pady=(8, 0))
        self.cancel_button = ttk.Button(
            button_frame, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_button.grid(row=0, column=0, padx=(0, 8))
        self.generate_button = ttk.Button(
            button_frame, text="Generate", command=self._start_generation
        )
        self.generate_button.grid(row=0, column=1)

        log_group = ttk.LabelFrame(container, text="Activity", padding=10)
        log_group.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        log_group.columnconfigure(0, weight=1)
        log_group.rowconfigure(0, weight=1)
        self.log = scrolledtext.ScrolledText(
            log_group,
            height=8,
            wrap="word",
            state="disabled",
            font=("Segoe UI", 9),
        )
        self.log.grid(row=0, column=0, sticky="nsew")

        self.input_controls = [
            folder_radio,
            files_radio,
            self.folder_button,
            self.files_button,
            self.recursive_check,
            self.output_button,
        ]

    def _choose_folder(self):
        selected = filedialog.askdirectory(title="Choose a video folder")
        if selected:
            self.folder_path.set(selected)
            self._update_generate_state()

    def _choose_files(self):
        patterns = " ".join(f"*{extension}" for extension in sorted(VIDEO_EXTENSIONS))
        selected = filedialog.askopenfilenames(
            title="Choose video files",
            filetypes=[("Video files", patterns), ("All files", "*.*")],
        )
        if selected:
            self.selected_files = [Path(path) for path in selected]
            count = len(self.selected_files)
            self.files_summary.set(f"{count} video file{'s' if count != 1 else ''} selected")
            self._update_generate_state()

    def _choose_output(self):
        selected = filedialog.askdirectory(title="Choose an output folder")
        if selected:
            self.output_path.set(selected)
            self._update_generate_state()

    def _update_mode(self):
        if self.mode.get() == "folder":
            self.files_frame.grid_remove()
            self.folder_frame.grid()
        else:
            self.folder_frame.grid_remove()
            self.files_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self._update_generate_state()

    def _has_valid_selection(self):
        if not self.output_path.get():
            return False
        if self.mode.get() == "folder":
            return bool(self.folder_path.get())
        return bool(self.selected_files)

    def _update_generate_state(self):
        if not hasattr(self, "generate_button"):
            return
        enabled = self._has_valid_selection() and not self.running
        self.generate_button.configure(state="normal" if enabled else "disabled")

    def _set_running_state(self, running):
        self.running = running
        control_state = "disabled" if running else "normal"
        for control in self.input_controls:
            control.configure(state=control_state)
        self.cancel_button.configure(state="normal" if running else "disabled")
        self._update_generate_state()

    def _collect_videos(self):
        if self.mode.get() == "folder":
            input_folder = Path(self.folder_path.get())
            videos = find_video_paths(
                input_folder,
                self.output_path.get(),
                self.include_subfolders.get(),
            )
            return videos, input_folder
        return list(self.selected_files), None

    def _start_generation(self):
        videos, input_folder = self._collect_videos()
        if not videos:
            messagebox.showwarning(
                "No videos found",
                "No supported video files were found in the selected input.",
                parent=self.root,
            )
            return

        output_folder = Path(self.output_path.get())
        tasks = plan_output_tasks(videos, output_folder, input_folder)
        conflicts = [task for task in tasks if task[1].exists()]
        skipped_count = 0

        if conflicts:
            choice = messagebox.askyesnocancel(
                "Existing contact sheets",
                (
                    f"{len(conflicts)} contact sheet(s) already exist.\n\n"
                    "Yes: overwrite all existing files\n"
                    "No: skip all existing files\n"
                    "Cancel: do not start this run"
                ),
                parent=self.root,
            )
            if choice is None:
                return
            if not choice:
                tasks = [task for task in tasks if not task[1].exists()]
                skipped_count = len(conflicts)

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.progress_bar.configure(maximum=max(1, len(tasks)), value=0)
        self.progress_text.set(f"0 / {len(tasks)} completed")
        self.cancel_event = threading.Event()
        self.close_requested = False
        self._set_running_state(True)
        self._append_log(f"Starting {len(tasks)} video(s)...")

        worker = threading.Thread(
            target=self._run_generation,
            args=(tasks, len(videos), skipped_count, output_folder),
            daemon=True,
        )
        worker.start()

    def _run_generation(self, tasks, selected_count, skipped_count, output_folder):
        started_at = perf_counter()
        try:
            result = generate_contact_sheets(
                tasks,
                self.cancel_event,
                lambda completed, total, success, message: self.event_queue.put(
                    ("progress", completed, total, success, message)
                ),
            )
            completed_at = datetime.now().astimezone()
            report_path = write_generation_report(
                output_folder,
                completed_at,
                perf_counter() - started_at,
                selected_count,
                result,
                skipped_count,
            )
            self.event_queue.put(("done", result, skipped_count, report_path))
        except Exception as exc:
            self.event_queue.put(("fatal", str(exc)))

    def _poll_events(self):
        try:
            while True:
                event = self.event_queue.get_nowait()
                event_type = event[0]
                if event_type == "progress":
                    _, completed, total, success, message = event
                    self.progress_bar.configure(value=completed)
                    self.progress_text.set(f"{completed} / {total} completed")
                    self._append_log(message)
                elif event_type == "done":
                    _, result, skipped_count, report_path = event
                    self._finish_run(result, skipped_count, report_path)
                elif event_type == "fatal":
                    self._handle_fatal_error(event[1])
        except queue.Empty:
            pass

        try:
            if self.root.winfo_exists():
                self.root.after(100, self._poll_events)
        except tk.TclError:
            pass

    def _append_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _cancel(self):
        if self.running and self.cancel_event and not self.cancel_event.is_set():
            self.cancel_event.set()
            self.cancel_button.configure(state="disabled")
            self.progress_text.set("Canceling after active videos finish...")
            self._append_log("Cancellation requested. Active videos will finish safely.")

    def _finish_run(self, result, skipped_count, report_path):
        self._set_running_state(False)
        if result.canceled_count:
            self.progress_text.set("Canceled")
        else:
            self.progress_text.set("Complete")

        if self.close_requested:
            self.root.destroy()
            return

        messagebox.showinfo(
            "Generation complete",
            (
                f"Succeeded: {result.success_count}\n"
                f"Failed: {result.failure_count}\n"
                f"Skipped: {skipped_count}\n"
                f"Canceled: {result.canceled_count}\n\n"
                f"Report: {report_path}"
            ),
            parent=self.root,
        )

    def _handle_fatal_error(self, message):
        self._set_running_state(False)
        self.progress_text.set("Generation failed")
        self._append_log(f"Fatal error: {message}")
        if self.close_requested:
            self.root.destroy()
            return
        messagebox.showerror("Generation failed", message, parent=self.root)

    def _on_close(self):
        if not self.running:
            self.root.destroy()
            return

        should_close = messagebox.askyesno(
            "Cancel and exit?",
            "Active videos must finish safely before the app can close. Cancel queued work and exit afterward?",
            parent=self.root,
        )
        if should_close:
            self.close_requested = True
            self._cancel()


def launch_app():
    root = tk.Tk()
    VideoContactSheetApp(root)
    root.mainloop()

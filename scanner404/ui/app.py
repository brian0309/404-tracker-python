import asyncio
import ctypes
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from scanner404.config import load_config, save_config
from scanner404.scanner import Scanner404
from scanner404.ui.state import default_counts, has_retryable_errors, summary_text
from scanner404.ui.table import save_visible_rows_to_csv, sort_tree_column, tag_for_status


class ScannerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("404 Link Scanner")
        self.root.geometry("1180x720")
        self.root.minsize(920, 520)

        self.config = load_config()
        self.theme_mode = self.config.get("scanner", "theme", fallback="dark").strip().lower()
        if self.theme_mode not in ("light", "dark"):
            self.theme_mode = "dark"

        self.dark_palette = {
            "bg": "#101418",
            "surface": "#1A2128",
            "surface_alt": "#222C36",
            "surface_muted": "#2A3642",
            "line": "#2E3B48",
            "scrollbar_track": "#161D24",
            "scrollbar_thumb": "#3A4A58",
            "scrollbar_hover": "#4A5E70",
            "scrollbar_active": "#5A7186",
            "scrollbar_arrow": "#B5C3D1",
            "text": "#E8EDF2",
            "muted_text": "#A9B8C7",
            "primary": "#1E88E5",
            "primary_active": "#1769AA",
            "accent": "#00A86B",
            "danger": "#E1514A",
            "danger_active": "#BC3A34",
            "focus": "#58A6FF",
            "ok": "#57D087",
            "notfound": "#FF7B72",
            "error": "#B0BEC9",
            "other": "#F4BF75",
            "pending": "#8EA7BA",
        }
        self.light_palette = {
            "bg": "#F4F8FC",
            "surface": "#FFFFFF",
            "surface_alt": "#F1F5FA",
            "surface_muted": "#E3EDF7",
            "line": "#E5ECF3",
            "scrollbar_track": "#EEF3F8",
            "scrollbar_thumb": "#B8C8D9",
            "scrollbar_hover": "#9FB5CB",
            "scrollbar_active": "#87A2BE",
            "scrollbar_arrow": "#516678",
            "text": "#1E2936",
            "muted_text": "#5F7287",
            "primary": "#1677C8",
            "primary_active": "#105D9E",
            "accent": "#0B8F5A",
            "danger": "#CC3D39",
            "danger_active": "#A5302D",
            "focus": "#1677C8",
            "ok": "#1D7F4A",
            "notfound": "#B42318",
            "error": "#6B7280",
            "other": "#8A5A00",
            "pending": "#64758B",
        }

        self.palette = self.dark_palette.copy() if self.theme_mode == "dark" else self.light_palette.copy()
        self._setup_styles()

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.update_queue = queue.Queue()

        self.scanning = False
        self.paused = False

        self.all_rows: dict[str, tuple[str, str]] = {}
        self.counts = default_counts()

        self._build_ui()
        self._apply_windows_titlebar_theme()
        self._poll_queue()

    def _set_theme(self, mode: str):
        self.theme_mode = "dark" if mode == "dark" else "light"
        self.palette = self.dark_palette.copy() if self.theme_mode == "dark" else self.light_palette.copy()
        self._setup_styles()
        self._apply_windows_titlebar_theme()
        if hasattr(self, "tree"):
            self._apply_tree_tag_colors()
        if hasattr(self, "context_menu"):
            self.context_menu.configure(
                bg=self.palette["surface_muted"],
                fg=self.palette["text"],
                activebackground=self.palette["primary_active"],
                activeforeground="#FFFFFF",
            )

    def _apply_windows_titlebar_theme(self):
        if sys.platform != "win32":
            return

        try:
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            use_dark = 1 if self.theme_mode == "dark" else 0
            value = ctypes.c_int(use_dark)
            dwmapi = ctypes.windll.dwmapi

            # 20 works on most Windows 10/11 builds, 19 is used by some older builds.
            for attr in (20, 19):
                result = dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attr,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
                if result == 0:
                    break
        except Exception:
            # Non-fatal: title bar theming may be unavailable depending on Windows build.
            pass

    def toggle_theme(self):
        mode = "dark" if self.dark_mode_var.get() else "light"
        self._set_theme(mode)
        if not self.config.has_section("scanner"):
            self.config["scanner"] = {}
        self.config["scanner"]["theme"] = mode
        save_config(self.config)

    def _setup_styles(self):
        self.root.configure(bg=self.palette["bg"])
        self.root.option_add("*Font", "{Segoe UI} 10")

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            background=self.palette["bg"],
            foreground=self.palette["text"],
            fieldbackground=self.palette["surface_alt"],
            bordercolor=self.palette["line"],
            lightcolor=self.palette["line"],
            darkcolor=self.palette["line"],
        )

        style.configure("App.TFrame", background=self.palette["bg"])
        style.configure("Card.TFrame", background=self.palette["surface"])

        style.configure(
            "Title.TLabel",
            background=self.palette["bg"],
            foreground=self.palette["text"],
            font="{Segoe UI} 18 bold",
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.palette["bg"],
            foreground=self.palette["muted_text"],
            font="{Segoe UI} 10",
        )
        style.configure(
            "FieldLabel.TLabel",
            background=self.palette["surface"],
            foreground=self.palette["muted_text"],
            font="{Segoe UI} 9 bold",
        )
        style.configure(
            "Counter.TLabel",
            background=self.palette["surface"],
            foreground=self.palette["text"],
            font=("Consolas", 10),
        )

        style.configure(
            "Modern.TEntry",
            padding=(8, 6),
            borderwidth=0,
            relief="flat",
            fieldbackground=self.palette["surface"],
            foreground=self.palette["text"],
            insertcolor=self.palette["text"],
            bordercolor=self.palette["surface"],
            lightcolor=self.palette["surface"],
            darkcolor=self.palette["surface"],
        )
        style.configure(
            "Modern.TSpinbox",
            arrowsize=14,
            borderwidth=0,
            relief="flat",
            fieldbackground=self.palette["surface"],
            foreground=self.palette["text"],
            insertcolor=self.palette["text"],
            bordercolor=self.palette["surface"],
            lightcolor=self.palette["surface"],
            darkcolor=self.palette["surface"],
        )

        style.configure(
            "Primary.TButton",
            background=self.palette["primary"],
            foreground="#FFFFFF",
            padding=(14, 8),
            borderwidth=0,
            relief="flat",
            font="{Segoe UI} 10 bold",
        )
        style.map(
            "Primary.TButton",
            background=[("active", self.palette["primary_active"]), ("disabled", "#3A4B5D")],
            foreground=[("disabled", "#93A6B8")],
        )

        style.configure(
            "Secondary.TButton",
            background=self.palette["surface_muted"],
            foreground=self.palette["text"],
            padding=(12, 8),
            borderwidth=0,
            relief="flat",
            font="{Segoe UI} 10",
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#344452"), ("disabled", "#283540")],
            foreground=[("disabled", "#8FA0B0")],
        )

        style.configure(
            "Danger.TButton",
            background=self.palette["danger"],
            foreground="#FFFFFF",
            padding=(12, 8),
            borderwidth=0,
            relief="flat",
            font="{Segoe UI} 10 bold",
        )
        style.map(
            "Danger.TButton",
            background=[("active", self.palette["danger_active"]), ("disabled", "#4A373A")],
            foreground=[("disabled", "#BCA8AA")],
        )

        style.configure(
            "Filter.TRadiobutton",
            background=self.palette["surface"],
            foreground=self.palette["muted_text"],
            padding=(8, 3),
            indicatorcolor=self.palette["bg"],
            indicatormargin=2,
            focuscolor=self.palette["focus"],
            font="{Segoe UI} 9",
        )
        style.map(
            "Filter.TRadiobutton",
            foreground=[("selected", self.palette["accent"]), ("active", self.palette["text"])],
            background=[("active", self.palette["surface"])],
        )

        style.configure(
            "Modern.TCheckbutton",
            background=self.palette["surface"],
            foreground=self.palette["muted_text"],
            font="{Segoe UI} 9",
        )
        style.map(
            "Modern.TCheckbutton",
            foreground=[("selected", self.palette["text"]), ("active", self.palette["text"])],
        )

        style.configure(
            "Modern.Treeview",
            background=self.palette["surface"],
            foreground=self.palette["text"],
            fieldbackground=self.palette["surface"],
            rowheight=28,
            borderwidth=0,
            relief="flat",
            bordercolor=self.palette["surface"],
            lightcolor=self.palette["surface"],
            darkcolor=self.palette["surface"],
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", self.palette["primary_active"])],
            foreground=[("selected", "#FFFFFF")],
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=self.palette["surface_muted"],
            foreground=self.palette["text"],
            borderwidth=0,
            relief="flat",
            padding=(8, 7),
            font="{Segoe UI} 9 bold",
            bordercolor=self.palette["surface_muted"],
            lightcolor=self.palette["surface_muted"],
            darkcolor=self.palette["surface_muted"],
        )
        style.map(
            "Modern.Treeview.Heading",
            background=[("active", "#344452")],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=self.palette["scrollbar_thumb"],
            troughcolor=self.palette["scrollbar_track"],
            borderwidth=0,
            arrowcolor=self.palette["scrollbar_arrow"],
            arrowsize=10,
            width=10,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", self.palette["scrollbar_hover"]), ("pressed", self.palette["scrollbar_active"])],
            arrowcolor=[("active", self.palette["text"])],
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=self.palette["scrollbar_thumb"],
            troughcolor=self.palette["scrollbar_track"],
            borderwidth=0,
            arrowcolor=self.palette["scrollbar_arrow"],
            arrowsize=10,
            width=10,
        )
        style.map(
            "Horizontal.TScrollbar",
            background=[("active", self.palette["scrollbar_hover"]), ("pressed", self.palette["scrollbar_active"])],
            arrowcolor=[("active", self.palette["text"])],
        )

    def _build_ui(self):
        shell = ttk.Frame(self.root, style="App.TFrame", padding=16)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell, style="App.TFrame")
        header.pack(fill="x", pady=(0, 12))
        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="404 Link Scanner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Scan pages, track broken links, and export report-ready CSV results.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        self.dark_mode_var = tk.BooleanVar(value=self.theme_mode == "dark")
        ttk.Checkbutton(
            header,
            text="Dark mode",
            variable=self.dark_mode_var,
            command=self.toggle_theme,
            style="Modern.TCheckbutton",
        ).pack(side="right", padx=(8, 0), pady=(4, 0))

        top = ttk.Frame(shell, style="Card.TFrame", padding=14)
        top.pack(fill="x")

        ttk.Label(top, text="Base URL", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar(value="https://briancarlo.pages.dev/")
        ttk.Entry(top, textvariable=self.url_var, width=58, style="Modern.TEntry").grid(
            row=0,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(10, 0),
        )

        ttk.Label(top, text="Threads", style="FieldLabel.TLabel").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(10, 0),
        )
        self.threads_var = tk.IntVar(
            value=self.config.getint("scanner", "threads", fallback=5)
        )
        ttk.Spinbox(
            top,
            from_=1,
            to=50,
            textvariable=self.threads_var,
            width=6,
            style="Modern.TSpinbox",
        ).grid(row=1, column=1, sticky="w", pady=(10, 0), padx=(10, 0))

        ttk.Label(top, text="Timeout (s)", style="FieldLabel.TLabel").grid(
            row=1,
            column=2,
            sticky="w",
            pady=(10, 0),
            padx=(14, 0),
        )
        self.timeout_var = tk.IntVar(
            value=self.config.getint("scanner", "timeout", fallback=10)
        )
        ttk.Spinbox(
            top,
            from_=1,
            to=120,
            textvariable=self.timeout_var,
            width=6,
            style="Modern.TSpinbox",
        ).grid(row=1, column=3, sticky="w", pady=(10, 0), padx=(10, 0))

        for col in range(4):
            top.columnconfigure(col, weight=1 if col in (1, 3) else 0)

        ttk.Separator(top, orient="horizontal").grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(12, 10),
        )

        if self.config.has_option("scanner", "crawl_subpages"):
            crawl_subpages_default = self.config.getboolean(
                "scanner", "crawl_subpages", fallback=True
            )
        elif self.config.has_option("scanner", "only_page_links"):
            crawl_subpages_default = not self.config.getboolean(
                "scanner", "only_page_links", fallback=False
            )
        else:
            crawl_subpages_default = True

        ttk.Label(top, text="Crawl Behavior", style="FieldLabel.TLabel").grid(
            row=3,
            column=0,
            sticky="w",
        )
        self.crawl_subpages_var = tk.BooleanVar(value=crawl_subpages_default)
        ttk.Checkbutton(
            top,
            text="Recursively crawl internal links from discovered pages",
            variable=self.crawl_subpages_var,
            style="Modern.TCheckbutton",
        ).grid(row=3, column=1, columnspan=3, sticky="w")

        btn_frame = ttk.Frame(shell, style="Card.TFrame", padding=(14, 10))
        btn_frame.pack(fill="x", pady=(12, 0))

        self.start_btn = ttk.Button(
            btn_frame,
            text="Start Scan",
            command=self.start_scan,
            style="Primary.TButton",
        )
        self.start_btn.pack(side="left")

        self.pause_btn = ttk.Button(
            btn_frame,
            text="Pause",
            command=self.toggle_pause,
            state="disabled",
            style="Secondary.TButton",
        )
        self.pause_btn.pack(side="left", padx=(8, 0))

        self.stop_btn = ttk.Button(
            btn_frame,
            text="Stop",
            command=self.stop_scan,
            state="disabled",
            style="Danger.TButton",
        )
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.rerun_btn = ttk.Button(
            btn_frame,
            text="Rerun Errors",
            command=self.rerun_errors,
            state="disabled",
            style="Secondary.TButton",
        )
        self.rerun_btn.pack(side="left", padx=(8, 0))

        self.save_btn = ttk.Button(
            btn_frame,
            text="Save CSV",
            command=self.save_csv,
            style="Secondary.TButton",
        )
        self.save_btn.pack(side="left", padx=(8, 0))

        ttk.Separator(btn_frame, orient="vertical").pack(side="left", fill="y", padx=12)

        filter_frame = ttk.Frame(btn_frame, style="Card.TFrame")
        filter_frame.pack(side="left")

        ttk.Label(filter_frame, text="Filter:", style="FieldLabel.TLabel").pack(
            side="left",
            padx=(0, 6),
        )
        self.filter_var = tk.StringVar(value="all")
        for text, value in [
            ("All", "all"),
            ("Pending", "Pending"),
            ("200", "200"),
            ("404", "404"),
            ("ERR", "ERR"),
        ]:
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self.filter_var,
                value=value,
                command=self.apply_filter,
                style="Filter.TRadiobutton",
            ).pack(side="left", padx=(0, 6))

        stats_frame = ttk.Frame(shell, style="Card.TFrame", padding=(14, 8))
        stats_frame.pack(fill="x", pady=(12, 0))

        self.counter_var = tk.StringVar(value=summary_text(default_counts()))
        ttk.Label(
            stats_frame,
            textvariable=self.counter_var,
            anchor="w",
            style="Counter.TLabel",
        ).pack(fill="x")

        tree_frame = ttk.Frame(shell, style="Card.TFrame", padding=(12, 10, 12, 12))
        tree_frame.pack(fill="both", expand=True, pady=(12, 0))

        columns = ("status", "title", "url", "source")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="Modern.Treeview",
        )
        self.tree.heading(
            "status",
            text="Status",
            command=lambda: sort_tree_column(self.tree, "status", False),
        )
        self.tree.heading(
            "title",
            text="Page Title",
            command=lambda: sort_tree_column(self.tree, "title", False),
        )
        self.tree.heading(
            "url",
            text="URL",
            command=lambda: sort_tree_column(self.tree, "url", False),
        )
        self.tree.heading(
            "source",
            text="Source",
            command=lambda: sort_tree_column(self.tree, "source", False),
        )
        self.tree.column("status", width=82, minwidth=60, stretch=False)
        self.tree.column("title", width=280, minwidth=170)
        self.tree.column("url", width=430, minwidth=240)
        self.tree.column("source", width=340, minwidth=180)

        vsb = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
            style="Vertical.TScrollbar",
        )
        hsb = ttk.Scrollbar(
            tree_frame,
            orient="horizontal",
            command=self.tree.xview,
            style="Horizontal.TScrollbar",
        )
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        hsb.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self._apply_tree_tag_colors()

        self.context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=self.palette["surface_muted"],
            fg=self.palette["text"],
            activebackground=self.palette["primary_active"],
            activeforeground="#FFFFFF",
            bd=0,
        )
        self.context_menu.add_command(label="Copy Row Log", command=self.copy_row_log)
        self.context_menu.add_command(label="Copy URL", command=self.copy_url)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def _apply_tree_tag_colors(self):
        self.tree.tag_configure("ok", foreground=self.palette["ok"])
        self.tree.tag_configure("notfound", foreground=self.palette["notfound"])
        self.tree.tag_configure("error", foreground=self.palette["error"])
        self.tree.tag_configure("other", foreground=self.palette["other"])
        self.tree.tag_configure("pending", foreground=self.palette["pending"])

    def show_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.context_menu.post(event.x_root, event.y_root)

    def copy_row_log(self):
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0], "values")
        if values:
            source = values[3] if len(values) > 3 else ""
            text = f"Status: {values[0]} | Title/Error: {values[1]} | URL: {values[2]} | Source: {source}"
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def copy_url(self):
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0], "values")
        if values and len(values) > 2:
            self.root.clipboard_clear()
            self.root.clipboard_append(values[2])

    def update_counters(self):
        self.counter_var.set(summary_text(self.counts))

    def apply_filter(self):
        selected_filter = self.filter_var.get()
        for row_id in self.tree.get_children():
            self.tree.detach(row_id)

        for _, (row_id, status) in self.all_rows.items():
            if selected_filter == "all" or status == selected_filter:
                self.tree.reattach(row_id, "", "end")

    def add_or_update_row(self, url: str, status: str, title: str = "", source: str = ""):
        tag = tag_for_status(status)

        if url in self.all_rows:
            row_id, old_status = self.all_rows[url]
            if old_status in self.counts:
                self.counts[old_status] = max(0, self.counts[old_status] - 1)
            existing_values = self.tree.item(row_id, "values")
            row_source = source or (existing_values[3] if len(existing_values) > 3 else "")
            self.tree.item(row_id, values=(status, title, url, row_source), tags=(tag,))
            self.all_rows[url] = (row_id, status)
        else:
            row_id = self.tree.insert("", "end", values=(status, title, url, source), tags=(tag,))
            self.all_rows[url] = (row_id, status)

        if status in self.counts:
            self.counts[status] += 1

        self.update_counters()

    def add_pending_row(self, url: str, source: str = ""):
        if url in self.all_rows:
            self.add_or_update_row(url, "Pending", "", source)
            return

        row_id = self.tree.insert(
            "",
            "end",
            values=("Pending", "", url, source),
            tags=(tag_for_status("Pending"),),
        )
        self.all_rows[url] = (row_id, "Pending")
        self.counts["Pending"] += 1
        self.update_counters()

    def _poll_queue(self):
        batch_size = 0

        while not self.update_queue.empty() and batch_size < 200:
            message = self.update_queue.get_nowait()
            if message[0] == "row":
                _, url, status, title = message
                self.add_or_update_row(url, status, title)
            elif message[0] == "pending":
                if len(message) >= 3:
                    self.add_pending_row(message[1], message[2])
                else:
                    self.add_pending_row(message[1], "")
            batch_size += 1

        if self.scanning and self.stop_event.is_set():
            self.scanning = False
            self.start_btn.configure(state="normal")
            self.pause_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self.rerun_btn.configure(state="normal" if has_retryable_errors(self.all_rows) else "disabled")
            self.paused = False
            self.pause_btn.configure(text="Pause")
            self.stop_event.clear()

        self.root.after(100, self._poll_queue)

    def _run_scan(self, url: str, threads: int, crawl_subpages: bool):
        async def async_scan():
            try:
                scanner = Scanner404(
                    base_url=url,
                    config=self.config,
                    update_queue=self.update_queue,
                    stop_event=self.stop_event,
                    pause_event=self.pause_event,
                    crawl_subpages=crawl_subpages,
                )
                await scanner.scan(threads)
            except Exception as err:
                self.update_queue.put(("row", url, "ERR", str(err)))

        asyncio.run(async_scan())

    def start_scan(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Input", "Enter a URL.")
            return

        if not url.startswith("http"):
            url = f"https://{url}"
            self.url_var.set(url)

        for row_id in self.tree.get_children():
            self.tree.delete(row_id)

        self.all_rows.clear()
        self.counts = default_counts()
        self.update_counters()

        self.scanning = True
        self.paused = False
        self.stop_event.clear()
        self.pause_event.set()

        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="Pause")
        self.stop_btn.configure(state="normal")
        self.rerun_btn.configure(state="disabled")

        self.config["scanner"]["threads"] = str(self.threads_var.get())
        self.config["scanner"]["timeout"] = str(self.timeout_var.get())
        self.config["scanner"]["crawl_subpages"] = "1" if self.crawl_subpages_var.get() else "0"
        self.config["scanner"]["theme"] = self.theme_mode
        save_config(self.config)

        thread = threading.Thread(
            target=self._run_scan,
            args=(url, self.threads_var.get(), self.crawl_subpages_var.get()),
            daemon=True,
        )
        thread.start()

    def toggle_pause(self):
        if self.paused:
            self.pause_event.set()
            self.paused = False
            self.pause_btn.configure(text="Pause")
            return

        self.pause_event.clear()
        self.paused = True
        self.pause_btn.configure(text="Resume")

    def stop_scan(self):
        self.stop_event.set()
        self.pause_event.set()
        self.scanning = False
        self.paused = False
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="Pause")
        self.stop_btn.configure(state="disabled")

    def rerun_errors(self):
        error_urls = [
            url for url, (_, status) in self.all_rows.items() if status in ("404", "ERR")
        ]
        if not error_urls:
            messagebox.showinfo("Rerun", "No 404 or ERR results to rerun.")
            return

        self.scanning = True
        self.paused = False
        self.stop_event.clear()
        self.pause_event.set()

        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="Pause")
        self.stop_btn.configure(state="normal")
        self.rerun_btn.configure(state="disabled")

        self.config["scanner"]["threads"] = str(self.threads_var.get())
        self.config["scanner"]["timeout"] = str(self.timeout_var.get())
        self.config["scanner"]["theme"] = self.theme_mode
        save_config(self.config)

        url = self.url_var.get().strip()
        thread = threading.Thread(
            target=self._rerun_errors_thread,
            args=(url, error_urls, self.threads_var.get(), self.crawl_subpages_var.get()),
            daemon=True,
        )
        thread.start()

    def _rerun_errors_thread(self, base_url: str, urls: list[str], threads: int, crawl_subpages: bool):
        async def async_rerun():
            try:
                scanner = Scanner404(
                    base_url=base_url,
                    config=self.config,
                    update_queue=self.update_queue,
                    stop_event=self.stop_event,
                    pause_event=self.pause_event,
                    crawl_subpages=crawl_subpages,
                )
                scanner.visited.update(urls)

                for url in urls:
                    scanner.update_queue.put(("pending", url, "Rerun"))
                    scanner.queued.add(url)
                    await scanner.url_queue.put((url, 0, False))
                    scanner.visited.discard(url)

                await scanner.scan(threads)
            except Exception as err:
                self.update_queue.put(("row", base_url, "ERR", str(err)))

        asyncio.run(async_rerun())

    def save_csv(self):
        if not self.all_rows:
            messagebox.showinfo("Save", "No results to save.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if not path:
            return

        save_visible_rows_to_csv(self.tree, path)
        messagebox.showinfo("Save", f"Saved {len(self.all_rows)} rows to {path}")


def run_app():
    root = tk.Tk()
    app = ScannerApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
    return app

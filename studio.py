"""
Cartoon Shorts Studio — Desktop App
====================================
A simple window for everything: make one video, run autopilot batches.
No PowerShell needed.

Run:    python studio.py
Or:     double-click run_studio.bat
"""

import asyncio
import datetime
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from make_video import build_video, CARTOON_STYLES, VOICES
from pollinations_llm import enhance_visual_prompt, generate_script


# ─── stdout redirect → log queue ──────────────────────────────────────────────

class QueueWriter:
    """File-like object that pushes writes into a queue (thread-safe)."""
    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)

    def flush(self):
        pass


# ─── Main app ─────────────────────────────────────────────────────────────────

class CartoonShortsStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬  Cartoon Shorts Studio")
        self.root.geometry("960x760")
        self.root.minsize(820, 640)

        # styling
        try:
            style = ttk.Style()
            for theme in ("vista", "clam", "default"):
                if theme in style.theme_names():
                    style.theme_use(theme)
                    break
            style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=8)
            style.configure("Section.TLabelframe", padding=12)
            style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        except Exception:
            pass

        self.log_queue = queue.Queue()
        self.busy = False
        self._build_ui()
        self._poll_log_queue()
        self._append_log("Ready. Pick a tab and click a build button.\n")

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Menu bar
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open Output Folder", command=self._open_output)
        filemenu.add_command(label="Open Scripts Folder", command=self._open_scripts)
        filemenu.add_command(label="Edit Topics File", command=self._open_topics)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self._show_about)
        helpmenu.add_command(label="Tips for Better Quality", command=self._show_tips)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)

        # Main container
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.rowconfigure(0, weight=3)
        main.rowconfigure(1, weight=2)
        main.columnconfigure(0, weight=1)

        # Notebook (tabs)
        self.nb = ttk.Notebook(main)
        self.nb.grid(row=0, column=0, sticky="nsew")
        self.tab_one = ttk.Frame(self.nb)
        self.tab_auto = ttk.Frame(self.nb)
        self.nb.add(self.tab_one, text="  📝  Make One Video  ")
        self.nb.add(self.tab_auto, text="  🚀  Autopilot (Daily Batch)  ")

        self._build_one_tab()
        self._build_auto_tab()

        # Shared log area
        log_frame = ttk.LabelFrame(main, text=" Log ", style="Section.TLabelframe")
        log_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap="word", font=("Consolas", 9),
            background="#1e1e1e", foreground="#dcdcdc", insertbackground="#dcdcdc",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

        # Status bar
        status_bar = ttk.Frame(main)
        status_bar.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        status_bar.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_bar, textvariable=self.status_var, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=4
        )
        ttk.Button(status_bar, text="Clear log", command=self._clear_log).grid(row=0, column=1, sticky="e")

    # ─── Tab 1: Make One Video ────────────────────────────────────────────────

    def _build_one_tab(self):
        t = self.tab_one
        t.columnconfigure(0, weight=1)
        t.rowconfigure(1, weight=1)

        # Script source
        src_frame = ttk.LabelFrame(t, text=" Script ", style="Section.TLabelframe")
        src_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        src_frame.columnconfigure(0, weight=1)

        radio_row = ttk.Frame(src_frame)
        radio_row.grid(row=0, column=0, sticky="w")
        self.script_mode = tk.StringVar(value="paste")
        ttk.Radiobutton(radio_row, text="Paste script", variable=self.script_mode,
                        value="paste", command=self._on_script_mode_change).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(radio_row, text="Load .txt file", variable=self.script_mode,
                        value="file", command=self._on_script_mode_change).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(radio_row, text="Auto-generate via free LLM", variable=self.script_mode,
                        value="generate", command=self._on_script_mode_change).pack(side="left")

        self.gen_topic_frame = ttk.Frame(src_frame)
        ttk.Label(self.gen_topic_frame, text="Topic to generate about:").pack(side="left", padx=(0, 6))
        self.gen_topic_var = tk.StringVar(value="unexplained mysteries")
        ttk.Entry(self.gen_topic_frame, textvariable=self.gen_topic_var, width=40).pack(side="left", padx=(0, 6))
        ttk.Button(self.gen_topic_frame, text="Generate now", command=self._generate_script_into_box).pack(side="left")

        self.script_text_widget = scrolledtext.ScrolledText(src_frame, wrap="word",
                                                            height=8, font=("Segoe UI", 10))
        self.script_text_widget.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.script_text_widget.insert("1.0",
            "Paste your script here, or pick a radio button above to load a file or auto-generate."
        )

        self.file_picker_frame = ttk.Frame(src_frame)
        ttk.Button(self.file_picker_frame, text="Browse for .txt file…",
                   command=self._browse_for_script).pack(side="left")
        self.chosen_file_var = tk.StringVar(value="(no file chosen)")
        ttk.Label(self.file_picker_frame, textvariable=self.chosen_file_var,
                  foreground="#666").pack(side="left", padx=(8, 0))

        # Settings
        settings = ttk.LabelFrame(t, text=" Settings ", style="Section.TLabelframe")
        settings.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text="Style:").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self.style_var = tk.StringVar(value="adult_cartoon")
        ttk.Combobox(settings, textvariable=self.style_var,
                     values=list(CARTOON_STYLES.keys()), state="readonly", width=18).grid(
            row=0, column=1, sticky="w", padx=(0, 20), pady=4
        )

        ttk.Label(settings, text="Voice:").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        self.voice_var = tk.StringVar(value="narrator")
        ttk.Combobox(settings, textvariable=self.voice_var,
                     values=list(VOICES.keys()), state="readonly", width=18).grid(
            row=0, column=3, sticky="w", pady=4
        )

        ttk.Label(settings, text="Topic hint (optional):").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        self.topic_hint_var = tk.StringVar(value="")
        ttk.Entry(settings, textvariable=self.topic_hint_var).grid(
            row=1, column=1, columnspan=3, sticky="ew", pady=4
        )

        ttk.Label(settings, text="Output filename:").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=4)
        self.name_var = tk.StringVar(value="my_video_001")
        ttk.Entry(settings, textvariable=self.name_var).grid(
            row=2, column=1, columnspan=3, sticky="ew", pady=4
        )

        # Action buttons
        btn_row = ttk.Frame(t)
        btn_row.grid(row=3, column=0, sticky="ew", padx=8, pady=(8, 8))
        self.build_one_btn = ttk.Button(btn_row, text="🎬   Build Video",
                                        style="Accent.TButton", command=self._start_one_build)
        self.build_one_btn.pack(side="left")
        ttk.Button(btn_row, text="Open output folder",
                   command=self._open_output).pack(side="left", padx=(8, 0))

        self._on_script_mode_change()

    # ─── Tab 2: Autopilot ─────────────────────────────────────────────────────

    def _build_auto_tab(self):
        t = self.tab_auto
        t.columnconfigure(0, weight=1)

        info = ttk.Label(
            t, foreground="#666",
            text=(
                "Generates fresh scripts via free LLM, then builds that many videos.\n"
                "Each video takes ~7–10 min, so 5 videos = roughly 35–50 minutes total."
            ),
            font=("Segoe UI", 9), justify="left"
        )
        info.grid(row=0, column=0, sticky="w", padx=8, pady=(10, 6))

        batch = ttk.LabelFrame(t, text=" Today's Batch ", style="Section.TLabelframe")
        batch.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        batch.columnconfigure(1, weight=1)
        batch.columnconfigure(3, weight=1)

        ttk.Label(batch, text="Topic:").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self.auto_topic_var = tk.StringVar(value=self._todays_topic())
        ttk.Entry(batch, textvariable=self.auto_topic_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", pady=4
        )

        ttk.Label(batch, text="Number of videos:").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        self.auto_count_var = tk.IntVar(value=5)
        ttk.Spinbox(batch, from_=1, to=10, textvariable=self.auto_count_var, width=6).grid(
            row=1, column=1, sticky="w", pady=4
        )

        ttk.Label(batch, text="Target length (seconds):").grid(row=1, column=2, sticky="w", padx=(20, 6), pady=4)
        self.auto_length_var = tk.IntVar(value=40)
        ttk.Spinbox(batch, from_=20, to=90, increment=5, textvariable=self.auto_length_var, width=6).grid(
            row=1, column=3, sticky="w", pady=4
        )

        ttk.Label(batch, text="Style:").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=4)
        self.auto_style_var = tk.StringVar(value="adult_cartoon")
        ttk.Combobox(batch, textvariable=self.auto_style_var, values=list(CARTOON_STYLES.keys()),
                     state="readonly", width=18).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(batch, text="Voice:").grid(row=2, column=2, sticky="w", padx=(20, 6), pady=4)
        self.auto_voice_var = tk.StringVar(value="narrator")
        ttk.Combobox(batch, textvariable=self.auto_voice_var, values=list(VOICES.keys()),
                     state="readonly", width=18).grid(row=2, column=3, sticky="w", pady=4)

        # Upload section
        up_frame = ttk.LabelFrame(t, text=" After building ", style="Section.TLabelframe")
        up_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=4)

        self.auto_upload_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(up_frame, text="Auto-upload to YouTube (requires client_secret.json setup)",
                        variable=self.auto_upload_var).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(
            up_frame,
            text="⚠  Strong advice: keep this off for your first 5 batches. Review videos manually.",
            foreground="#a04000", font=("Segoe UI", 9)
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Action buttons
        btn_row = ttk.Frame(t)
        btn_row.grid(row=3, column=0, sticky="ew", padx=8, pady=(8, 8))
        self.build_auto_btn = ttk.Button(btn_row, text="🚀   Build Batch",
                                         style="Accent.TButton", command=self._start_auto_build)
        self.build_auto_btn.pack(side="left")
        ttk.Button(btn_row, text="Open output folder",
                   command=self._open_output).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="Edit topics list",
                   command=self._open_topics).pack(side="left", padx=(8, 0))

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _todays_topic(self):
        p = Path("topics.txt")
        if not p.exists():
            return "unexplained mysteries"
        lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
        if not lines:
            return "unexplained mysteries"
        idx = datetime.date.today().toordinal() % len(lines)
        return lines[idx]

    def _on_script_mode_change(self):
        mode = self.script_mode.get()
        # Hide/show conditional widgets
        self.gen_topic_frame.grid_forget()
        self.file_picker_frame.grid_forget()
        if mode == "generate":
            self.gen_topic_frame.grid(row=1, column=0, sticky="w", pady=(6, 0))
        elif mode == "file":
            self.file_picker_frame.grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _browse_for_script(self):
        f = filedialog.askopenfilename(
            title="Pick a script file",
            initialdir="scripts",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if f:
            try:
                content = Path(f).read_text(encoding="utf-8").strip()
                self.script_text_widget.delete("1.0", "end")
                self.script_text_widget.insert("1.0", content)
                self.chosen_file_var.set(Path(f).name)
                # Auto-name
                self.name_var.set(Path(f).stem)
            except Exception as exc:
                messagebox.showerror("Read error", str(exc))

    def _generate_script_into_box(self):
        topic = self.gen_topic_var.get().strip() or "unexplained mysteries"
        self._set_busy(True, status=f"Generating script about '{topic}'…")
        self._append_log(f"\n📝  Generating fresh script about: {topic}\n")

        def worker():
            try:
                script = generate_script(topic, length_seconds=40)
            except Exception as exc:
                script = None
                self.log_queue.put(f"   error: {exc}\n")
            self.root.after(0, lambda: self._fill_generated_script(script, topic))

        threading.Thread(target=worker, daemon=True).start()

    def _fill_generated_script(self, script, topic):
        if not script:
            self._append_log("   ⚠️ LLM didn't return anything. Try again.\n")
            self._set_busy(False, status="Ready")
            return
        self.script_text_widget.delete("1.0", "end")
        self.script_text_widget.insert("1.0", script)
        slug = topic.replace(" ", "_")[:30]
        self.name_var.set(f"{slug}_{datetime.datetime.now().strftime('%H%M')}")
        self._append_log(f"   ✓ got {len(script)} chars\n")
        self._set_busy(False, status="Script ready — click Build Video")

    # ─── Build actions ────────────────────────────────────────────────────────

    def _start_one_build(self):
        if self.busy:
            return
        script = self.script_text_widget.get("1.0", "end").strip()
        if not script or script.startswith("Paste your script"):
            messagebox.showwarning("No script", "Please paste, load, or generate a script first.")
            return
        name = (self.name_var.get() or "video").strip().replace(" ", "_")
        style = self.style_var.get()
        voice = self.voice_var.get()
        topic = self.topic_hint_var.get().strip()

        self._set_busy(True, status=f"Building {name}.mp4 …")
        self._append_log(f"\n{'═' * 60}\n  Building '{name}.mp4'  ({style} / {voice})\n{'═' * 60}\n")

        def coro():
            return build_video(
                script=script, name=name, style=style, voice=voice,
                topic_hint=topic,
                output_dir=Path("output"), temp_dir=Path("temp"),
            )

        self._run_async_in_thread(coro, on_done=lambda ok: self._on_build_done(ok, name))

    def _start_auto_build(self):
        if self.busy:
            return
        topic = self.auto_topic_var.get().strip() or self._todays_topic()
        count = self.auto_count_var.get()
        length = self.auto_length_var.get()
        style = self.auto_style_var.get()
        voice = self.auto_voice_var.get()
        do_upload = self.auto_upload_var.get()

        confirm = messagebox.askyesno(
            "Confirm batch",
            f"Build {count} videos about '{topic}'?\n\n"
            f"This will take roughly {count * 8} minutes.\n"
            + ("Videos WILL be uploaded to YouTube.\n\n" if do_upload else "")
            + "Continue?",
        )
        if not confirm:
            return

        self._set_busy(True, status=f"Autopilot: building {count} videos…")
        self._append_log(f"\n{'═' * 60}\n  AUTOPILOT  topic='{topic}'  count={count}\n{'═' * 60}\n")

        def coro():
            return self._run_autopilot_async(topic, count, length, style, voice, do_upload)

        self._run_async_in_thread(coro, on_done=lambda ok: self._on_build_done(ok, "batch"))

    async def _run_autopilot_async(self, topic, count, length, style, voice, do_upload):
        today_str = datetime.date.today().isoformat()
        scripts_dir = Path("scripts")
        scripts_dir.mkdir(exist_ok=True)
        output_dir = Path("output")

        print(f"\n📝  Generating {count} scripts via free LLM...")
        scripts = []
        for i in range(count):
            print(f"   [{i + 1}/{count}] generating script...", flush=True)
            tries = 0
            script = None
            while tries < 3 and not script:
                tries += 1
                script = generate_script(topic, length_seconds=length,
                                         attempt_label=f"(variant {i + 1}, attempt {tries})")
            if not script:
                print(f"   ⚠️  script {i + 1} failed, skipping")
                continue
            slug = f"{today_str}_{i + 1:02d}"
            (scripts_dir / f"{slug}.txt").write_text(script, encoding="utf-8")
            scripts.append((slug, script))
            print(f"   ✓ saved {slug}.txt")

        print(f"\n🎬  Building {len(scripts)} videos...")
        built = 0
        for slug, script in scripts:
            try:
                await build_video(
                    script=script, name=slug, style=style, voice=voice,
                    topic_hint=topic, output_dir=output_dir, temp_dir=Path("temp"),
                )
                built += 1
            except Exception as exc:
                print(f"   ❌  {slug} failed: {exc}")

        print(f"\n   Built {built}/{len(scripts)} videos.")

        if do_upload and built:
            print(f"\n📤  Uploading via upload.py…")
            try:
                proc = subprocess.run(
                    [sys.executable, "upload.py", "--batch",
                     "--schedule", "3hours", "--move-uploaded"],
                    capture_output=True, text=True, timeout=600
                )
                print(proc.stdout)
                if proc.returncode != 0:
                    print(f"   upload.py exit code {proc.returncode}\n{proc.stderr}")
            except Exception as exc:
                print(f"   upload failed: {exc}")

    def _run_async_in_thread(self, coro_factory, on_done):
        def worker():
            writer = QueueWriter(self.log_queue)
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = writer
            sys.stderr = writer
            ok = False
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    coro = coro_factory()
                    if asyncio.iscoroutine(coro):
                        loop.run_until_complete(coro)
                    ok = True
                finally:
                    loop.close()
            except Exception:
                self.log_queue.put("\n" + traceback.format_exc() + "\n")
                ok = False
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            self.root.after(0, lambda: on_done(ok))

        threading.Thread(target=worker, daemon=True).start()

    def _on_build_done(self, ok, name):
        if ok:
            self._append_log(f"\n✅  Done.\n")
            self._set_busy(False, status=f"Done — see output folder")
            try:
                if messagebox.askyesno("Done!", f"Build finished. Open the output folder?"):
                    self._open_output()
            except Exception:
                pass
        else:
            self._append_log("\n❌  Build hit an error. Check the log above.\n")
            self._set_busy(False, status="Error — see log")

    # ─── UI helpers ───────────────────────────────────────────────────────────

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _append_log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_busy(self, busy, status=""):
        self.busy = busy
        self.build_one_btn.configure(state="disabled" if busy else "normal")
        self.build_auto_btn.configure(state="disabled" if busy else "normal")
        if status:
            self.status_var.set(status)

    def _open_output(self):
        p = Path("output").resolve()
        p.mkdir(exist_ok=True)
        self._open_in_explorer(p)

    def _open_scripts(self):
        p = Path("scripts").resolve()
        p.mkdir(exist_ok=True)
        self._open_in_explorer(p)

    def _open_topics(self):
        p = Path("topics.txt").resolve()
        if not p.exists():
            p.write_text("# Add topics, one per line\nunexplained mysteries\n", encoding="utf-8")
        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as exc:
            messagebox.showerror("Could not open", str(exc))

    def _open_in_explorer(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Could not open", str(exc))

    def _show_about(self):
        messagebox.showinfo(
            "About",
            "Cartoon Shorts Studio\n\n"
            "Free pipeline: Pollinations (images), Edge TTS (voice), "
            "Whisper (captions), moviepy (assembly).\n\n"
            "Each video takes 5–10 minutes."
        )

    def _show_tips(self):
        tips = (
            "QUALITY TIPS\n\n"
            "• Style choice matters a lot. Try adult_cartoon vs adult_scifi vs "
            "comic to see which suits your topic.\n\n"
            "• Topic hint matters. 'true crime 1970s detective' gives sharper images "
            "than a blank field.\n\n"
            "• Edit the prompts. Open make_video.py, search for CARTOON_STYLES, "
            "tweak the style strings to taste.\n\n"
            "• If captions still cut off, lower max_width in render_caption_text_tight.\n\n"
            "• Reroll for variety: same script + same style + different run = different images "
            "(seeds use timestamps)."
        )
        messagebox.showinfo("Tips", tips)


def main():
    root = tk.Tk()
    app = CartoonShortsStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()

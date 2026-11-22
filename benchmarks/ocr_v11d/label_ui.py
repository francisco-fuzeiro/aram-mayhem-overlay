"""Opt-in desktop-only manual screenshot annotator for ARAM Oracle OCR V1.1d.

No capture APIs, game processes, network requests or OCR calls during import.
The only OCR button (development data) is separate and requires confirmed
human labels, a validated sealed manifest and a second explicit action.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import threading
from uuid import uuid4

from PIL import Image, ImageTk

from benchmarks.ocr_v11.runner import REFERENCE_SHA, read_cases
from benchmarks.ocr_v11d.label_core import _pixel_digest, save_confirmed_frame, title_suggestions


def fresh(prefix: str) -> str:
    return prefix + "-" + uuid4().hex[:10]


class Labeler:
    def __init__(self, root, private_root: Path, reference: Path):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.private_root = private_root.resolve()
        self.reference = reference.resolve()
        self.repository = Path(__file__).resolve().parents[2]
        from benchmarks.ocr_v11c.evaluate_local import assert_private_paths
        assert_private_paths(self.repository, [self.private_root])
        actual = subprocess.check_output(
            ["git", "-C", str(self.reference), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != REFERENCE_SHA:
            raise ValueError("pinned OCR reference is not at the verified SHA")
        cases, catalog = read_cases(self.reference)
        self.titles = set(catalog.values())
        self.frozen_hashes = {c["sha256"] for c in cases}
        frozen_source = self.reference / "tests" / "fixtures" / "ocr_titles"
        self.frozen_pixel_hashes = set()
        for case in cases:
            with Image.open(frozen_source / case["file"]) as old:
                self.frozen_pixel_hashes.add(_pixel_digest(old))
        self.image = None
        self.preview = None
        self.scale = 1.0
        self.start = None
        self.selection_rectangle = None
        self.box = None
        self.selections = {}
        self.session = tk.StringVar(value=fresh("session"))
        self.frame = tk.StringVar(value=fresh("frame"))
        self.offer = tk.StringVar(value=fresh("offer"))
        self.split = tk.StringVar(value="development")
        self.slot = tk.StringVar(value="left")
        self.category = tk.StringVar(value="title")
        self.title = tk.StringVar()
        self.rarity = tk.StringVar(value="Unknown")
        self.two_line = tk.BooleanVar(value=False)
        self.scene = tk.StringVar(value="offer")
        self.reroll = tk.StringVar(value="none")
        self.focus = tk.StringVar(value="game")
        self.opgg = tk.StringVar(value="unknown")
        self.dpi = tk.StringVar(value="unknown")
        self.status = tk.StringVar(value="Import a screenshot manually. No OCR is performed.")
        root.title("ARAM Oracle OCR V1.1d — PRIVATE human labels")
        root.geometry("1330x860")
        root.minsize(1040, 680)
        self._layout()

    def _choice(self, parent, label, var, values, row, col=0):
        ttk = self.ttk
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=4, pady=(6, 1))
        box = ttk.Combobox(parent, textvariable=var, values=list(values),
                           state="readonly", width=18)
        box.grid(row=row + 1, column=col, sticky="ew", padx=4)
        return box

    def _layout(self):
        tk, ttk = self.tk, self.ttk
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="PRIVATE / MANUAL / NO AUTO-CAPTURE",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(outer,
                  text="Choose a still screenshot, drag a rectangle around each card TITLE only, then verify names. "
                       "Never include player names or chat. Save only after human confirmation.",
                  wraplength=1250).pack(anchor="w", pady=(2, 8))
        main = ttk.Panedwindow(outer, orient="horizontal")
        main.pack(fill="both", expand=True)
        preview_area = ttk.Frame(main)
        inspector = ttk.Frame(main, width=390)
        main.add(preview_area, weight=3)
        main.add(inspector, weight=1)
        ttk.Button(preview_area, text="1. Import local screenshot...", command=self.import_image).pack(anchor="w")
        self.canvas = tk.Canvas(preview_area, bg="#1a1d24", highlightthickness=1,
                                highlightbackground="#50545c", width=820, height=510)
        self.canvas.pack(fill="both", expand=True, pady=10)
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        ttk.Label(preview_area,
                  text="Drag = crop exactly the visible title region. Repeat for left/centre/right on the SAME screenshot. "
                       "A reroll screenshot always gets a new frame ID.",
                  wraplength=760).pack(anchor="w")

        header = ttk.LabelFrame(inspector, text="Session and same-frame evidence", padding=8)
        header.pack(fill="x", pady=(0, 8))
        for caption, var in (("Session (pseudonymous)", self.session),
                             ("Offer ID", self.offer), ("Frame ID (unique screenshot)", self.frame)):
            ttk.Label(header, text=caption).pack(anchor="w")
            ttk.Entry(header, textvariable=var).pack(fill="x")
        split_line = ttk.Frame(header)
        split_line.pack(fill="x", pady=(4, 0))
        ttk.Label(split_line, text="Split (per session):").pack(side="left")
        ttk.Combobox(split_line, textvariable=self.split,
                     values=("development", "holdout"), state="readonly",
                     width=14).pack(side="left", padx=4)
        ttk.Button(header, text="New session", command=self.new_session).pack(fill="x", pady=(4, 2))
        ttk.Button(header, text="New offer", command=self.new_offer).pack(fill="x")

        fields = ttk.LabelFrame(inspector, text="2. Label one physical card crop", padding=8)
        fields.pack(fill="x", pady=(0, 8))
        self._choice(fields, "Slot", self.slot, ("left", "centre", "right"), 0, 0)
        self._choice(fields, "Type", self.category, ("title", "dialog", "no_offer"), 0, 1)
        ttk.Label(fields, text="Canonical augment title (exact catalog spelling)").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.title_box = ttk.Combobox(fields, textvariable=self.title, width=38,
                                      values=title_suggestions("", self.titles, limit=328))
        self.title_box.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.title.trace_add("write", self._suggest)
        self._choice(fields, "Rarity", self.rarity,
                     ("Silver", "Gold", "Prismatic", "Other", "Unknown"), 4, 0)
        ttk.Checkbutton(fields, text="Title has two lines",
                        variable=self.two_line).grid(row=5, column=1, rowspan=2, sticky="w")
        ttk.Button(fields, text="Add this crop to frame", command=self.add_crop).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=8)

        context = ttk.LabelFrame(inspector, text="Observed context (manual)", padding=8)
        context.pack(fill="x", pady=(0, 8))
        self._choice(context, "Scene", self.scene,
                     ("offer", "reroll", "animation", "transition", "dialog", "no_offer"), 0, 0)
        self._choice(context, "Rerolled slot", self.reroll,
                     ("none", "left", "centre", "right", "unknown"), 0, 1)
        self._choice(context, "Focus", self.focus, ("game", "alt_tab", "unknown"), 2, 0)
        self._choice(context, "OP.GG active", self.opgg, ("yes", "no", "unknown"), 2, 1)
        self._choice(context, "DPI scale (human)", self.dpi,
                     ("unknown", "100", "125", "150", "175", "200", "250", "300"), 4, 0)

        actions = ttk.Frame(inspector)
        actions.pack(fill="x")
        ttk.Button(actions, text="3. Review + confirm frame (NO OCR)",
                   command=self.confirm_frame).pack(fill="x", pady=3)
        ttk.Button(actions, text="4. Prepare private manifests (NO OCR)",
                   command=self.prepare).pack(fill="x", pady=3)
        ttk.Button(actions, text="5. Run OCR on DEVELOPMENT ONLY",
                   command=self.evaluate_development).pack(fill="x", pady=3)
        ttk.Label(inspector, textvariable=self.status, wraplength=355,
                  foreground="#597fb0").pack(fill="x", pady=8)
        ttk.Label(outer,
                  text="Outputs remain only in LOCALAPPDATA/ARAMOracle/OCR-V11c/private-captures. "
                       "Holdout remains sealed; this UI never releases it. "
                       "No League, Vanguard, OP.GG, screen capture or uploads.",
                  wraplength=1250).pack(anchor="w", pady=(10, 0))

    def _suggest(self, *_):
        query = self.title.get()
        self.title_box["values"] = title_suggestions(query, self.titles, limit=80)

    def import_image(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(title="Select already captured private image",
                 filetypes=[("Screenshots", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        try:
            source = Path(path).resolve()
            if source.is_relative_to(self.repository) or source.is_relative_to(self.reference):
                raise ValueError("Independent screenshots must be outside Git and pinned reference.")
            with Image.open(source) as original:
                self.image = original.convert("RGB")
            self.selections.clear()
            self.box = None
            self.redraw()
            self.status.set(f"Imported {self.image.width}x{self.image.height}; "
                            "drag a title crop, select slot and exact name.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Unreadable screenshot", str(exc))

    def redraw(self):
        if self.image is None:
            return
        scale = min(1.0, 900 / self.image.width, 530 / self.image.height)
        self.scale = scale
        width = max(1, round(self.image.width * scale))
        height = max(1, round(self.image.height * scale))
        self.preview = ImageTk.PhotoImage(self.image.resize((width, height)))
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, width, height))
        self.canvas.create_image(0, 0, image=self.preview, anchor="nw")
        for label, item in self.selections.items():
            x0, y0, x1, y1 = item["rect"]
            self.canvas.create_rectangle(x0 * scale, y0 * scale,
                                         x1 * scale, y1 * scale,
                                         outline="#39bd8f", width=2)
            self.canvas.create_text(x0 * scale, y0 * scale, text=label,
                                    anchor="sw", fill="#39bd8f")

    def _clamp(self, x, y):
        if self.image is None:
            return (0, 0)
        return (min(max(0, int(x / self.scale)), self.image.width),
                min(max(0, int(y / self.scale)), self.image.height))

    def press(self, event):
        if self.image is None:
            return
        self.start = self._clamp(event.x, event.y)
        self.box = None

    def drag(self, event):
        if self.start is None:
            return
        self.box = (*self.start, *self._clamp(event.x, event.y))
        self.redraw()
        a, b, c, d = self.box
        self.canvas.create_rectangle(a * self.scale, b * self.scale,
                                     c * self.scale, d * self.scale,
                                     outline="#f6c25b", width=2)

    def release(self, event):
        if self.start is None:
            return
        p = self._clamp(event.x, event.y)
        self.box = (min(self.start[0], p[0]), min(self.start[1], p[1]),
                    max(self.start[0], p[0]), max(self.start[1], p[1]))
        self.start = None
        self.redraw()
        a, b, c, d = self.box
        self.canvas.create_rectangle(a * self.scale, b * self.scale,
                                     c * self.scale, d * self.scale,
                                     outline="#f6c25b", width=2)

    def add_crop(self):
        from tkinter import messagebox
        if self.image is None or self.box is None:
            messagebox.showwarning("Crop needed", "Import an image and drag the title rectangle.")
            return
        a, b, c, d = self.box
        if a >= c or b >= d:
            messagebox.showwarning("Crop needed", "Select a nonempty title rectangle.")
            return
        category = self.category.get()
        name = self.title.get().strip() if category == "title" else ""
        if category == "title" and name not in self.titles:
            messagebox.showwarning("Exact title required",
                                   "Select the verified name from the canonical catalog.")
            return
        slot = self.slot.get()
        self.selections[slot] = {
            "slot": slot, "rect": self.box, "category": category,
            "expected": name, "rarity": self.rarity.get(),
            "two_line": bool(self.two_line.get()) if category == "title" else False,
        }
        self.status.set("Frame crops: " + ", ".join(sorted(self.selections)) +
                        ". Drag next title region or confirm this frame.")
        self.box = None
        self.redraw()

    def _context(self):
        return {"scene": self.scene.get(), "focus": self.focus.get(),
                "opgg": self.opgg.get(), "dpi": self.dpi.get(),
                "reroll": self.reroll.get()}

    def confirm_frame(self):
        from tkinter import messagebox
        if not self.selections or self.image is None:
            messagebox.showwarning("Nothing to save", "Add at least one crop first.")
            return
        summary = "\n".join(
            f"{s}: {v['category']} / {v['expected'] or '(no title)'}"
            for s, v in sorted(self.selections.items())
        )
        approved = messagebox.askyesno(
            "Human ground truth + privacy confirmation",
            f"{summary}\n\nFrame: {self.frame.get()}\nSplit: {self.split.get()}\n"
            "I visually verified every title and slot, checked privacy "
            "(no player names/chat/identifiers), and assigned the dataset split "
            "BEFORE OCR. Save private crops with approval=yes?\n\n"
            "No OCR or upload is performed."
        )
        if not approved:
            return
        try:
            count = save_confirmed_frame(
                self.image, list(self.selections.values()), self.private_root,
                repository=self.repository, catalog=self.titles,
                frozen_hashes=self.frozen_hashes,
                frozen_pixel_hashes=self.frozen_pixel_hashes,
                session=self.session.get(), frame=self.frame.get(),
                offer=self.offer.get(), split=self.split.get(),
                confirmed=True, context=self._context(),
            )
        except (ValueError, OSError) as exc:
            messagebox.showerror("Private safety gate rejected frame", str(exc))
            return
        self.selections.clear()
        self.box = None
        self.frame.set(fresh("frame"))
        self.status.set(f"Saved {count} human-confirmed crop(s) locally. "
                        "Import a NEW screenshot for the next frame. OCR not run.")
        self.redraw()

    def new_session(self):
        from tkinter import messagebox
        if self.selections and not messagebox.askyesno(
            "Discard unsaved selections?", "Discard unconfirmed crop rectangles?"
        ):
            return
        self.session.set(fresh("session"))
        self.new_offer()
        self.selections.clear()
        self.status.set("New pseudonymous session. Set split BEFORE evaluating any OCR.")

    def new_offer(self):
        self.offer.set(fresh("offer"))
        self.frame.set(fresh("frame"))
        self.selections.clear()
        self.box = None

    def prepare(self):
        from tkinter import messagebox
        labels = self.private_root / "human_labels.csv"
        if not labels.is_file():
            messagebox.showwarning("BLOCKED", "No human-confirmed crops yet.")
            return
        command = [sys.executable, "-m", "benchmarks.ocr_v11c.manifest",
                   "--labels", str(labels), "--root", str(self.private_root),
                   "--reference", str(self.reference),
                   "--out", str(self.private_root / "labels")]
        try:
            subprocess.run(command, cwd=self.repository, check=True,
                           capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            messagebox.showerror("Manifest safety gate", exc.stderr[-900:])
            return
        self.status.set("PASS — private manifests prepared. Holdout SEALED / NOT EVALUATED.")
        messagebox.showinfo("Private manifests", "Prepared and sealed outside Git. "
                            "No OCR has been run. Check split/labels before evaluation.")

    def evaluate_development(self):
        from tkinter import messagebox
        manifest = self.private_root / "labels" / "development.manifest.json"
        if not manifest.is_file():
            messagebox.showwarning("BLOCKED", "Prepare human-confirmed manifests first.")
            return
        if not messagebox.askyesno("Explicit DEVELOPMENT-only OCR",
              "This will run the five local OCR engines on DEVELOPMENT ONLY. "
              "Holdout stays sealed. Continue?"):
            return
        result = self.private_root / "results" / "development-ocr.json"
        command = [sys.executable, "-m", "benchmarks.ocr_v11c.evaluate_local",
                   "--labels-dir", str(manifest.parent),
                   "--reference", str(self.reference),
                   "--models", str(self.reference.parent / "models"),
                   "--holdout-root", str(self.private_root),
                   "--out", str(result)]
        self.status.set("Development-only OCR running locally; no upload.")
        def work():
            try:
                run = subprocess.run(command, cwd=self.repository, text=True,
                                     capture_output=True, check=False)
                if run.returncode:
                    message = "FAIL/BLOCKED: " + run.stderr[-700:]
                    self.root.after(0, lambda: self.status.set(message))
                else:
                    context_cmd = [
                        sys.executable, "-m", "benchmarks.ocr_v11d.context_report",
                        "--labels", str(self.private_root / "human_labels.csv"),
                        "--manifest", str(manifest),
                        "--result", str(result),
                        "--out", str(result.with_name("development-context-summary.json")),
                    ]
                    breakdown = subprocess.run(context_cmd, cwd=self.repository,
                                               text=True, capture_output=True, check=False)
                    if breakdown.returncode:
                        message = ("OCR PASS, contextual breakdown BLOCKED: " +
                                   breakdown.stderr[-500:])
                    else:
                        message = ("PASS — development OCR and scenario breakdown "
                                   "saved locally in private-captures/results.")
                    self.root.after(0, lambda: self.status.set(message))
            except Exception as exc:
                message = "FAIL/BLOCKED: " + str(exc)
                self.root.after(0, lambda: self.status.set(message))
        threading.Thread(target=work, daemon=True).start()


def main():
    import argparse
    import os
    from tkinter import Tk
    p = argparse.ArgumentParser(description="Manual local labels, no automatic capture")
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ARAMOracle" / "OCR-V11c"
    p.add_argument("--private-root", type=Path, default=base / "private-captures")
    p.add_argument("--reference", type=Path, default=base / "reference")
    args = p.parse_args()
    window = Tk()
    try:
        Labeler(window, args.private_root, args.reference)
    except Exception:
        window.destroy()
        raise
    window.mainloop()


if __name__ == "__main__":
    main()

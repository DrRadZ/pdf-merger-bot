from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

import fitz  # PyMuPDF
from PIL import Image, ImageTk


@dataclass
class ViewState:
    zoom: float = 1.5
    page_index: int = 0
    tool: str = "draw"  # draw | highlight | text
    draw_width: float = 2.0


class PdfAnnotatorApp(tk.Tk):
    """
    Practical PDF annotator:
      - Renders PDF pages (PyMuPDF) -> displays in Tkinter Canvas
      - Tools:
          * draw: freehand ink
          * highlight: rectangle highlight
          * note: click -> add text note (sticky note annotation)
      - Navigation: prev/next page
      - Save: writes annotations into a new PDF (in output/)
    """

    def __init__(self):
        super().__init__()
        self.title("PDF Annotator (PyMuPDF + Tkinter)")
        self.geometry("1100x800")

        self.state = ViewState()
        self.doc: fitz.Document | None = None
        self.pdf_path: Path | None = None

        self._tk_img = None  # keep reference
        self._page_pixmap = None

        # For interactions
        self._drag_start = None  # (x,y)
        self._current_highlight_rect_id = None
        self._last_draw_point = None
        self._current_stroke_points = []  # stores (x, y) canvas points

        self._build_ui()

    # ---------------- UI ----------------

    def _build_ui(self):
        top = tk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Button(top, text="Open PDF", command=self.open_pdf).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(top, text="Save As...", command=self.save_as).pack(side=tk.LEFT, padx=5, pady=5)

        tk.Button(top, text="Prev", command=self.prev_page).pack(side=tk.LEFT, padx=5)
        tk.Button(top, text="Next", command=self.next_page).pack(side=tk.LEFT, padx=5)

        tk.Label(top, text="Tool:").pack(side=tk.LEFT, padx=(15, 5))
        self.tool_var = tk.StringVar(value=self.state.tool)
        for tool in ("draw", "highlight", "text"):
            tk.Radiobutton(top, text=tool.capitalize(), variable=self.tool_var, value=tool,
                           command=self._set_tool).pack(side=tk.LEFT)

        tk.Label(top, text="Zoom:").pack(side=tk.LEFT, padx=(15, 5))
        self.zoom_var = tk.DoubleVar(value=self.state.zoom)
        tk.Spinbox(top, from_=0.5, to=4.0, increment=0.1, textvariable=self.zoom_var,
                   width=5, command=self._apply_zoom).pack(side=tk.LEFT)

        self.page_label = tk.Label(top, text="Page: - / -")
        self.page_label.pack(side=tk.RIGHT, padx=10)

        # Canvas with scrollbars
        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(container, bg="gray20")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        hbar = tk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        # Mouse bindings
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Keyboard shortcuts
        self.bind("<Left>", lambda e: self.prev_page())
        self.bind("<Right>", lambda e: self.next_page())
        self.bind("<Control-s>", lambda e: self.save_as())

    # ---------------- PDF open/render ----------------

    def open_pdf(self):
        file_path = filedialog.askopenfilename(
            title="Open PDF",
            filetypes=[("PDF files", "*.pdf")]
        )
        if not file_path:
            return

        try:
            self.doc = fitz.open(file_path)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))
            return

        self.pdf_path = Path(file_path)
        self.state.page_index = 0
        self._render_page()

    def _render_page(self):
        if not self.doc:
            return

        page_count = self.doc.page_count
        self.state.page_index = max(0, min(self.state.page_index, page_count - 1))
        page = self.doc[self.state.page_index]

        self.state.zoom = float(self.zoom_var.get())
        mat = fitz.Matrix(self.state.zoom, self.state.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        self._page_pixmap = pix
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._tk_img = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img, tags="PAGE")
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))

        self.page_label.config(text=f"Page: {self.state.page_index + 1} / {page_count}")

    # ---------------- Navigation ----------------

    def prev_page(self):
        if not self.doc:
            return
        self.state.page_index -= 1
        self._render_page()

    def next_page(self):
        if not self.doc:
            return
        self.state.page_index += 1
        self._render_page()

    # ---------------- Tool control ----------------

    def _set_tool(self):
        self.state.tool = self.tool_var.get()

    def _apply_zoom(self):
        if self.doc:
            self._render_page()

    # ---------------- Coordinate mapping ----------------

    def _canvas_to_pdf(self, x: float, y: float) -> tuple[float, float]:
        """
        Canvas coords -> PDF coords.
        We render with zoom factor, so PDF coords are canvas / zoom.
        """
        z = self.state.zoom
        return (x / z, y / z)

    # ---------------- Mouse events ----------------

    def on_mouse_down(self, event):
        if not self.doc:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        tool = self.state.tool
        if tool == "draw":
            self._current_stroke_points = [(x, y)]
            self._last_draw_point = (x, y)

        elif tool == "highlight":
            self._drag_start = (x, y)
            # temporary rectangle on canvas (visual feedback only)
            self._current_highlight_rect_id = self.canvas.create_rectangle(
                x, y, x, y, outline="yellow", width=2
            )


        elif tool == "text":

            text_value = simpledialog.askstring("Add Text", "Type the text to place on the PDF:")
            if not text_value:
                return
            self._add_text_at_canvas_point(x, y, text_value)
            self._render_page()

    def on_mouse_drag(self, event):
        if not self.doc:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        tool = self.state.tool
        if tool == "draw" and self._last_draw_point is not None:
            x0, y0 = self._last_draw_point
            self.canvas.create_line(
                x0, y0, x, y,
                fill="red",
                width=2,
                capstyle=tk.ROUND,
                smooth=True,
                tags="INK_TMP"
            )
            self._last_draw_point = (x, y)
            self._current_stroke_points.append((x, y))

        elif tool == "highlight" and self._drag_start and self._current_highlight_rect_id:
            x0, y0 = self._drag_start
            self.canvas.coords(self._current_highlight_rect_id, x0, y0, x, y)

    def on_mouse_up(self, event):
        if not self.doc:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        tool = self.state.tool
        if tool == "draw":
            self._finalize_draw_stroke()
            self._last_draw_point = None
            self._render_page()

        elif tool == "highlight" and self._drag_start:
            x0, y0 = self._drag_start
            self._drag_start = None

            # Remove temp rectangle
            if self._current_highlight_rect_id:
                self.canvas.delete(self._current_highlight_rect_id)
                self._current_highlight_rect_id = None

            # Add PDF highlight annotation (rect)
            self._add_highlight_rect(x0, y0, x, y)
            self._render_page()

    # ---------------- Annotation writers ----------------

    def _add_highlight_rect(self, x0, y0, x1, y1):
        if not self.doc:
            return
        page = self.doc[self.state.page_index]

        # Normalize rectangle
        left, right = sorted([x0, x1])
        top, bottom = sorted([y0, y1])

        # Map canvas -> PDF coords
        px0, py0 = self._canvas_to_pdf(left, top)
        px1, py1 = self._canvas_to_pdf(right, bottom)

        rect = fitz.Rect(px0, py0, px1, py1)
        annot = page.add_highlight_annot(rect)
        annot.update()

    def _add_text_at_canvas_point(self, x, y, text: str):
        """
        Places visible text directly on the PDF page using a FreeText annotation.
        """
        if not self.doc:
            return

        page = self.doc[self.state.page_index]
        px, py = self._canvas_to_pdf(x, y)

        # Define a rectangle where the text will appear.
        # You can tweak width/height depending on your preference.
        rect_width = 250
        rect_height = 40
        rect = fitz.Rect(px, py, px + rect_width, py + rect_height)

        annot = page.add_freetext_annot(
            rect,
            text,
            fontsize=12,
            fontname="helv"  # built-in Helvetica
        )

        # Optional: make it look like plain text (no border/fill)
        annot.set_colors(stroke=None, fill=None)  # no border, no background
        annot.update()

    def _add_note_at_canvas_point(self, x, y, text: str):
        if not self.doc:
            return
        page = self.doc[self.state.page_index]
        px, py = self._canvas_to_pdf(x, y)

        annot = page.add_text_annot((px, py), text)
        annot.update()

    def _finalize_draw_stroke(self):
        """
        Convert the collected stroke points into ONE ink annotation.
        """
        if not self.doc or len(self._current_stroke_points) < 2:
            return

        page = self.doc[self.state.page_index]

        # Convert canvas points -> PDF points
        stroke_pdf_points = [
            self._canvas_to_pdf(x, y) for (x, y) in self._current_stroke_points
        ]

        # Ink annotation expects a list of strokes
        annot = page.add_ink_annot([stroke_pdf_points])
        annot.set_border(width=self.state.draw_width)
        annot.update()

        # Cleanup
        self.canvas.delete("INK_TMP")
        self._current_stroke_points = []

    # ---------------- Saving ----------------

    def save_as(self):
        if not self.doc or not self.pdf_path:
            messagebox.showinfo("Nothing to save", "Open a PDF first.")
            return

        default_name = f"{self.pdf_path.stem}_annotated_{int(time.time())}.pdf"
        out_path = filedialog.asksaveasfilename(
            title="Save Annotated PDF As",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf")]
        )
        if not out_path:
            return

        try:
            # Save a full copy with annotations embedded
            self.doc.save(out_path)
            messagebox.showinfo("Saved", f"Saved annotated PDF:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))


if __name__ == "__main__":
    app = PdfAnnotatorApp()
    app.mainloop()

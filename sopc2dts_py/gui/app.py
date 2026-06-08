# sopc2dts - Devicetree generation for Altera systems
#
# Python port Copyright (C) 2026 Laurence <laurence@anodes4life.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
FastAPI application for the sopc2dts web GUI.

Single-user — state is a module-level singleton (this is a local desktop tool,
not a multi-tenant web service).
"""

from __future__ import annotations

import asyncio
import logging
import queue
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

class _AppState:
    def __init__(self) -> None:
        self.prefill_input: str = ""
        self.system = None          # AvalonSystem | None
        self.boardinfo = None       # BoardInfo | None  (None = use fresh default)
        self.boardinfo_path: str = ""  # last successfully loaded board file
        self.last_output: Optional[bytes | str] = None
        self.last_output_type: str = "dts"


state = _AppState()

# ---------------------------------------------------------------------------
# Log capture — intercept the root logger and feed a queue for SSE streaming
# ---------------------------------------------------------------------------

_log_queue: queue.Queue[str] = queue.Queue(maxsize=500)


class _GUILogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _log_queue.put_nowait(self.format(record))
        except queue.Full:
            pass


_gui_handler = _GUILogHandler()
_gui_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(_gui_handler)

# ---------------------------------------------------------------------------
# FastAPI app + Jinja2 templates
# ---------------------------------------------------------------------------

app = FastAPI(title="sopc2dts GUI", docs_url=None, redoc_url=None)
_tpl_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_tpl_dir))

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Launcher polls this to know the server is ready."""
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Main page.  Auto-loads the system if -i was given on the CLI."""
    if state.prefill_input and state.system is None:
        _do_load(state.prefill_input)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "prefill_input": state.prefill_input,
            "boardinfo_path": state.boardinfo_path,
            "system_html": _render_system_html() if state.system else "",
        },
    )


@app.post("/load", response_class=HTMLResponse)
async def load(input_path: str = Form(...)) -> HTMLResponse:
    """Parse a sopcinfo / qsys file and return the system-section fragment."""
    err = _do_load(input_path.strip())
    if err:
        return HTMLResponse(f'<p class="err">Error: {err}</p>')
    return HTMLResponse(_render_system_html())


@app.post("/load-board", response_class=HTMLResponse)
async def load_board(board_path: str = Form(...)) -> HTMLResponse:
    """Load a boardinfo XML file and return a status fragment."""
    board_path = board_path.strip()
    if not board_path:
        # Clear board — revert to default
        state.boardinfo = None
        state.boardinfo_path = ""
        return HTMLResponse('<span class="ok">Using default board settings.</span>')

    p = Path(board_path)
    if not p.exists():
        return HTMLResponse(f'<span class="err">File not found: {board_path}</span>')
    try:
        from ..parsers import load_boardinfo  # noqa: PLC0415
        state.boardinfo = load_boardinfo(str(p))
        state.boardinfo_path = board_path
        return HTMLResponse(f'<span class="ok">&#x2713; Loaded: {p.name}</span>')
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(f'<span class="err">Error: {exc}</span>')


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    output_type: str = Form("dts"),
    pov: str = Form(""),
    sort: str = Form(""),
    show_clocks: Optional[str] = Form(None),
    no_timestamp: Optional[str] = Form(None),
) -> HTMLResponse:
    """Run the selected generator and return the output-section fragment."""
    if state.system is None:
        return HTMLResponse('<p class="err">No system loaded.</p>')

    err, output = _do_generate(
        output_type=output_type,
        pov=pov.strip(),
        sort=sort,
        show_clocks=show_clocks is not None,
        no_timestamp=no_timestamp is not None,
    )
    if err:
        return HTMLResponse(f'<p class="err">Error: {err}</p>')

    state.last_output = output
    state.last_output_type = output_type

    if isinstance(output, bytes):
        return HTMLResponse(
            f'<p>Binary output &mdash; {len(output):,} bytes. '
            f'<a href="/download" download="output.{_ext(output_type)}">'
            f'&#x2B07; Download</a></p>'
        )

    escaped = (output or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(
        f'<textarea rows="30" spellcheck="false">{escaped}</textarea>'
    )


@app.get("/download")
def download() -> Response:
    """Serve the last generated binary output as a file download."""
    if state.last_output is None:
        return Response("No output available.", status_code=404)
    content = (
        state.last_output
        if isinstance(state.last_output, bytes)
        else state.last_output.encode("utf-8")
    )
    filename = f"output.{_ext(state.last_output_type)}"
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/log/stream")
async def log_stream() -> StreamingResponse:
    """SSE endpoint — streams log messages to the browser log panel."""

    async def _events():
        while True:
            try:
                msg = _log_queue.get_nowait()
                msg = msg.replace("\n", " ")  # SSE data must be single-line
                yield f"data: {msg}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.25)
                yield ": keepalive\n\n"

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _do_load(input_path: str) -> Optional[str]:
    """Parse input file into state.system.  Returns an error string or None."""
    from ..parsers import load_system, load_component_libs_in_dir  # noqa: PLC0415

    p = Path(input_path)
    if not p.exists():
        return f"File not found: {input_path}"
    try:
        lib_dir = Path(__file__).parent.parent.parent
        load_component_libs_in_dir(lib_dir)
        state.system = load_system(str(p))
        state.system.recheck_components()
        state.prefill_input = input_path
        from ..model.boardinfo import BoardInfo  # noqa: PLC0415
        state.boardinfo = BoardInfo()
        return None
    except Exception as exc:  # noqa: BLE001
        return str(exc)


def _do_generate(
    output_type: str,
    pov: str,
    sort: str,
    show_clocks: bool,
    no_timestamp: bool,
) -> tuple[Optional[str], Optional[bytes | str]]:
    """Run the generator.  Returns (error_str | None, output | None)."""
    from ..model.boardinfo import BoardInfo, SortType  # noqa: PLC0415
    from ..generators.GeneratorFactory import GeneratorFactory  # noqa: PLC0415

    bi = state.boardinfo or BoardInfo()
    if pov:
        bi.set_pov(pov)
    if sort:
        bi.set_sort_type({
            "address": SortType.ADDRESS,
            "name":    SortType.NAME,
            "label":   SortType.LABEL,
        }.get(sort, SortType.NONE))
    bi.show_clock_tree = show_clocks
    bi.include_time = not no_timestamp

    gen_type = GeneratorFactory.get_type_by_name(output_type)
    if gen_type is None:
        return f"Unknown output type: {output_type}", None

    generator = GeneratorFactory.create_generator_for(state.system, gen_type)
    if generator is None:
        return f"No generator for: {output_type}", None

    try:
        if generator.is_text_output():
            return None, generator.get_text_output(bi)
        return None, generator.get_binary_output(bi)
    except Exception as exc:  # noqa: BLE001
        return str(exc), None


def _render_system_html() -> str:
    """Build the system-section inner HTML from current state."""
    sys = state.system
    if sys is None:
        return "<p>No system loaded.</p>"

    rows = "\n".join(
        f"<tr><td>{c.instance_name}</td>"
        f"<td>{c.class_name}</td>"
        f"<td>{c.scd.group}</td></tr>"
        for c in sys.components
    )

    type_options = "\n".join(
        f'<option value="{v}">{label}</option>'
        for v, label in [
            ("dts",          "DTS — Device Tree Source"),
            ("dtb",          "DTB — Binary (requires dtc)"),
            ("dtb-ihex8",    "DTB Intel I8Hex"),
            ("dtb-ihex32",   "DTB Intel I32Hex"),
            ("dtb-char-arr", "DTB C char array"),
            ("kernel",       "Kernel CMacro headers"),
            ("uboot",        "U-Boot headers"),
            ("sopc-header",  "sopc-create-header-files"),
            ("graph",        "Graphviz dot"),
        ]
    )

    return f"""
<h2>System: <code>{sys.name}</code> &mdash; {len(sys.components)} components</h2>
<details>
  <summary>Component list</summary>
  <table>
    <thead><tr><th>Instance</th><th>Class</th><th>Group</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</details>

<hr>
<h3>Generate</h3>
<form hx-post="/generate" hx-target="#output-section" hx-swap="innerHTML"
      hx-indicator="#spinner">
  <div class="row">
    <label>Output type</label>
    <select name="output_type">{type_options}</select>
  </div>
  <div class="row">
    <label>POV component</label>
    <input name="pov" type="text" placeholder="auto-detect first CPU">
  </div>
  <div class="row">
    <label>Sort</label>
    <select name="sort">
      <option value="">default</option>
      <option value="address">address</option>
      <option value="name">name</option>
      <option value="label">label</option>
    </select>
  </div>
  <div class="row">
    <label></label>
    <span>
      <label><input type="checkbox" name="show_clocks"> show clocks</label>
      &nbsp;
      <label><input type="checkbox" name="no_timestamp"> no timestamp</label>
    </span>
  </div>
  <div class="row">
    <label></label>
    <button type="submit">Generate</button>
    <span id="spinner" class="htmx-indicator"> &#x23F3; generating…</span>
  </div>
</form>
"""


_EXT_MAP: dict[str, str] = {
    "dts":          "dts",
    "dtb":          "dtb",
    "dtb-ihex8":    "hex",
    "dtb-ihex32":   "hex",
    "dtb-char-arr": "h",
    "kernel":       "h",
    "uboot":        "h",
    "sopc-header":  "h",
    "graph":        "dot",
}


def _ext(output_type: str) -> str:
    return _EXT_MAP.get(output_type, "bin")

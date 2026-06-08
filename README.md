sopc2dts
========

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)

Tool to generate a Linux devicetree (DTS/DTB) from an Altera/Intel FPGA sopcinfo or Qsys file.

This is a Python port and modernisation of the original Java tool by Walter Goossens.
See [NOTICE](./NOTICE) for original authorship and licensing details.

> **Work in progress.** Do NOT use in production yet.  
> Track progress in [docs/PORTING.md](./docs/PORTING.md).

## License

This project is licensed under the [GNU General Public License v3.0](./COPYING) or later.  
The original Java codebase was licensed under LGPLv2.1; this port is redistributed under GPLv3
per LGPLv2.1 Section 3.

## Known Bugs

Bugs are tracked as [GitHub Issues](https://github.com/LaurenceA4L/sopc2dts/issues?q=is%3Aissue+is%3Aopen+label%3Abug).
Use the 👍 reaction on an issue to upvote it (one per account) — high-vote bugs get fixed first.

| # | Component | Summary | Workaround |
|---|-----------|---------|------------|
| [#1](https://github.com/LaurenceA4L/sopc2dts/issues/1) | GUI / Windows | `Ctrl+C` in PowerShell does not stop the uvicorn server | Close the browser tab — the server exits when the last SSE connection drops |

To report a new bug, open an issue and label it `bug`.

---

Thank you for your interest in this project. Please check in again soon to see the latest progress!

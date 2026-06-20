# arcbench

Intel Arc GPU benchmark console for Linux — a guided TUI for running, validating, and sharing GPU benchmark results.

```
arcbench
```

Built for Intel Arc GPU owners on Linux who want comparable, shareable results without memorizing CLI flags.

---

## Features

- **System preflight** — detects GPU, oneAPI, llama-bench, and telemetry availability on launch
- **Guided benchmark runner** — preset configurations matching the [Intel-Arc-GPU-Benchmarks](https://github.com/Wesley-Jakob-Gilbert/Intel-Arc-GPU-Benchmarks) repo format
- **Live telemetry** — GPU VRAM, CPU, RAM monitoring during benchmark runs
- **Result validation** — checks for SYCL backend, both pp/tg rows, and GPU activity
- **Repo-compatible export** — Markdown output ready for GitHub contribution

---

## Quick start

### Prerequisites

- Ubuntu 22.04+ or Debian 12+
- Intel Arc GPU with xe driver
- Intel oneAPI BaseKit (`/opt/intel/oneapi/setvars.sh`)
- `llama-bench` built with SYCL backend (see [setup guide](https://github.com/Wesley-Jakob-Gilbert/Intel-Arc-GPU-Benchmarks/blob/main/setup/ubuntu-26.04.md))

### Install

**Option A — `uv` (recommended, fastest)**

`uv` manages its own isolated environment automatically. No manual venv activation needed.

```bash
git clone https://github.com/Wesley-Jakob-Gilbert/arcbench
cd arcbench
uv venv              # creates .venv/ in the project directory
source .venv/bin/activate
uv pip install -e .
arcbench
```

> **Important:** `uv pip install` installs into whichever environment is currently active.
> If you run it without activating the venv first, the package lands in your system Python
> and the `arcbench` command may not be on your PATH (or may conflict with system packages).
> Always `source .venv/bin/activate` before installing or running.

To re-enter the environment in a new shell:

```bash
cd arcbench
source .venv/bin/activate
arcbench
```

**Option B — `pipx` (install once, run anywhere)**

`pipx` creates and manages the venv for you — no activation step ever needed.

```bash
pipx install git+https://github.com/Wesley-Jakob-Gilbert/arcbench
arcbench
```

**Option C — standard `pip` from source**

```bash
git clone https://github.com/Wesley-Jakob-Gilbert/arcbench
cd arcbench
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
arcbench
```

---

## Benchmark coverage

### Machine Learning (llama.cpp SYCL)

| Preset | Model | Size | Notes |
|---|---|---|---|
| Llama 3.1 8B Q4_K_M | Meta-Llama-3.1-8B-Instruct | 4.58 GiB | Quick sanity + repo standard |
| Llama 3.1 8B Q5_K_M | Meta-Llama-3.1-8B-Instruct | 5.33 GiB | Higher quality |
| Llama 3.1 8B Q8_0 | Meta-Llama-3.1-8B-Instruct | 7.95 GiB | Memory bandwidth wall demo |
| Llama 3.1 70B Q2_K | Meta-Llama-3.1-70B-Instruct | 24.56 GiB | Largest all-GPU fit on 32GB |
| Llama 3.1 70B IQ3_XS | Meta-Llama-3.1-70B-Instruct | 27.29 GiB | 3.3bpw, all-GPU |
| Llama 3.1 70B Q4_K_M hybrid | Meta-Llama-3.1-70B-Instruct | 39.59 GiB | Hybrid CPU+GPU — ngl 60 |

### Coming soon

- Blender benchmark runner
- GROMACS / HPC workloads
- Multi-GPU configurations

---

## Project structure

```
arcbench/
  arcbench/
    app.py              # Textual app entry point
    screens/
      welcome.py        # System scan
      home.py           # Dashboard + category select
      category.py       # Benchmark list + detail panel
      running.py        # Live benchmark + telemetry
      completion.py     # Results + export
    workers/
      benchmark.py      # llama-bench subprocess management
      telemetry.py      # GPU/CPU/RAM polling
    data/
      system.py         # Hardware/software detection
      manifest.py       # Benchmark preset loader
      results.py        # Local result storage
  benchmarks/
    llama_cpp/
      llama31.yaml      # Llama 3.1 preset definitions
```

---

## Contributing benchmarks

Results are contributed to the [Intel-Arc-GPU-Benchmarks](https://github.com/Wesley-Jakob-Gilbert/Intel-Arc-GPU-Benchmarks) repo.

arcbench exports a Markdown file with:
- Repo-format table row
- Hardware/software manifest
- Exact command used
- Raw llama-bench output

Open a PR at the benchmarks repo and drop the exported file in the appropriate `results/` subdirectory.

---

## License

MIT

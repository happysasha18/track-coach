# track-coach — Installation Troubleshooting (macOS)

## Quick reference: manual commands

If setup.sh fails at a step, here are the exact commands for each piece.

### ffmpeg (requires Homebrew)

```bash
brew install ffmpeg
```

If brew is not installed:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
This will ask for your Mac login password. Claude cannot enter passwords — you run this yourself.

After installing brew, run `brew install ffmpeg`.

### uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart your terminal (or run `source ~/.zshrc` / `source ~/.bashrc`).

### Create the virtual environment manually

```bash
cd /path/to/track-coach
uv venv .venv --python 3.11
```

### Install Python dependencies manually

```bash
cd /path/to/track-coach
uv pip install --python .venv/bin/python -r requirements.txt
```

---

## Common issues

### "ffmpeg not found" after installing

The ffmpeg binary may not be on your PATH yet. Try:
```bash
export PATH="/opt/homebrew/bin:$PATH"   # Apple Silicon Mac
# or:
export PATH="/usr/local/bin:$PATH"      # Intel Mac
```
Add the correct line to your `~/.zshrc` to make it permanent.

### numpy 2.x conflict with librosa

librosa 0.10.x has a known incompatibility with numpy 2.0+. If you see errors like
`AttributeError: module 'numpy' has no attribute 'float'`, check:
```bash
.venv/bin/python -c "import numpy; print(numpy.__version__)"
```
Should be `1.26.4`. If not:
```bash
uv pip install --python .venv/bin/python "numpy==1.26.4" --force-reinstall
```

### torch download takes too long / fails

PyTorch CPU build is ~200 MB. On slow connections this may time out.
Try downloading manually:
```bash
# Check the correct wheel URL for your Python version at https://pytorch.org/get-started/locally/
# Example for Python 3.11, macOS, CPU:
uv pip install --python .venv/bin/python torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu
```

### Demucs model download fails

Demucs downloads the `htdemucs` model (~80 MB) on first run. If you're offline or on a metered connection, this will fail. The model is cached at:
```
~/.cache/torch/hub/checkpoints/
```
You can pre-download it on a good connection and it won't re-download.

### "Permission denied" on setup.sh

Make it executable:
```bash
chmod +x /path/to/track-coach/setup.sh
```

### Apple MPS vs CPU

MPS (Metal Performance Shaders — Apple GPU acceleration) is auto-detected and optional. If you see MPS errors, the scripts will fall back to CPU automatically. To force CPU explicitly:
```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 python scripts/separate.py ...
```

### check_env.py exits with errors but everything seems installed

Make sure you're using the venv Python, not the system Python:
```bash
.venv/bin/python scripts/check_env.py
# NOT: python scripts/check_env.py
```

---

## Platform note

track-coach v1 is macOS only. Setup has been tested on macOS with Homebrew.
Linux/Windows support is not claimed and has not been tested.

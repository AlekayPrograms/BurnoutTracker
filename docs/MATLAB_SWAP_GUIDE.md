# MATLAB Swap-In Guide

## Current Architecture

All charts are generated in `src/ui/plot_backend.py`. Each function:
1. Takes data as input (sessions list, stats dict)
2. Creates a matplotlib figure
3. Saves it as PNG to `src/assets/plots/`
4. Returns a `QPixmap` for display

## How to Swap to MATLAB

### Prerequisites
- MATLAB R2021b+ installed
- MATLAB Engine API for Python: `cd "C:\Program Files\MATLAB\R2024a\extern\engines\python" && pip install .`

### Steps

1. **Install MATLAB Engine**
   ```
   pip install matlabengine
   ```

2. **Create MATLAB scripts** in `matlab/` folder, one per chart:
   - `plot_sessions_over_time.m`
   - `plot_focus_metrics.m`
   - `plot_focus_block_histogram.m`
   - `plot_burnout_procrastination_timing.m`
   - `plot_focus_ratio_trend.m`
   - `plot_category_comparison.m`

3. **Each MATLAB script should:**
   - Accept data via `load('temp_data.mat')`
   - Apply dark theme (see template below)
   - Save to `src/assets/plots/<name>.png`

4. **Replace each function in `plot_backend.py`:**

```python
import matlab.engine

_eng = None

def _get_engine():
    global _eng
    if _eng is None:
        _eng = matlab.engine.start_matlab()
        _eng.addpath('matlab/', nargout=0)
    return _eng

def plot_sessions_over_time(sessions):
    eng = _get_engine()
    # Export data to temp .mat file
    dates = [s.start_time.isoformat() for s in sessions if s.start_time]
    scipy.io.savemat('temp_data.mat', {'dates': dates})

    eng.plot_sessions_over_time(nargout=0)

    path = Path('src/assets/plots/sessions_over_time.png')
    return QPixmap(str(path))
```

### MATLAB Dark Theme Template

```matlab
function apply_dark_theme()
    set(gcf, 'Color', [0.118 0.118 0.180]);
    set(gca, 'Color', [0.118 0.118 0.180]);
    set(gca, 'XColor', [0.651 0.659 0.741]);
    set(gca, 'YColor', [0.651 0.659 0.741]);
    set(gca, 'GridColor', [0.192 0.196 0.267]);
    set(gca, 'GridAlpha', 0.5);
    title(gca, gca.Title.String, 'Color', [0.804 0.839 0.957]);
end
```

### Key Notes
- The swap only changes `plot_backend.py` - no other file is affected
- The QPixmap interface stays the same
- MATLAB figures can be higher quality (vector-based export)
- Consider caching: MATLAB startup is slow (~5s), reuse the engine

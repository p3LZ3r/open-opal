# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Zero-Dep** (Zero Dependency) is a Windows application that transforms Luxonis OAK devices into fully configurable virtual webcams. The project provides a single-installer solution that bypasses OAK's hardware UVC limitations to enable simultaneous video streaming and XLink control (AI features, manual focus, exposure, white balance).

**Current Status:** Planning phase - comprehensive PRD complete ([PRD.md](PRD.md) in German), no source code implementation yet.

## Architecture: Three-Layer System

The solution avoids the OAK's native UVC mode (which blocks XLink) by implementing a host-side software bridge:

```
┌─────────────────────────────────────────────┐
│ OAK Device (Firmware Layer)                 │
│  Pipeline: ColorCamera → ImageManip →       │
│            XLinkOut (RGB frames)             │
└────────────────┬────────────────────────────┘
                 │ USB 3.0 (XLink Protocol)
┌────────────────▼────────────────────────────┐
│ Host Application (Python Bridge)            │
│  - Receives frames via depthai/XLink        │
│  - Writes to shared memory (pyvirtualcam)   │
│  - Provides GUI for camera controls         │
│  - Handles device reconnection              │
└────────────────┬────────────────────────────┘
                 │ Shared Memory (OAKCamMemory)
┌────────────────▼────────────────────────────┐
│ Virtual DirectShow Driver (C++ DLLs)        │
│  - Modified Unity Capture (MIT license)     │
│  - Registers as "OAK Smart Cam"             │
│  - Reads from shared memory                 │
│  - Presents frames as RGB24 DirectShow      │
└────────────────┬────────────────────────────┘
                 │ DirectShow Interface
┌────────────────▼────────────────────────────┐
│ Windows Applications (Zoom, Teams, etc.)    │
└─────────────────────────────────────────────┘
```

## Technology Stack

**Host Application:**
- Python 3.14+ (packaged with PyInstaller)
- `depthai` - OAK device communication
- `pyvirtualcam` - Shared memory abstraction
- PyQt6 - GUI framework
- Threading model: GUI thread + Pipeline thread (continuous capture/transmission)

**Virtual Driver:**
- C++ DirectShow filter (based on Unity Capture)
- Two builds required: x86 (32-bit) and x64 (64-bit)
- User-mode operation (no kernel driver complexity)
- Registered via regsvr32 as COM object

**Installation:**
- Inno Setup - Orchestrates complete installation
- Bundles VC++ Runtime (vc_redist.x64.exe)
- Single Setup.exe - no pre-installed dependencies required

## Development Commands

### C++ Driver Build (Visual Studio)
```bash
# Build both architectures
msbuild DirectShow/OAKSmartCam.sln /p:Configuration=Release /p:Platform=x64
msbuild DirectShow/OAKSmartCam.sln /p:Configuration=Release /p:Platform=Win32

# Manual testing - register DLLs (requires admin)
regsvr32 "path\to\ZeroDepCam64.dll"
regsvr32 "path\to\ZeroDepCam32.dll"

# Unregister (for cleanup)
regsvr32 /u "path\to\ZeroDepCam64.dll"
```

### Python Host Application
```bash
# Development setup
python -m venv venv
venv\Scripts\activate
pip install depthai pyvirtualcam pyqt5

# Run development version
python src/python/main.py

# Build with PyInstaller (creates OAK_Controller.exe)
pyinstaller --noconfirm --onedir --windowed ^
  --add-data "assets/*;assets/" ^
  src/python/main.py

# Note: Use --onedir (not --onefile) for faster startup and AV compatibility
```

### Installer Build (Inno Setup)
```bash
# Compile installer (requires Inno Setup installed)
iscc installer/setup.iss

# Output: Setup.exe in installer/Output/
```

## Critical Implementation Details

### Why Not UVC Mode?
The OAK's native UVC node blocks XLink when active (USB resource conflict - Windows usbvideo.sys takes exclusive control). This prevents simultaneous video streaming and AI/control features. The XLink-only approach with software virtualization solves this limitation.

### Why DirectShow (Not Media Foundation or Kernel Driver)?
- **DirectShow:** Universal compatibility (Zoom, Teams, Skype), user-mode, simple regsvr32 registration, proven by OBS/ManyCam
- **Media Foundation:** Poor virtual source support, limited legacy app compatibility
- **Kernel Driver:** Requires EV code signing, risk of BSOD, excessive complexity

### OAK Pipeline Configuration
```python
# On-device pipeline (avoids host CPU conversion overhead)
cam = pipeline.create(dai.node.ColorCamera)
manip = pipeline.create(dai.node.ImageManip)  # RGB conversion on VPU
xout = pipeline.create(dai.node.XLinkOut)

cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
cam.setInterleaved(True)  # RGB interleaved format
manip.setMaxOutputFrameSize(1920*1080*3)
cam.preview.link(manip.inputImage)
manip.out.link(xout.input)
```

### Threading Architecture
- **Thread 1 (GUI):** Handles user input (sliders, buttons), non-blocking
- **Thread 2 (Pipeline):** Continuous loop - `queue.get()` from OAK → `cam.send()` to shared memory
- **Synchronization:** Python `queue.Queue` for thread-safe control message passing
- **Reconnection:** Background polling for `dai.Device.getAllAvailableDevices()` on disconnect

### Performance Budget
- **Latency Target:** <200ms (glass-to-glass for lip-sync)
  - Sensor: ~30ms | ISP/VPU: ~10-20ms | USB: ~5-10ms | Host: ~5ms | Driver: ~5ms
- **Bandwidth:** 1080p RGB30 = ~186 MB/s (USB 3.0 capable)
- **USB 2.0 Fallback:** Auto-switch to MJPEG encoding on device when `device.getUsbSpeed() == USB2`

### Driver Modifications (Unity Capture Fork)
When forking Unity Capture, change:
1. **GUIDs:** Generate new `CLSID_UnityCapture` and `CLSID_VirtualCam` (avoid conflicts)
2. **Device Name:** `"Unity Video Capture"` → `"OAK Smart Cam"`
3. **Shared Memory Key:** `UnityCaptureMemory` → `OAKCamMemory`
4. **Registry Paths:** Custom paths in `DllRegisterServer()`

### Camera Controls (CameraControl API)
```python
# Manual focus (lens position 0-255)
ctrl = dai.CameraControl()
ctrl.setManualFocus(lens_position)
control_queue.send(ctrl)

# Manual exposure (time in microseconds, ISO sensitivity)
ctrl.setManualExposure(exposure_time_us, iso_sensitivity)

# White balance (color temperature in Kelvin, 1000-12000)
ctrl.setManualWhiteBalance(color_temp_k)

# Autofocus trigger
ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.AUTO)
ctrl.setAutoFocusTrigger()
```

## Installation Orchestration

The Inno Setup installer must execute steps in this exact order:

1. **Admin Rights Check:** `PrivilegesRequired=admin` (required for Program Files and COM registration)
2. **File Copy:** All files to `{app}` (e.g., `C:\Program Files\OAK Smart Cam`)
3. **VC++ Runtime Check:** Query registry `HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64`
4. **Silent Runtime Install:** `vc_redist.x64.exe /install /quiet /norestart` (if needed)
5. **DLL Registration:**
   ```
   regsvr32.exe /s "{app}\drivers\ZeroDepCam64.dll"
   regsvr32.exe /s "{app}\drivers\ZeroDepCam32.dll"
   ```
6. **Uninstall:** Must deregister DLLs (`regsvr32 /u /s`) BEFORE file deletion

## Security and Signing

**Code Signing Required:**
- Unsigned installers/DLLs trigger Windows SmartScreen and Defender false positives
- PyInstaller bundles are particularly susceptible to AV flagging
- Minimum: OV (Organization Validation) certificate
- Sign: Both DLLs, the host EXE, and the final Setup.exe installer
- Tool: `signtool.exe` (Windows SDK)
- Recommended: Submit to Microsoft for analysis to prevent Defender warnings

## Testing Requirements

| Scenario                  | Expected Behavior                                                                        |
| ------------------------- | ---------------------------------------------------------------------------------------- |
| Clean Install (Win 10/11) | No errors, VCRedist auto-installs, camera appears in Zoom immediately                    |
| Upgrade Install           | Old files replaced, DLLs re-registered successfully                                      |
| USB Hot-Unplug            | App shows "Connecting..." status, Zoom doesn't crash (shows last frame or logo)          |
| Multi-App Access          | Zoom + OBS can use same virtual camera simultaneously (driver must support multi-client) |
| Antivirus Scan            | Installation not blocked, no false positives (requires code signing)                     |

**Latency Testing:** Measure with high-speed camera recording monitor + physical scene for glass-to-glass validation.

**USB Bandwidth Testing:** Validate 1080p@30fps on USB 3.0, verify automatic MJPEG fallback on USB 2.0.

## Key Constraints

**Out of Scope:**
- Audio routing (use system microphone or OAK's USB audio separately)
- Linux/macOS support (Windows-specific DirectShow architecture)
- Multi-camera support in initial release (single OAK device)

**Language:** PRD and technical documentation in German. Code comments and user-facing strings in English is acceptable for international compatibility.

## DirectShow Registry Structure

After registration, the driver appears at:
- 64-bit: `HKEY_CLASSES_ROOT\CLSID\{GUID}\Instance`
- 32-bit: `HKEY_CLASSES_ROOT\WOW6432Node\CLSID\{GUID}\Instance`
- Category: Video Input Device `{860BB310-5D01-11d0-BD3B-00A0C911CE86}`

## Error Handling Patterns

**Connection Loss:**
```python
try:
    frame = rgb_queue.get(timeout=1.0)
except RuntimeError as e:
    if "X_LINK_ERROR" in str(e):
        # Show "Disconnected" in GUI
        # Keep last frame in shared memory
        # Poll for device reconnection
        reconnect_attempt()
```

**PyInstaller Hidden Imports:**
```python
# In .spec file, explicitly include dynamically loaded DLLs
binaries=[
    ('path/to/UnityCapture.dll', '.'),
    ('path/to/depthai/libs/*.dll', 'depthai/libs')
]
```

## Performance Optimization Notes

- **RGB Conversion:** MUST happen on OAK's VPU (ImageManip node), not on host CPU (30-50ms penalty for NumPy/OpenCV conversion)
- **Shared Memory:** Direct memory mapping via pyvirtualcam - avoid unnecessary copies
- **Frame Dropping:** If host processing lags, drop frames rather than queue (prevents latency buildup)
- **USB Scheduling:** XLink uses bulk transfers (not isochronous like UVC), more tolerant of CPU scheduling delays

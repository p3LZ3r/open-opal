# Zero-Dep DirectShow Driver

This directory contains the C++ DirectShow filter source code.

## Structure

### UnityCapture/
Forked Unity Capture source code (MIT license).
This is the baseline for our custom driver.

### ZeroDepCam/x64/
Compiled 64-bit version of the custom DirectShow driver.
- ZeroDepCam64.dll - The final driver binary
- .pdb files for debugging

### ZeroDepCam/x86/
Compiled 32-bit version of the custom DirectShow driver.
- ZeroDepCam32.dll - The final driver binary
- .pdb files for debugging

## Build Instructions

1. Open `UnityCapture/OAKSmartCam.sln` in Visual Studio
2. Build for both x64 and Win32 platforms
3. Copy output DLLs to respective ZeroDepCam directories
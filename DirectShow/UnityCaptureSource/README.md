# Unity Capture Source Base

This directory will contain the forked/modified Unity Capture source code.

## Next Steps:
1. Clone Unity Capture or similar DirectShow virtual camera repository
2. Modify device name from "Unity Video Capture" to "OAK Smart Cam"
3. Generate new CLSID GUIDs for the filter
4. Update shared memory key from "UnityCaptureMemory" to "OAKCamMemory"

## Key Files to Modify:
- UnityCaptureFilter.cpp/h - Main filter implementation
- UnityCapture.def - DLL exports
- Registry keys in DllRegisterServer
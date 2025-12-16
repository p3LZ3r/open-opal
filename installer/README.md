# Zero-Dep Installer

This directory contains all components for creating the zero-dependency installer.

## Structure

### redist/
Third-party redistributables that must be bundled:
- vc_redist.x64.exe - Microsoft Visual C++ Redistributable
- Other required runtimes

### Output/
Compiled installer files:
- Setup.exe - Final installer executable

### setup.iss
Inno Setup script that orchestrates the complete installation process.

## Installation Process

1. Check administrative privileges
2. Copy all files to Program Files
3. Install VC++ Runtime (if needed)
4. Register DirectShow DLLs via regsvr32
5. Create Start Menu shortcuts
6. Register for Windows startup (optional)
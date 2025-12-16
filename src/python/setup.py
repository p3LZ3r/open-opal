from setuptools import setup, find_packages

setup(
    name="oak-smart-cam",
    version="1.0.0",
    description="OAK Smart Camera Controller",
    author="Zero-Dep Project",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "depthai>=2.24.0",
        "pyvirtualcam>=0.10.0",
        "PyQt6>=6.5.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
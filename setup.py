from setuptools import setup, find_packages

setup(
    name="csvviewer",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "PySide6>=6.6.0",
        "duckdb>=0.10.0",
        "polars>=0.20.0",
        "chardet>=5.0.0",
    ],
    entry_points={
        "console_scripts": [
            "csvviewer=csvviewer.app:main",
        ],
    },
    python_requires=">=3.10",
)

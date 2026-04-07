from setuptools import setup, find_packages
from pathlib import Path

long_description = ""
readme_path = Path(__file__).parent / "README.md"
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

setup(
    name="csvviewer",
    version="1.0.0",
    author="CSV Viewer Contributors",
    author_email="",
    description="A high-performance desktop CSV viewer and editor built with PySide6 and DuckDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/eriktechpawan/csvviewer",
    project_urls={
        "Bug Tracker": "https://github.com/eriktechpawan/csvviewer/issues",
        "Source Code": "https://github.com/eriktechpawan/csvviewer",
    },
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Utilities",
    ],
    keywords="csv viewer editor duckdb pyside6 desktop",
    packages=find_packages(),
    install_requires=[
        "PySide6>=6.6.0",
        "duckdb>=0.10.0",
        "chardet>=5.0.0",
    ],
    entry_points={
        "console_scripts": [
            "csvviewer=csvviewer.app:main",
        ],
    },
    python_requires=">=3.10",
)

"""
Setup configuration for PD Tracker.

This file tells pip how to install the package and creates the 'pd' command.

To install for development (editable mode):
    pip install -e .

This creates the 'pd' command that you can use from anywhere.
"""

from setuptools import setup, find_packages

setup(
    name="pd-tracker",
    version="0.1.0",
    description="Parkinson's Disease management app for tracking medications, symptoms, sleep, and exercise",
    author="Your Name",
    python_requires=">=3.10",

    # find_packages() automatically finds the pd_tracker folder
    packages=find_packages(),

    # Dependencies - same as requirements.txt
    install_requires=[
        "click>=8.0.0",
        "tabulate>=0.9.0",
    ],

    # This creates the 'pd' command
    # It says: when someone types 'pd', run the 'main' function from pd_tracker.cli
    entry_points={
        "console_scripts": [
            "pd=pd_tracker.cli:main",
        ],
    },
)

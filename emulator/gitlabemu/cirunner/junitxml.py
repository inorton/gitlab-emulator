"""
Module to handle merging multiple junit xml files into one file

Uses defusedxml for safety
"""
from pathlib import Path
from typing import List

from defusedxml import ElementTree


def merge_junit_files(outfile: Path, files: List[Path]) -> None:

    for report in files:
        parsed = ElementTree.parse(report)

        assert True

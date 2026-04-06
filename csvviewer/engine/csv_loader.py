"""CSV file auto-detection utilities.

Detects delimiter, encoding, and header row from CSV files
before loading into DuckDB.
"""

import os
import csv
import chardet
from typing import Optional

from csvviewer.engine.export import format_file_size


def detect_encoding(file_path: str, sample_size: int = 65536) -> str:
    """Detect file encoding using chardet.
    
    Reads a sample of the file to determine encoding.
    Falls back to utf-8 if detection confidence is low.
    """
    with open(file_path, 'rb') as f:
        raw = f.read(sample_size)
    
    result = chardet.detect(raw)
    encoding = result.get('encoding', 'utf-8')
    confidence = result.get('confidence', 0)
    
    if not encoding or confidence < 0.5:
        return 'utf-8'
    
    # Normalize encoding names
    encoding = encoding.lower().replace('-', '_')
    if encoding in ('ascii', 'utf_8', 'utf8'):
        return 'utf-8'
    
    return encoding


def detect_delimiter(file_path: str, encoding: str = 'utf-8', 
                     sample_lines: int = 20) -> str:
    """Detect CSV delimiter by analyzing first few lines.
    
    Uses csv.Sniffer and falls back to frequency analysis.
    """
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            sample = ''
            for i, line in enumerate(f):
                if i >= sample_lines:
                    break
                sample += line
        
        # Try csv.Sniffer first
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
            return dialect.delimiter
        except csv.Error:
            pass
        
        # Fallback: count common delimiters
        candidates = [',', ';', '\t', '|']
        counts = {}
        lines = sample.strip().split('\n')
        
        for delim in candidates:
            line_counts = [line.count(delim) for line in lines if line.strip()]
            if line_counts and min(line_counts) > 0:
                # Good delimiter has consistent count across lines
                avg = sum(line_counts) / len(line_counts)
                variance = sum((c - avg) ** 2 for c in line_counts) / len(line_counts)
                if variance < avg:  # Reasonably consistent
                    counts[delim] = avg
        
        if counts:
            return max(counts, key=counts.get)
        
        return ','  # Default
        
    except Exception:
        return ','


def detect_has_header(file_path: str, encoding: str = 'utf-8',
                      delimiter: str = ',') -> bool:
    """Detect whether the CSV has a header row.
    
    Uses csv.Sniffer.has_header().
    """
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            sample = ''
            for i, line in enumerate(f):
                if i >= 20:
                    break
                sample += line
        
        return csv.Sniffer().has_header(sample)
    except Exception:
        return True  # Assume header by default


def get_file_info(file_path: str) -> dict:
    """Get basic file info."""
    stat = os.stat(file_path)
    
    return {
        'path': file_path,
        'name': os.path.basename(file_path),
        'size': stat.st_size,
        'size_str': format_file_size(stat.st_size),
        'modified': stat.st_mtime,
    }


def auto_detect_csv(file_path: str) -> dict:
    """Run all auto-detection on a CSV file.
    
    Returns dict with: encoding, delimiter, has_header, file_info
    """
    encoding = detect_encoding(file_path)
    delimiter = detect_delimiter(file_path, encoding)
    has_header = detect_has_header(file_path, encoding, delimiter)
    file_info = get_file_info(file_path)
    
    return {
        'encoding': encoding,
        'delimiter': delimiter,
        'has_header': has_header,
        'file_info': file_info,
    }

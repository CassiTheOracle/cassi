"""Typed byte dataset for training on arbitrary files.

Uses a compact 2-byte protocol:
- 0xFF + type_id = type marker (start of file/chunk)
- 0xFF 0x00 = end-of-file marker
- type_id 0x01-0x7F = common file types

This allows the model to learn type-specific byte patterns efficiently.
"""

import os
import torch
from torch.utils.data import Dataset
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import mmap
import numpy as np


# Common file type IDs (0x01-0x7F)
FILE_TYPE_IDS = {
    # Text formats
    'txt': 0x01,
    'md': 0x02,
    'py': 0x03,
    'js': 0x04,
    'ts': 0x05,
    'html': 0x06,
    'css': 0x07,
    'json': 0x08,
    'xml': 0x09,
    'yaml': 0x0A,
    'yml': 0x0A,  # alias
    
    # Document formats
    'pdf': 0x10,
    'doc': 0x11,
    'docx': 0x12,
    
    # Image formats
    'png': 0x20,
    'jpg': 0x21,
    'jpeg': 0x21,  # alias
    'gif': 0x22,
    'bmp': 0x23,
    'svg': 0x24,
    
    # Audio formats
    'mp3': 0x30,
    'wav': 0x31,
    'flac': 0x32,
    
    # Video formats
    'mp4': 0x40,
    'avi': 0x41,
    'mov': 0x42,
    
    # Archive formats
    'zip': 0x50,
    'tar': 0x51,
    'gz': 0x52,
    
    # Binary/executable
    'exe': 0x60,
    'dll': 0x61,
    'so': 0x62,
    
    # Data formats
    'csv': 0x70,
    'parquet': 0x71,
    'sqlite': 0x72,
}

# Reverse mapping
ID_TO_FILE_TYPE = {v: k for k, v in FILE_TYPE_IDS.items()}

# Special markers
TYPE_MARKER = 0xFF
EOF_MARKER = 0x00


class TypedByteDataset(Dataset):
    """Dataset that wraps files with type markers for training.
    
    Each file is tagged with a 2-byte type marker (0xFF + type_id) at the start
    and an EOF marker (0xFF 0x00) at the end. Files are chunked to fit the
    sequence length, with optional overlap for context preservation.
    
    Args:
        file_paths: List of file paths to include
        seq_len: Sequence length for training windows
        overlap: Overlap between chunks (default: seq_len // 4)
        max_file_size: Skip files larger than this (default: 10MB)
        cache_dir: Directory to cache processed files (default: None = no cache)
    """
    
    def __init__(
        self,
        file_paths: List[str],
        seq_len: int = 128,
        overlap: Optional[int] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        cache_dir: Optional[str] = None,
    ):
        self.seq_len = seq_len
        self.overlap = overlap if overlap is not None else seq_len // 4
        self.max_file_size = max_file_size
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.chunks = []  # List of (file_path, start_idx, type_id)
        self._process_files(file_paths)
        
        print(f"TypedByteDataset: {len(self.chunks)} chunks from {len(file_paths)} files")
    
    def _process_files(self, file_paths: List[str]):
        """Process files and build chunk index."""
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue
            
            # Get file extension and type ID
            ext = path.suffix.lower().lstrip('.')
            if ext not in FILE_TYPE_IDS:
                continue  # Skip unknown types
            
            type_id = FILE_TYPE_IDS[ext]
            file_size = path.stat().st_size
            
            # Skip files that are too large
            if file_size > self.max_file_size:
                continue
            
            # For small files, still include them (will be padded in __getitem__)
            # For larger files, calculate chunks with overlap
            if file_size < self.seq_len:
                num_chunks = 1
            else:
                num_chunks = max(1, (file_size - self.seq_len) // (self.seq_len - self.overlap) + 1)
            
            
            for i in range(num_chunks):
                start_idx = i * (self.seq_len - self.overlap)
                self.chunks.append((file_path, start_idx, type_id))
    
    def __len__(self):
        return len(self.chunks)
    
    def __getitem__(self, idx):
        """Load a chunk and return (context, target) pair.
        
        Returns:
            context: [seq_len] tensor of bytes (including type marker)
            target: [seq_len] tensor of bytes (shifted by 1 for next-byte prediction)
        """
        file_path, start_idx, type_id = self.chunks[idx]
        
        # Read file bytes
        with open(file_path, 'rb') as f:
            f.seek(start_idx)
            data = f.read(self.seq_len - 2)  # -2 for type marker
        
        # Prepend type marker
        chunk = bytes([TYPE_MARKER, type_id]) + data
        
        # Pad if necessary
        if len(chunk) < self.seq_len:
            chunk = chunk + bytes([0] * (self.seq_len - len(chunk)))
        
        # Convert to tensor
        context = torch.tensor(list(chunk[:self.seq_len]), dtype=torch.long)
        target = torch.tensor(list(chunk[1:self.seq_len+1]), dtype=torch.long)
        
        # Pad target if necessary
        if len(target) < self.seq_len:
            target = torch.cat([target, torch.zeros(self.seq_len - len(target), dtype=torch.long)])
        
        return context, target


def prepare_typed_dataset(
    root_dir: str,
    extensions: Optional[List[str]] = None,
    max_files: Optional[int] = None,
) -> List[str]:
    """Walk directory and collect files with known types.
    
    Args:
        root_dir: Root directory to scan
        extensions: List of extensions to include (default: all known types)
        max_files: Maximum number of files to collect (default: no limit)
    
    Returns:
        List of file paths
    """
    if extensions is None:
        extensions = list(FILE_TYPE_IDS.keys())
    
    file_paths = []
    root = Path(root_dir)
    
    for ext in extensions:
        for path in root.rglob(f'*.{ext}'):
            if path.is_file():
                file_paths.append(str(path))
                if max_files and len(file_paths) >= max_files:
                    return file_paths
    
    return file_paths


if __name__ == '__main__':
    # Test the dataset
    import tempfile
    
    # Create some test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a Python file
        py_file = Path(tmpdir) / 'test.py'
        py_file.write_text('def hello():\n    print("Hello, world!")\n')
        
        # Create a text file
        txt_file = Path(tmpdir) / 'test.txt'
        txt_file.write_text('This is a test text file.\n' * 10)
        
        # Create dataset
        dataset = TypedByteDataset(
            file_paths=[str(py_file), str(txt_file)],
            seq_len=64,
        )
        
        print(f"Dataset size: {len(dataset)}")
        
        # Load a sample
        context, target = dataset[0]
        print(f"Context shape: {context.shape}")
        print(f"Target shape: {target.shape}")
        print(f"First 10 bytes: {context[:10].tolist()}")
        print(f"Type marker: 0x{context[0]:02X}, type_id: 0x{context[1]:02X}")

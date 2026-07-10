import os
import sys
from pathlib import Path

def setup_root():
    # Resolve the absolute path of the repository root
    root = Path(__file__).resolve().parent.parent
    
    # Add src/ to sys.path
    src_path = str(root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        
    # Change working directory to repository root
    os.chdir(root)
    
    print(f"Project root: {root}")
    return root

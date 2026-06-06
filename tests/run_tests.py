"""
Test Runner for minecraftBC

Usage:
    python tests/run_tests.py
    python tests/run_tests.py -v          # Verbose
    python tests/run_tests.py -k punch    # Run specific tests
    python tests/run_tests.py --cov     # With coverage
"""

import sys
import subprocess
from pathlib import Path


def run_tests():
    """Run all tests"""
    # Get test directory
    test_dir = Path(__file__).parent
    root_dir = test_dir.parent
    
    # Add src to path
    sys.path.insert(0, str(root_dir / "src"))
    
    print("=" * 60)
    print("Running minecraftBC Tests")
    print("=" * 60)
    
    # Build pytest arguments
    args = ["pytest", str(test_dir)]
    
    # Add command line arguments
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
    else:
        # Default: verbose and show progress
        args.extend(["-v", "--tb=short"])
    
    print(f"Command: {' '.join(args)}")
    print()
    
    # Run tests
    result = subprocess.run(args)
    
    print()
    print("=" * 60)
    if result.returncode == 0:
        print("All tests PASSED!")
    else:
        print(f"Tests FAILED with code {result.returncode}")
    print("=" * 60)
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())

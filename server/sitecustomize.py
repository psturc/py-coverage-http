# sitecustomize.py
# This file is automatically imported by every Python process during startup.
# It enables coverage collection in ALL processes (master and workers).
#
# Based on: https://coverage.readthedocs.io/en/latest/subprocess.html
#
# To use:
# 1. Place this file in Python's site-packages OR add its directory to PYTHONPATH
# 2. Set COVERAGE_PROCESS_START=/path/to/.coveragerc
# 3. Start your application normally

import os

# Only enable coverage if explicitly requested via environment variable
if os.environ.get('COVERAGE_PROCESS_START'):
    try:
        import coverage
        # This automatically starts coverage in every process
        # Each process writes to its own file when parallel=True in .coveragerc
        coverage.process_startup()
    except ImportError:
        pass  # coverage not installed - silently skip
    except Exception as e:
        # Log but don't crash the application
        import sys
        print(f"[sitecustomize] Coverage startup failed: {e}", file=sys.stderr)

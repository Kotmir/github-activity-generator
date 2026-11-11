#!/usr/bin/env python
"""Backward compatible CLI entry point:
    python contribute.py --repository=git@github.com:user/repo.git
For the web interface use:  python run.py
Author: kotmir (based on Shpota/github-activity-generator)."""
import sys

from app.cli import main

if __name__ == '__main__':
    sys.exit(main())

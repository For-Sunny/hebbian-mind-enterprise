#!/usr/bin/env python3
"""
Hebbian Mind Enterprise - Entry Point

Allows running the server with:
    python -m hebbian_mind

Copyright (c) 2026 CIPS LLC
"""

import asyncio
from .server import main

if __name__ == "__main__":
    asyncio.run(main())

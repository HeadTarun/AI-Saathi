import asyncio
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(src_dir))

from streamlit_app import main


if __name__ == "__main__":
    asyncio.run(main())

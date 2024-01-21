import subprocess
from icecream import ic
import uvicorn
from app import app

ic.configureOutput(prefix='|> ')


def setup_playwright():
    result = ic(subprocess.run("playwright --version", shell=True, capture_output=True))
    if result.returncode != 0:
        ic(subprocess.run("playwright install", shell=True, capture_output=True))


if __name__ == "__main__":
    setup_playwright()
    uvicorn.run(app, host="0.0.0.0", port=8080)

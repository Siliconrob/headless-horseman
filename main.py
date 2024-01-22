from icecream import ic
import uvicorn
from app import app

ic.configureOutput(prefix='|> ')

if __name__ == "__main__":
    ic(uvicorn.run(app, host="0.0.0.0", port=8080))

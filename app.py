import os
from fastapi.middleware.cors import CORSMiddleware
from icecream import ic
from fastapi import FastAPI, HTTPException
from urllib.parse import urlparse
from starlette.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from core.runner import scrape_price_url, scrape_reviews_url
from middlewares.exceptionhandler import ExceptionHandlerMiddleware

ic.configureOutput(prefix='|> ')

tags_metadata = [
    {"name": "Headless", "description": "For headless operations"},
]


class RequestTarget(BaseModel):
    target_url: str
    watermark: str


app = FastAPI(title="Headless Horseman",
              description="A drowsy, dreamy influence seems to hang over the land, and to pervade the very atmosphere",
              version="0.0.1",
              terms_of_service="Strength is irrelevant. Resistance is futile. We wish to improve ourselves. We will add your biological and technological distinctiveness to our own.",
              contact={
                  "url": "https://siliconheaven.info",
                  "email": "siliconrob@siliconheaven.net",
              },
              openapi_tags=tags_metadata,
              license_info={
                  "name": "MIT License",
                  "url": "https://opensource.org/license/mit/",
              })

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ExceptionHandlerMiddleware)


def is_valid_url(url):
    try:
        result = urlparse(url)
        return True
    except ValueError:
        return False


@app.post("/retrieve_price", tags=["Headless"], include_in_schema=True)
async def direct_price(target: RequestTarget):
    if not is_valid_url(target.target_url):
        raise HTTPException(400, detail=f"Invalid url {target.target_url}")
    if os.getenv('API_REQUEST') != target.watermark:
        raise HTTPException(401)
    ic(target)
    response = ic(await scrape_price_url(target.target_url))
    return dict(result=response)


@app.post("/retrieve_reviews", tags=["Headless"], include_in_schema=True)
async def direct_price(target: RequestTarget):
    if not is_valid_url(target.target_url):
        raise HTTPException(400, detail=f"Invalid url {target.target_url}")
    if os.getenv('API_REQUEST') != target.watermark:
        raise HTTPException(401)
    ic(target)
    response = ic(await scrape_reviews_url(target.target_url))
    return dict(result=response)


@app.get("/", tags=["Headless"], include_in_schema=False)
async def to_docs():
    return RedirectResponse("/docs")

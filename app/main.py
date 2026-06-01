from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

from app.models import mongodb
from app.models.products import ProductModel
from app.product_scraper import NaverProductScraper

app = FastAPI()


BASE_DIR = Path(__file__).resolve().parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # product=ProductModel(
    #     keyword="python",
    #     publisher="lizb",
    #     price=1200,
    #     image="me.png"
    # )
    # save_product= await mongodb.engine.save(product)
    # print(save_product.model_dump(),flush=True)
    return templates.TemplateResponse(request, "index.html", {"title": "쇼핑"})


@app.get("/search", response_class=HTMLResponse)
async def read_item(request: Request, q: str):
    keyword = q

    naver_product_scraper = NaverProductScraper()

    products = await naver_product_scraper.search(keyword, 10)

    favorite_products = await mongodb.engine.find(
        ProductModel, ProductModel.is_favorite == True
    )

    favorite_images = [product.image for product in favorite_products]

    product_models = []

    for product in products:
        print(product)
        product_model = ProductModel(
            keyword=keyword,
            publisher=product.get("title", ""),
            price=int(product.get("lprice") or 0),
            image=product["image"],
            link=product.get("link", ""),
        )

        if product_model.image in favorite_images:
            product_model.is_favorite = True

        product_models.append(product_model)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "keyword": q,
            "products": product_models,
            "next_url": f"/search?q={q}",
        },
    )


@app.post("/favorites")
async def toggle_favorite(
    request: Request,
    keyword: str = Form(...),
    publisher: str = Form(...),
    price: int = Form(...),
    image: str = Form(...),
    next_url: str = Form("/"),
    link: str = Form(...),
):
    favorite_product = await mongodb.engine.find_one(
        ProductModel,
        (ProductModel.keyword == keyword)
        & (ProductModel.publisher == publisher)
        & (ProductModel.image == image)
        & (ProductModel.is_favorite == True),
    )
    if favorite_product:
        await mongodb.engine.delete(favorite_product)

    else:
        product = ProductModel(
            keyword=keyword,
            publisher=publisher,
            price=price,
            image=image,
            link=link,
            is_favorite=True,
        )
        await mongodb.engine.save(product)

    return RedirectResponse(url=next_url, status_code=303)


@app.get("/favorites", response_class=HTMLResponse)
async def favorites(request: Request):
    products = await mongodb.engine.find(ProductModel, ProductModel.is_favorite == True)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "즐겨찾기 목록",
            "products": products,
            "next_url": "/favorites",
        },
    )


@app.on_event("startup")
async def on_app_start():
    print("hello server")
    mongodb.connect()


@app.on_event("shutdown")
async def on_app_shutdown():
    print("goodbye server")
    mongodb.close()

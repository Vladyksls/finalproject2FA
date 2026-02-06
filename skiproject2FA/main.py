from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from data import products

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Sessions (replacement for Flask session)
app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-key"
)

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Fake DB
users = {}
cart_store = {}


class Product:
    def __init__(self, data):
        self.__dict__.update(data)


products_obj = [Product(p) for p in products]


# ---------- HELPERS ----------

def get_cart(request: Request):
    user = request.session.get("user")
    if not user:
        return []
    return cart_store.get(user, [])


def cart_products(cart_ids):
    return [p for p in products if p["id"] in cart_ids]


# ---------- ROUTES ----------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/catalog/{category}", response_class=HTMLResponse)
def catalog(request: Request, category: str):
    # --- Query parameters ---
    q = request.query_params.get("q", "").lower()
    sort = request.query_params.get("sort", "default")
    min_price = request.query_params.get("min_price", "")
    max_price = request.query_params.get("max_price", "")
    brands = [b.lower() for b in request.query_params.getall("brand")]
    levels = [l.lower() for l in request.query_params.getall("level")]
    styles = [s.lower() for s in request.query_params.getall("style")]

    # --- Filter by category ---
    if category == "sales":
        filtered = [p for p in products_obj if getattr(p, "is_sale", False)]
    elif category == "arrivals":
        filtered = [p for p in products_obj if getattr(p, "is_new", False)]
    else:
        filtered = [p for p in products_obj if getattr(p, "category") == category]

    # --- Search filter ---
    if q:
        filtered = [p for p in filtered if q in getattr(p, "name", "").lower()]

    # --- Checkbox filters ---
    if brands:
        filtered = [p for p in filtered if getattr(p, "brand", "").lower() in brands]
    if levels:
        filtered = [p for p in filtered if getattr(p, "level", "").lower() in levels]
    if styles:
        filtered = [p for p in filtered if getattr(p, "style", "").lower() in styles]

    # --- Price filters ---
    try:
        if min_price:
            filtered = [p for p in filtered if getattr(p, "price", 0) >= float(min_price)]
        if max_price:
            filtered = [p for p in filtered if getattr(p, "price", 0) <= float(max_price)]
    except:
        pass

    # --- Sorting ---
    if sort == "price_asc":
        filtered.sort(key=lambda x: getattr(x, "price", 0))
    elif sort == "price_desc":
        filtered.sort(key=lambda x: -getattr(x, "price", 0))
    elif sort == "name":
        filtered.sort(key=lambda x: getattr(x, "name", ""))

    # --- Sidebar filters based on full category ---
    if category == "sales":
        base_products = [p for p in products_obj if getattr(p, "is_sale", False)]
    elif category == "arrivals":
        base_products = [p for p in products_obj if getattr(p, "is_new", False)]
    else:
        base_products = [p for p in products_obj if getattr(p, "category") == category]

    return templates.TemplateResponse(
        "catalog.html",
        {
            "request": request,
            "products": filtered,
            "category": category,
            "count": len(filtered),
            "filters": {
                "brands": sorted(set(p.brand for p in base_products)),
                "levels": sorted(set(p.level for p in base_products)),
                "styles": sorted(set(p.style for p in base_products)),
            },
            "selected": {
                "q": q,
                "brand": brands,
                "level": levels,
                "style": styles,
                "sort": sort,
                "min_price": min_price,
                "max_price": max_price
            }
        }
    )


@app.get("/product/{pid}", response_class=HTMLResponse)
def product_page(request: Request, pid: int):
    product = next((p for p in products_obj if p.id == pid), None)
    if not product:
        return HTMLResponse("Product not found", status_code=404)

    related = [p for p in products_obj if p.category == product.category and p.id != pid][:4]

    return templates.TemplateResponse(
        "product.html",
        {
            "request": request,
            "product": product,
            "related": related
        }
    )


# ---------- CART ----------

@app.get("/add-to-cart/{product_id}")
def add_to_cart(request: Request, product_id: int):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=302)

    cart_store.setdefault(user, []).append(product_id)
    return RedirectResponse("/cart", status_code=302)


@app.get("/remove-from-cart/{product_id}")
def remove_from_cart(request: Request, product_id: int):
    user = request.session.get("user")
    if user and user in cart_store:
        cart_store[user] = [i for i in cart_store[user] if i != product_id]
    return RedirectResponse("/cart", status_code=302)


@app.get("/cart", response_class=HTMLResponse)
def cart(request: Request):
    cart_ids = get_cart(request)
    items = cart_products(cart_ids)
    total = sum(p["price"] for p in items)

    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "products": items,
            "total": total
        }
    )


# ---------- CHECKOUT ----------

@app.get("/checkout", response_class=HTMLResponse)
def checkout(request: Request):
    return templates.TemplateResponse(
        "checkout.html",
        {"request": request}
    )


@app.post("/checkout")
def checkout_post():
    return RedirectResponse("/", status_code=302)


# ---------- AUTH ----------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )


@app.post("/login")
def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...)
):
    if users.get(email) == password:
        request.session["user"] = email
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid login"}
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )


@app.post("/register")
def register(
        request: Request,
        email: str = Form(...),
        password: str = Form(...)
):
    if email in users:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "User already exists"}
        )

    users[email] = password
    request.session["user"] = email
    return RedirectResponse("/", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

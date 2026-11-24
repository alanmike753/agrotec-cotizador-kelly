from __future__ import annotations

import json
import logging
import os
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from .calculations import apply_successive_discounts, calculate_sale, decimal_string
from .auth import (
    COOKIE_NAME, bootstrap_initial_admin, clear_session_cookie, create_session,
    get_current_user, hash_password, normalize_email, require_admin, revoke_session,
    set_session_cookie, user_payload, verify_password,
)
from .database import SessionLocal, engine, get_db
from .family_classifier import NEEDS_CONFIRMATION, classify_catalog
from .importer import ROOT_DIR, import_catalog
from .migrations import migrate_database
from .models import DiscountRule, Product, ProductCommercialPreference, Setting, User, UserSession
from .schemas import (
    BulkFamilyUpdate,
    BulkProductRuleApplyRequest,
    CalculationRequest,
    CommercialPreferenceInput,
    ProductUpdate,
    RuleApplyRequest,
    RulePreviewRequest,
    SettingUpdate,
    LoginInput,
    UserCreateInput,
    UserUpdateInput,
)


logger = logging.getLogger("agrotec")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
login_attempts: dict[str, list[float]] = {}


def login_rate_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def check_login_rate(request: Request) -> str:
    key = login_rate_key(request)
    cutoff = time.time() - 900
    attempts = [stamp for stamp in login_attempts.get(key, []) if stamp >= cutoff]
    login_attempts[key] = attempts
    if len(attempts) >= 8:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Espera 15 minutos.")
    if len(login_attempts) > 5000:
        oldest = min(login_attempts, key=lambda item: login_attempts[item][-1] if login_attempts[item] else 0)
        login_attempts.pop(oldest, None)
    return key


def rule_discounts(rule: DiscountRule | None) -> list[str] | None:
    return json.loads(rule.discounts_json) if rule else None


def effective_rule(db: Session, product: Product) -> DiscountRule | None:
    override = db.scalar(select(DiscountRule).where(
        DiscountRule.scope_type == "product", DiscountRule.scope_key == product.id
    ))
    if override:
        return override
    if product.family and product.family != NEEDS_CONFIRMATION:
        return db.scalar(select(DiscountRule).where(
            DiscountRule.scope_type == "family", DiscountRule.scope_key == product.family
        ))
    return None


_UNSET = object()


def effective_preference(db: Session, product: Product) -> dict:
    saved = db.get(ProductCommercialPreference, product.id)
    if saved:
        return {
            "profit_mode": saved.profit_mode,
            "profit_value": saved.profit_value,
            "rounding_increment": saved.rounding_increment,
            "is_custom": True,
            "updated_at": saved.updated_at.isoformat(),
        }
    default_markup = product.default_markup_pct or db.get(Setting, "default_markup_pct").value
    return {
        "profit_mode": "markup",
        "profit_value": default_markup,
        "rounding_increment": "1",
        "is_custom": product.default_markup_pct is not None,
        "updated_at": product.updated_at.isoformat() if product.default_markup_pct is not None else None,
    }


def serialize_product(
    db: Session,
    product: Product,
    include_calculation: bool = False,
    resolved_rule: DiscountRule | None | object = _UNSET,
    resolved_preference: dict | object = _UNSET,
) -> dict:
    rule = effective_rule(db, product) if resolved_rule is _UNSET else resolved_rule
    discounts = rule_discounts(rule)
    preference = effective_preference(db, product) if resolved_preference is _UNSET else resolved_preference
    payload = {
        "id": product.id,
        "name": product.name,
        "supplier_code": product.supplier_code,
        "category": product.category,
        "family": product.family,
        "family_status": product.family_status,
        "family_source_label": product.family_source_label,
        "list_price_mxn": product.list_price,
        "default_markup_pct": product.default_markup_pct,
        "status": "configured" if rule else "pending",
        "commercial_preference": preference,
        "rule": None if rule is None else {
            "id": rule.id,
            "scope_type": rule.scope_type,
            "scope_key": rule.scope_key,
            "name": rule.name,
            "discounts": discounts,
            "explicit_zero": rule.explicit_zero,
            "source": rule.source,
            "updated_at": rule.updated_at.isoformat(),
        },
        "origin": {
            "sheet": product.source_sheet,
            "row": product.source_row,
            "model_column": product.source_model_column,
            "price_column": product.source_price_column,
            "updated_at": product.updated_at.isoformat(),
        },
    }
    if include_calculation and discounts is not None:
        result = calculate_sale(
            Decimal(product.list_price),
            [Decimal(value) for value in discounts],
            preference["profit_mode"],
            Decimal(preference["profit_value"]),
            preference["rounding_increment"],
        )
        payload["calculation"] = {key: decimal_string(value) for key, value in result.items()}
        payload["calculation"]["profit_mode"] = preference["profit_mode"]
        payload["calculation"]["profit_value"] = preference["profit_value"]
        payload["calculation"]["rounding_increment"] = preference["rounding_increment"]
    else:
        payload["calculation"] = None
    return payload


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_database(engine)
    with SessionLocal() as db:
        import_catalog(db)
        classify_catalog(db)
        bootstrap_initial_admin(db)
        db.commit()
    yield


app = FastAPI(title="Agrotec — Lista de precios Kelly", version="1.0.0", lifespan=lifespan)
cors_origins = [item.strip() for item in os.getenv("AGROTEC_CORS_ORIGINS", "").split(",") if item.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info(
        "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id, request.method, request.url.path, response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


@app.get("/api/health")
async def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/assets/logo")
async def logo():
    path = ROOT_DIR / "assets" / "logo_agrotec_referencia.png"
    return FileResponse(path)


@app.post("/api/auth/login")
async def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_key = check_login_rate(request)
    user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        login_attempts.setdefault(rate_key, []).append(time.time())
        await asyncio.sleep(0.4)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos.")
    login_attempts.pop(rate_key, None)
    token = create_session(db, user, request)
    set_session_cookie(response, token)
    return user_payload(user)


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    revoke_session(db, request.cookies.get(COOKIE_NAME))
    clear_session_cookie(response)
    return {"logged_out": True}


@app.get("/api/auth/me")
async def me(user: User = Depends(get_current_user)):
    return user_payload(user)


@app.get("/api/users")
async def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.full_name, User.email)).all()
    return {"items": [user_payload(user) for user in users]}


@app.post("/api/users", status_code=201)
async def create_user(payload: UserCreateInput, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo.")
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_payload(user)


@app.patch("/api/users/{user_id}")
async def update_user(
    user_id: int, payload: UserUpdateInput,
    admin: User = Depends(require_admin), db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Usuario no encontrado.")
    if user.id == admin.id and (payload.is_active is False or payload.role == "seller"):
        raise HTTPException(422, "No puedes quitar tu propio acceso administrativo.")
    removes_admin = user.role == "admin" and (payload.role == "seller" or payload.is_active is False)
    if removes_admin:
        active_admins = db.scalar(select(func.count()).select_from(User).where(
            User.role == "admin", User.is_active.is_(True)
        ))
        if active_admins <= 1:
            raise HTTPException(422, "Debe permanecer al menos un administrador activo.")
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.password is not None or payload.is_active is False or payload.role is not None:
        db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()
    db.refresh(user)
    return user_payload(user)


@app.post("/api/import")
async def reimport(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = import_catalog(db)
    result["classification"] = classify_catalog(db)
    db.commit()
    return result


@app.get("/api/products")
async def list_products(
    search: str = "",
    status: str = Query("all", pattern="^(all|configured|pending)$"),
    family: str | None = None,
    family_status: str = Query("all", pattern="^(all|source_heading|manual|needs_confirmation)$"),
    sort: str = Query("name", pattern="^(name|price|status)$"),
    direction: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=300),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = db.scalars(select(Product)).all()
    all_rules = db.scalars(select(DiscountRule)).all()
    product_rules = {rule.scope_key: rule for rule in all_rules if rule.scope_type == "product"}
    family_rules = {rule.scope_key: rule for rule in all_rules if rule.scope_type == "family"}
    saved_preferences = {
        item.product_id: item for item in db.scalars(select(ProductCommercialPreference)).all()
    }
    global_markup = db.get(Setting, "default_markup_pct").value

    def resolved(product: Product) -> DiscountRule | None:
        return product_rules.get(product.id) or (
            family_rules.get(product.family)
            if product.family and product.family != NEEDS_CONFIRMATION else None
        )

    def preference(product: Product) -> dict:
        saved = saved_preferences.get(product.id)
        if saved:
            return {
                "profit_mode": saved.profit_mode, "profit_value": saved.profit_value,
                "rounding_increment": saved.rounding_increment, "is_custom": True,
                "updated_at": saved.updated_at.isoformat(),
            }
        return {
            "profit_mode": "markup", "profit_value": product.default_markup_pct or global_markup,
            "rounding_increment": "1", "is_custom": product.default_markup_pct is not None,
            "updated_at": product.updated_at.isoformat() if product.default_markup_pct is not None else None,
        }

    rows = [serialize_product(
        db, product, resolved_rule=resolved(product), resolved_preference=preference(product)
    ) for product in products]
    needle = search.strip().casefold()
    if needle:
        rows = [row for row in rows if any(
            needle in str(row.get(field) or "").casefold()
            for field in ("name", "id", "supplier_code", "family", "family_source_label")
        )]
    if status != "all":
        rows = [row for row in rows if row["status"] == status]
    if family is not None:
        rows = [row for row in rows if row["family"] == family]
    if family_status != "all":
        rows = [row for row in rows if row["family_status"] == family_status]
    key = {
        "name": lambda row: row["name"].casefold(),
        "price": lambda row: Decimal(row["list_price_mxn"]),
        "status": lambda row: row["status"],
    }[sort]
    rows.sort(key=key, reverse=direction == "desc")
    total = len(rows)
    start = (page - 1) * page_size
    counts = {"total": len(products), "configured": 0, "pending": 0, "family_confirmation": 0}
    for product in products:
        counts["configured" if resolved(product) else "pending"] += 1
        if product.family_status == "needs_confirmation":
            counts["family_confirmation"] += 1
    return {"items": rows[start:start + page_size], "filtered": total, "counts": counts, "page": page, "page_size": page_size}


@app.get("/api/products/{product_id}")
async def get_product(product_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Implemento no encontrado.")
    return serialize_product(db, product, include_calculation=True)


@app.post("/api/products/{product_id}/calculate")
async def calculate_product(
    product_id: str, request: CalculationRequest,
    _: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Implemento no encontrado.")
    rule = effective_rule(db, product)
    if rule is None and request.discounts is None:
        raise HTTPException(409, "Pendiente de configurar: no se puede calcular costo ni precio público.")
    discounts = request.discounts if request.discounts is not None else rule_discounts(rule) or []
    origin = "temporary" if request.discounts is not None else rule.scope_type
    try:
        result = calculate_sale(
            Decimal(product.list_price),
            [Decimal(value) for value in discounts],
            request.profit_mode,
            Decimal(request.profit_value),
            request.rounding_increment,
        )
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        key: decimal_string(value) for key, value in result.items()
    } | {
        "profit_mode": request.profit_mode,
        "profit_value": request.profit_value,
        "rounding_increment": request.rounding_increment,
        "discounts_used": discounts,
        "discount_origin": origin,
    }


@app.put("/api/products/{product_id}/commercial-preference")
async def save_commercial_preference(
    product_id: str, request: CommercialPreferenceInput,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Implemento no encontrado.")
    preference = db.get(ProductCommercialPreference, product_id)
    if preference is None:
        preference = ProductCommercialPreference(product_id=product_id)
        db.add(preference)
    preference.profit_mode = request.profit_mode
    preference.profit_value = request.profit_value
    preference.rounding_increment = request.rounding_increment
    db.commit()
    db.refresh(preference)
    return serialize_product(db, product, include_calculation=True)


@app.patch("/api/products/{product_id}")
async def update_product(
    product_id: str, request: ProductUpdate,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Implemento no encontrado.")
    if "family" in request.model_fields_set:
        family = request.family.strip() if request.family and request.family.strip() else NEEDS_CONFIRMATION
        product.family = family
        product.family_status = "needs_confirmation" if family == NEEDS_CONFIRMATION else "manual"
        product.family_source_label = "Asignación manual en administración"
    if "default_markup_pct" in request.model_fields_set:
        if request.default_markup_pct is None:
            product.default_markup_pct = None
        else:
            try:
                markup = Decimal(request.default_markup_pct)
            except InvalidOperation as exc:
                raise HTTPException(422, "El recargo debe ser un decimal válido.") from exc
            if markup < 0:
                raise HTTPException(422, "El recargo no puede ser negativo.")
            product.default_markup_pct = format(markup, "f")
            preference = db.get(ProductCommercialPreference, product_id)
            if preference is None:
                preference = ProductCommercialPreference(product_id=product_id)
                db.add(preference)
            preference.profit_mode = "markup"
            preference.profit_value = product.default_markup_pct
            preference.rounding_increment = preference.rounding_increment or "1"
    db.commit()
    return serialize_product(db, product, include_calculation=True)


@app.post("/api/products/bulk-family")
async def bulk_family(
    request: BulkFamilyUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    products = db.scalars(select(Product).where(Product.id.in_(request.product_ids))).all()
    if len(products) != len(set(request.product_ids)):
        raise HTTPException(404, "Uno o más implementos no existen.")
    family = request.family.strip() if request.family and request.family.strip() else NEEDS_CONFIRMATION
    for product in products:
        product.family = family
        product.family_status = "needs_confirmation" if family == NEEDS_CONFIRMATION else "manual"
        product.family_source_label = "Asignación manual masiva"
    db.commit()
    return {"updated": len(products), "family": family}


@app.get("/api/families")
async def families(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    products = db.scalars(select(Product)).all()
    rules_by_family = {
        rule.scope_key: rule for rule in db.scalars(select(DiscountRule).where(
            DiscountRule.scope_type == "family"
        )).all()
    }
    grouped: dict[str, dict] = {}
    for product in products:
        name = product.family or NEEDS_CONFIRMATION
        entry = grouped.setdefault(name, {
            "name": name, "count": 0, "status": product.family_status,
            "source_label": product.family_source_label, "has_rule": name in rules_by_family,
        })
        entry["count"] += 1
        if product.family_status == "needs_confirmation":
            entry["status"] = "needs_confirmation"
    return {"items": sorted(grouped.values(), key=lambda item: item["name"].casefold())}


@app.get("/api/rules")
async def rules(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    items = db.scalars(select(DiscountRule).order_by(DiscountRule.scope_type, DiscountRule.scope_key)).all()
    return {"items": [{
        "id": item.id, "scope_type": item.scope_type, "scope_key": item.scope_key,
        "name": item.name, "discounts": rule_discounts(item), "explicit_zero": item.explicit_zero,
        "source": item.source, "updated_at": item.updated_at.isoformat(),
    } for item in items]}


@app.post("/api/rules/preview")
async def preview_rule(
    request: RulePreviewRequest, _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    if request.scope_type == "family":
        if not request.scope_key or request.scope_key == NEEDS_CONFIRMATION:
            raise HTTPException(422, "La familia debe estar confirmada antes de recibir descuentos.")
        products = db.scalars(select(Product).where(Product.family == request.scope_key)).all()
        if not products:
            raise HTTPException(404, "La familia no tiene implementos asignados.")
    else:
        products = db.scalars(select(Product).where(Product.id.in_(request.product_ids))).all()
        if len(products) != len(set(request.product_ids)):
            raise HTTPException(404, "Uno o más implementos no existen.")
    discounts = [Decimal(value) for value in request.rule.discounts]
    items = [{
        "id": product.id,
        "name": product.name,
        "family": product.family,
        "list_price_mxn": product.list_price,
        "preview_distributor_cost": decimal_string(apply_successive_discounts(Decimal(product.list_price), discounts)),
        "current_rule_origin": (
            effective_rule(db, product).scope_type if effective_rule(db, product) else None
        ),
    } for product in products]
    return {
        "scope_type": request.scope_type,
        "scope_key": request.scope_key,
        "affected_count": len(items),
        "items": items,
    }


@app.put("/api/rules")
async def apply_rule(
    request: RuleApplyRequest, _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    if request.scope_type == "product" and db.get(Product, request.scope_key) is None:
        raise HTTPException(404, "Implemento no encontrado.")
    if request.scope_type == "family":
        if request.scope_key == NEEDS_CONFIRMATION:
            raise HTTPException(422, "No se pueden aplicar descuentos a una familia pendiente de confirmar.")
        exists = db.scalar(select(Product.id).where(Product.family == request.scope_key).limit(1))
        if exists is None:
            raise HTTPException(404, "La familia no tiene implementos asignados.")
    rule = db.scalar(select(DiscountRule).where(
        DiscountRule.scope_type == request.scope_type, DiscountRule.scope_key == request.scope_key
    ))
    if rule is None:
        rule = DiscountRule(scope_type=request.scope_type, scope_key=request.scope_key)
        db.add(rule)
    rule.name = request.rule.name
    rule.discounts_json = json.dumps(request.rule.discounts)
    rule.explicit_zero = request.rule.explicit_zero
    rule.source = "Configuración local autorizada"
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "scope_type": rule.scope_type, "scope_key": rule.scope_key, "discounts": rule_discounts(rule)}


@app.post("/api/rules/bulk-products")
async def apply_bulk_product_rules(
    request: BulkProductRuleApplyRequest,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    products = db.scalars(select(Product).where(Product.id.in_(request.product_ids))).all()
    if len(products) != len(set(request.product_ids)):
        raise HTTPException(404, "Uno o más implementos no existen.")
    for product in products:
        rule = db.scalar(select(DiscountRule).where(
            DiscountRule.scope_type == "product", DiscountRule.scope_key == product.id
        ))
        if rule is None:
            rule = DiscountRule(scope_type="product", scope_key=product.id)
            db.add(rule)
        rule.name = request.rule.name
        rule.discounts_json = json.dumps(request.rule.discounts)
        rule.explicit_zero = request.rule.explicit_zero
        rule.source = "Configuración local autorizada"
    db.commit()
    return {"updated": len(products), "product_ids": [product.id for product in products]}


@app.delete("/api/rules/{scope_type}/{scope_key}")
async def delete_rule(
    scope_type: str, scope_key: str,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    rule = db.scalar(select(DiscountRule).where(
        DiscountRule.scope_type == scope_type, DiscountRule.scope_key == scope_key
    ))
    if rule is None:
        raise HTTPException(404, "Regla no encontrada.")
    db.delete(rule)
    db.commit()
    return {"deleted": True}


@app.get("/api/settings")
async def get_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    setting = db.get(Setting, "default_markup_pct")
    return {"default_markup_pct": setting.value}


@app.patch("/api/settings")
async def update_settings(
    request: SettingUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    try:
        value = Decimal(request.default_markup_pct)
    except InvalidOperation as exc:
        raise HTTPException(422, "El recargo debe ser un decimal válido.") from exc
    if value < 0:
        raise HTTPException(422, "El recargo no puede ser negativo.")
    setting = db.get(Setting, "default_markup_pct")
    setting.value = format(value, "f")
    db.commit()
    return {"default_markup_pct": setting.value}


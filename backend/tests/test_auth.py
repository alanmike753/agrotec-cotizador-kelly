def test_private_endpoints_require_login(anonymous_client):
    assert anonymous_client.get("/api/health").status_code == 200
    assert anonymous_client.get("/api/products").status_code == 401
    assert anonymous_client.get("/api/rules").status_code == 401


def test_login_cookie_and_logout(anonymous_client):
    rejected = anonymous_client.post("/api/auth/login", json={
        "email": "admin@agrotec.test", "password": "incorrecta-segura",
    })
    assert rejected.status_code == 401
    accepted = anonymous_client.post("/api/auth/login", json={
        "email": "ADMIN@AGROTEC.TEST", "password": "Pruebas-Seguras-2026",
    })
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "admin"
    assert anonymous_client.get("/api/auth/me").status_code == 200
    assert anonymous_client.post("/api/auth/logout").status_code == 200
    assert anonymous_client.get("/api/auth/me").status_code == 401


def test_seller_can_quote_but_cannot_change_permanent_data(client):
    created = client.post("/api/users", json={
        "email": "ventas@agrotec.test", "full_name": "Vendedor",
        "password": "Vendedor-Seguro-2026", "role": "seller",
    })
    assert created.status_code == 201

    from conftest import SyncASGIClient
    seller = SyncASGIClient()
    assert seller.post("/api/auth/login", json={
        "email": "ventas@agrotec.test", "password": "Vendedor-Seguro-2026",
    }).status_code == 200
    assert seller.get("/api/products", params={"page_size": 300}).status_code == 200
    quote = seller.post("/api/products/implementos-0051-E/calculate", json={
        "discounts": ["57.5", "3", "8.5"], "profit_mode": "markup",
        "profit_value": "27", "rounding_increment": "10",
    })
    assert quote.status_code == 200
    assert quote.json()["discount_origin"] == "temporary"
    assert seller.get("/api/rules").status_code == 403
    assert seller.patch("/api/settings", json={"default_markup_pct": "30"}).status_code == 403
    assert seller.put("/api/rules", json={
        "scope_type": "product", "scope_key": "implementos-0051-E",
        "rule": {"discounts": ["57.5", "3", "8.5"]},
    }).status_code == 403


def test_two_seller_sessions_keep_simulations_independent(client):
    for number in (1, 2):
        assert client.post("/api/users", json={
            "email": f"ventas{number}@agrotec.test", "full_name": f"Vendedor {number}",
            "password": f"Vendedor-{number}-Seguro-2026", "role": "seller",
        }).status_code == 201

    from conftest import SyncASGIClient
    first, second = SyncASGIClient(), SyncASGIClient()
    first.post("/api/auth/login", json={
        "email": "ventas1@agrotec.test", "password": "Vendedor-1-Seguro-2026",
    })
    second.post("/api/auth/login", json={
        "email": "ventas2@agrotec.test", "password": "Vendedor-2-Seguro-2026",
    })
    before = client.get("/api/rules").json()
    first_quote = first.post("/api/products/implementos-0051-E/calculate", json={
        "discounts": ["57.5", "3", "5"], "profit_mode": "markup",
        "profit_value": "25", "rounding_increment": "1",
    }).json()
    second_quote = second.post("/api/products/implementos-0051-E/calculate", json={
        "discounts": ["57.5", "3", "10"], "profit_mode": "fixed",
        "profit_value": "1000", "rounding_increment": "100",
    }).json()
    assert first_quote["suggested_price"] != second_quote["suggested_price"]
    assert client.get("/api/rules").json() == before

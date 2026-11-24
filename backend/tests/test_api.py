def test_catalog_counts_and_no_out_of_scope(client):
    response = client.get("/api/products", params={"page_size": 300})
    assert response.status_code == 200
    data = response.json()
    assert data["counts"] == {"total": 283, "configured": 22, "pending": 261, "family_confirmation": 0}
    assert len(data["items"]) == 283
    assert {item["category"] for item in data["items"]} == {"Implementos"}
    assert all(item["origin"]["sheet"] == "Implementos" for item in data["items"])
    assert all(item["family"] for item in data["items"])
    assert sum(item["family_status"] == "needs_confirmation" for item in data["items"]) == 0


def test_repeat_import_is_idempotent(client):
    assert client.post("/api/import").json()["database_products"] == 283
    assert client.post("/api/import").json()["database_products"] == 283


def test_pending_product_has_no_calculation(client):
    product = client.get("/api/products/implementos-0009-A").json()
    assert product["status"] == "pending"
    assert product["calculation"] is None
    response = client.post("/api/products/implementos-0009-A/calculate", json={})
    assert response.status_code == 409


def test_temporary_discounts_calculate_without_persisting(client):
    product_id = "implementos-0009-A"
    before = client.get(f"/api/products/{product_id}").json()
    response = client.post(f"/api/products/{product_id}/calculate", json={
        "discounts": ["57.5", "3", "5"], "profit_mode": "markup",
        "profit_value": "25", "rounding_increment": "10",
    })
    assert response.status_code == 200
    assert response.json()["discount_origin"] == "temporary"
    assert response.json()["discounts_used"] == ["57.5", "3", "5"]
    after = client.get(f"/api/products/{product_id}").json()
    assert before["status"] == after["status"] == "pending"
    assert before["rule"] == after["rule"] is None


def test_pending_product_exact_decimal_temporary_quote(client):
    product_id = "implementos-0051-E"
    before_rules = client.get("/api/rules").json()["items"]
    response = client.post(f"/api/products/{product_id}/calculate", json={
        "discounts": ["57.5", "3", "10"],
        "profit_mode": "markup", "profit_value": "25", "rounding_increment": "1",
    })
    assert response.status_code == 200
    calculation = response.json()
    assert calculation["distributor_cost"] == "97668.99"
    assert calculation["suggested_price"] == "122086"
    assert calculation["discounts_used"] == ["57.5", "3", "10"]
    assert calculation["discount_origin"] == "temporary"
    assert client.get(f"/api/products/{product_id}").json()["rule"] is None
    assert client.get("/api/rules").json()["items"] == before_rules


def test_explicit_zero_is_valid_for_temporary_calculation(client):
    response = client.post("/api/products/implementos-0051-E/calculate", json={
        "discounts": ["57.5", "3", "0"], "profit_mode": "markup",
        "profit_value": "25", "rounding_increment": "1",
    })
    assert response.status_code == 200
    assert response.json()["distributor_cost"] == "108521.10"
    assert response.json()["discount_origin"] == "temporary"


def test_catalog_search_includes_family_and_description(client):
    catalog = client.get("/api/products", params={"page_size": 300}).json()["items"]
    sample = next(item for item in catalog if item["family"] != "Familia por confirmar")
    name_fragment = sample["name"].split()[0]
    by_name = client.get("/api/products", params={"search": name_fragment, "page_size": 300}).json()
    by_family = client.get("/api/products", params={"search": sample["family"], "page_size": 300}).json()
    assert any(name_fragment.casefold() in item["name"].casefold() for item in by_name["items"])
    assert any(item["family"] == sample["family"] for item in by_family["items"])


def test_corrected_rastra_families_are_complete_and_separate(client):
    type_sur = client.get("/api/products", params={
        "family": "Rastra de tiro con llantas tipo sur", "page_size": 300,
    }).json()
    light = client.get("/api/products", params={
        "family": "Rastra de tiro light", "page_size": 300,
    }).json()
    assert type_sur["filtered"] == 16
    assert light["filtered"] == 10
    assert {"RT-20 24 X 3/16", "RT-20 24 X 1/4", "RT-22 24 X 1/4", "RT-22 26 X 1/4"}.issubset(
        {item["name"] for item in type_sur["items"]}
    )
    assert all("LIGHT" not in item["name"].upper() for item in type_sur["items"])
    assert all("LIGHT" in item["name"].upper() for item in light["items"])


def test_fixed_discounts_cannot_be_changed_but_third_can_be_decimal(client):
    product_id = "implementos-0051-E"
    rejected = client.post(f"/api/products/{product_id}/calculate", json={
        "discounts": ["57", "3", "10"], "profit_mode": "markup",
        "profit_value": "25", "rounding_increment": "1",
    })
    accepted = client.post(f"/api/products/{product_id}/calculate", json={
        "discounts": ["57.5", "3", "8.25"], "profit_mode": "markup",
        "profit_value": "25", "rounding_increment": "1",
    })
    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["discounts_used"] == ["57.5", "3", "8.25"]


def test_required_products_via_api(client):
    first = client.get("/api/products/implementos-0089-I").json()
    second = client.get("/api/products/implementos-0103-I").json()
    assert first["calculation"]["distributor_cost"] == "30527.19"
    assert first["calculation"]["suggested_price"] == "38159"
    assert second["calculation"]["distributor_cost"] == "33681.65"
    assert second["calculation"]["suggested_price"] == "42102"


def test_profit_changes_and_rounding(client):
    response = client.post("/api/products/implementos-0089-I/calculate", json={
        "profit_mode": "fixed", "profit_value": "1000", "rounding_increment": "100"
    })
    assert response.status_code == 200
    assert response.json()["suggested_price"] == "31600"


def test_product_default_markup_is_persisted(client):
    product_id = "implementos-0089-I"
    response = client.request("PATCH", f"/api/products/{product_id}", json={"default_markup_pct": "31.5"})
    assert response.status_code == 200
    product = client.get(f"/api/products/{product_id}").json()
    assert product["default_markup_pct"] == "31.5"
    assert product["calculation"]["profit_value"] == "31.5"


def test_fixed_profit_and_rounding_preference_is_persisted(client):
    product_id = "implementos-0089-I"
    response = client.put(f"/api/products/{product_id}/commercial-preference", json={
        "profit_mode": "fixed", "profit_value": "1250.50", "rounding_increment": "50"
    })
    assert response.status_code == 200
    product = client.get(f"/api/products/{product_id}").json()
    assert product["commercial_preference"]["profit_mode"] == "fixed"
    assert product["commercial_preference"]["profit_value"] == "1250.50"
    assert product["commercial_preference"]["rounding_increment"] == "50"
    assert product["commercial_preference"]["updated_at"]


def test_family_preview_does_not_modify_rules(client):
    before = client.get("/api/products", params={"page_size": 300}).json()["counts"]
    response = client.post("/api/rules/preview", json={
        "scope_type": "family", "scope_key": "Cultivadoras", "product_ids": [],
        "rule": {"discounts": ["57.5", "3", "5"]},
    })
    assert response.status_code == 200
    assert response.json()["affected_count"] == 22
    after = client.get("/api/products", params={"page_size": 300}).json()["counts"]
    assert after == before


def test_confirmed_discounts_remain_exactly_on_22_products(client):
    catalog = client.get("/api/products", params={"page_size": 300}).json()
    configured = [item for item in catalog["items"] if item["status"] == "configured"]
    assert len(configured) == 22
    assert all(item["rule"]["discounts"] == ["57.5", "3", "10"] for item in configured)
    assert all(item["rule"]["scope_type"] == "family" for item in configured)


def test_preview_apply_override_and_explicit_zero(client):
    product_id = "implementos-0009-A"
    bad_zero = client.put("/api/rules", json={
        "scope_type": "product", "scope_key": product_id,
        "rule": {"discounts": ["57", "3", "0"], "explicit_zero": False},
    })
    assert bad_zero.status_code == 422
    preview = client.post("/api/rules/preview", json={
        "product_ids": [product_id], "rule": {"discounts": ["57.5", "3", "0"]}
    })
    assert preview.status_code == 200
    apply = client.put("/api/rules", json={
        "scope_type": "product", "scope_key": product_id,
        "rule": {"discounts": ["57.5", "3", "0"]},
    })
    assert apply.status_code == 200
    configured = client.get(f"/api/products/{product_id}").json()
    assert configured["status"] == "configured"
    assert configured["rule"]["scope_type"] == "product"
    assert configured["rule"]["discounts"] == ["57.5", "3", "0"]


def test_bulk_family_and_family_rule(client):
    ids = ["implementos-0009-A", "implementos-0010-A"]
    assert client.post("/api/products/bulk-family", json={"product_ids": ids, "family": "Prueba"}).status_code == 200
    assert client.put("/api/rules", json={
        "scope_type": "family", "scope_key": "Prueba", "rule": {"discounts": ["57.5", "3", "8"]}
    }).status_code == 200
    assert all(client.get(f"/api/products/{product_id}").json()["status"] == "configured" for product_id in ids)


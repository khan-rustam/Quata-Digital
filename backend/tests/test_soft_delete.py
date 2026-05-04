def test_delete_product_hides_from_public(client, admin_headers):
    # Find a seeded product to soft-delete.
    listing = client.get("/api/v1/products").json()
    assert listing, "expected seeded products"
    target = listing[0]
    pid = target["id"]
    slug = target["slug"]

    # Soft-delete via admin endpoint.
    r = client.delete(f"/api/v1/admin/products/{pid}", headers=admin_headers)
    assert r.status_code == 204, r.text

    # Public list no longer shows it.
    after = client.get("/api/v1/products").json()
    assert all(p["id"] != pid for p in after)

    # Public detail returns 404.
    detail = client.get(f"/api/v1/products/{slug}")
    assert detail.status_code == 404

    # Trash listing surfaces it for the admin.
    trash = client.get("/api/v1/admin/trash/products", headers=admin_headers)
    assert trash.status_code == 200
    assert any(item["id"] == pid for item in trash.json())

    # Restore the product and check it's public again.
    rr = client.post(
        f"/api/v1/admin/trash/products/{pid}/restore", headers=admin_headers
    )
    assert rr.status_code == 200
    again = client.get("/api/v1/products").json()
    assert any(p["id"] == pid for p in again)

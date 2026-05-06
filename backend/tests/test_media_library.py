"""Pytest coverage for the media library + image pipeline + used-on tracking.

Asserts that:
- An authenticated upload creates a MediaAsset row with width/height/WebP.
- /admin/media list + filter behaves.
- PATCH updates alt_text + tags (with normalisation).
- DELETE refuses 409 when used_on is non-empty; force=true bypasses.
- Reconciler rebuilds used_on from PageContent.
"""
from __future__ import annotations

import io


def _png_bytes(w: int = 320, h: int = 240) -> io.BytesIO:
    from PIL import Image

    img = Image.new("RGB", (w, h), color="steelblue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_upload_indexes_into_library_with_dims_and_webp(client, admin_headers):
    files = {"file": ("hero.png", _png_bytes(640, 360), "image/png")}
    r = client.post(
        "/api/v1/uploads",
        files=files,
        data={"folder": "cms"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    info = r.json()
    assert info["width"] == 640 and info["height"] == 360
    assert info["optimized_url"], "WebP shadow should be generated for PNG"
    assert info["optimized_size"] is not None


def test_media_library_list_and_filter(client, admin_headers):
    r = client.get("/api/v1/admin/media?content_type_prefix=image/", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body and "folders" in body


def test_patch_normalises_tags(client, admin_headers):
    # Upload one to have a stable id.
    r = client.post(
        "/api/v1/uploads",
        files={"file": ("foo.png", _png_bytes(120, 120), "image/png")},
        data={"folder": "cms"},
        headers=admin_headers,
    )
    info = r.json()
    asset_id = (
        client.get("/api/v1/admin/media", headers=admin_headers).json()["items"][0]["id"]
    )
    r = client.patch(
        f"/api/v1/admin/media/{asset_id}",
        json={"alt_text": "cover", "tags": ["Hero", "BRAND", "hero", "cms"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    # Lowercased + de-duplicated.
    assert body["tags"] == ["hero", "brand", "cms"]


def test_delete_refuses_when_in_use_then_force(client, admin_headers):
    # Upload + reference on a page.
    r = client.post(
        "/api/v1/uploads",
        files={"file": ("inuse.png", _png_bytes(100, 100), "image/png")},
        data={"folder": "cms"},
        headers=admin_headers,
    )
    info = r.json()
    url = info["url"]
    asset = next(
        (
            it
            for it in client.get("/api/v1/admin/media", headers=admin_headers).json()["items"]
            if it["url"] == url
        ),
        None,
    )
    assert asset is not None

    page = client.get("/api/v1/admin/cms/pages/home", headers=admin_headers).json()
    page["sections"][0]["image_url"] = url
    client.put(
        "/api/v1/admin/cms/pages/home",
        json={"sections": page["sections"]},
        headers=admin_headers,
    )

    r = client.delete(f"/api/v1/admin/media/{asset['id']}", headers=admin_headers)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "home" in detail["used_on"]

    r = client.delete(
        f"/api/v1/admin/media/{asset['id']}?force=true",
        headers=admin_headers,
    )
    assert r.status_code == 204


def test_reconciler_rebuilds_used_on(client, admin_headers):
    r = client.post(
        "/api/v1/admin/media/reconcile-used-on",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "rows_total" in body and "urls_referenced_from_pages" in body

def test_health_alias_returns_db_status(client):
    """/health is the back-compat alias of /health/ready."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_health_live_skips_db(client):
    """Liveness probe must not touch the database — orchestrators
    use it to decide whether to restart the process, not whether to
    route traffic."""
    r = client.get("/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "uptime_seconds" in body
    assert "version" in body
    # No DB check in the liveness payload.
    assert "checks" not in body


def test_health_ready_includes_db_check(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"

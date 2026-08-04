from __future__ import annotations

from app import create_app


def _login(client, admin=True):
    with client.session_transaction() as session:
        session["user"] = {"id": 1, "username": "tester", "is_admin": admin}
        session["is_admin"] = admin


def test_existing_and_new_endpoints_are_compatible(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/api/live/tracks").status_code == 401

    _login(client)
    stats = client.get("/stats")
    assert stats.status_code == 200
    assert stats.get_json()["areas"] == []
    stream = client.get("/video_feed", buffered=False)
    assert stream.status_code == 200
    assert next(stream.response).startswith(b"--frame")
    stream.close()
    assert client.post("/add_area", json={}).status_code == 400

    status = client.get("/api/calibration/status")
    assert status.status_code == 200
    assert "missing_intrinsics" in status.get_json()["blockers"]
    tracks = client.get("/api/live/tracks")
    assert tracks.status_code == 200
    assert tracks.get_json()["coordinateSystem"]["unit"] == "meter"
    assert client.get("/configuration").status_code == 200


def test_scene_mutations_allow_regular_authenticated_user(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()
    
    # Sin sesión debe rebotar con 401
    assert client.post("/api/scene/objects", json={}).status_code == 401
    assert client.get("/users/").status_code == 302

    # Con sesión de usuario regular (no admin), debe poder acceder a la escena pero no a usuarios
    _login(client, admin=False)
    response = client.post("/api/scene/objects", json={})
    assert response.status_code != 401
    assert response.status_code != 403  # Ya no es 403 para usuarios autenticados
    
    # Pero el módulo de usuarios sigue bloqueado para no administradores
    user_mgmt = client.get("/users/")
    assert user_mgmt.status_code == 302  # Redirige con flash por falta de rol admin


def test_demo_sites_expose_corridor_contract_without_login(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()

    sites = client.get("/api/v1/sites")
    assert sites.status_code == 200
    assert [item["siteId"] for item in sites.get_json()["items"]] == [
        "pasillo-real",
        "sitio-simulado",
    ]

    bootstrap = client.get("/api/v1/sites/pasillo-real/bootstrap")
    assert bootstrap.status_code == 200
    payload = bootstrap.get_json()
    assert [area["areaId"] for area in payload["areas"]] == [
        "zona-cercana",
        "zona-media",
        "zona-lejana",
    ]
    assert payload["scenes"][0]["coordinateSystem"]["unit"] == "meter"

    points = client.get("/api/v1/sites/pasillo-real/track-points")
    state = client.get("/api/v1/sites/pasillo-real/area-state")
    assert points.status_code == 200
    assert points.get_json() == {"items": [], "nextCursor": None}
    assert state.status_code == 200
    assert {item["areaId"] for item in state.get_json()["items"]} == {
        "zona-cercana",
        "zona-media",
        "zona-lejana",
    }


def test_api_rate_limit_returns_retryable_429(vision_config, monkeypatch):
    monkeypatch.setenv("API_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("API_GLOBAL_RATE_LIMIT_REQUESTS", "10")
    monkeypatch.setenv("API_RATE_LIMIT_WINDOW_SECONDS", "10")
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()

    assert client.get("/api/v1/sites").status_code == 200
    assert client.get("/api/v1/sites").status_code == 200
    limited = client.get("/api/v1/sites")
    assert limited.status_code == 429
    assert limited.get_json()["code"] == "rate_limit_exceeded"
    assert limited.headers["Retry-After"] == "10"


def test_camera_stream_is_limited_per_user_and_released(vision_config, monkeypatch):
    monkeypatch.setenv("MAX_MJPEG_STREAMS", "2")
    monkeypatch.setenv("MAX_MJPEG_STREAMS_PER_USER", "1")
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()
    _login(client)

    first = client.get("/video_feed", buffered=False)
    assert first.status_code == 200
    assert next(first.response).startswith(b"--frame")
    assert client.get("/video_feed", buffered=False).status_code == 429
    first.close()

    reopened = client.get("/video_feed", buffered=False)
    assert reopened.status_code == 200
    reopened.close()


def test_area_crud_is_reflected_by_live_bootstrap(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()
    _login(client)

    created = client.post(
        "/add_area",
        json={"name": "Area temporal", "x1": 100, "y1": 420, "x2": 300, "y2": 620},
    )
    assert created.status_code == 201
    area_id = created.get_json()["area"]["id"]
    external_id = created.get_json()["area"]["external_id"]
    bootstrap = client.get("/api/v1/sites/pasillo-real/bootstrap").get_json()
    assert any(area["areaId"] == external_id for area in bootstrap["areas"])

    updated = client.patch(
        f"/areas/{area_id}",
        json={"name": "Area editada", "x1": 120, "y1": 430, "x2": 320, "y2": 630},
    )
    assert updated.status_code == 200
    bootstrap = client.get("/api/v1/sites/pasillo-real/bootstrap").get_json()
    assert next(area for area in bootstrap["areas"] if area["areaId"] == external_id)["name"] == "Area editada"

    assert client.delete(f"/areas/{area_id}").status_code == 200
    bootstrap = client.get("/api/v1/sites/pasillo-real/bootstrap").get_json()
    assert all(area["areaId"] != external_id for area in bootstrap["areas"])


def test_local_areas_survive_application_restart(vision_config):
    first_app = create_app(start_background=False, vision_config=vision_config)
    first_app.extensions["tracker_service"].add_local_area(
        "Area persistente", 100, 400, 280, 620, external_id="area-persistente"
    )

    restarted_app = create_app(start_background=False, vision_config=vision_config)
    restarted_app.config.update(TESTING=True)
    bootstrap = restarted_app.test_client().get(
        "/api/v1/sites/pasillo-real/bootstrap"
    ).get_json()
    assert any(
        area["areaId"] == "area-persistente" and area["name"] == "Area persistente"
        for area in bootstrap["areas"]
    )


def test_local_demo_admin_login_requires_explicit_flag(vision_config, monkeypatch):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    app.extensions["api_client"].login = lambda *_: None
    client = app.test_client()

    monkeypatch.delenv("LOCAL_DEMO_AUTH", raising=False)
    denied = client.post("/login", data={"username": "admin", "password": "root"})
    assert denied.status_code == 200
    with client.session_transaction() as local_session:
        assert "user" not in local_session

    monkeypatch.setenv("LOCAL_DEMO_AUTH", "1")
    accepted = client.post("/login", data={"username": "admin", "password": "root"})
    assert accepted.status_code == 302
    assert accepted.headers["Location"].endswith("/")
    with client.session_transaction() as local_session:
        assert local_session["user"]["username"] == "admin"
        assert local_session["is_admin"] is True


def test_demo_login_stays_disabled_outside_local_environment(vision_config, monkeypatch):
    monkeypatch.setenv("LOCAL_DEMO_AUTH", "1")
    monkeypatch.setenv("APP_ENV", "production")
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    app.extensions["api_client"].login = lambda *_: None
    client = app.test_client()

    response = client.post("/login", data={"username": "admin", "password": "root"})
    assert response.status_code == 200
    with client.session_transaction() as local_session:
        assert "user" not in local_session


def test_area_state_and_alert_use_pixel_area_count_without_world_position(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    tracker = app.extensions["tracker_service"]
    area = tracker.add_local_area(
        "Prueba alerta", 10, 10, 200, 200, external_id="area-alerta"
    )
    with tracker.lock:
        tracker.areas[area["id"]]["current_count"] = 1
        tracker.latest_tracks = [
            {"trackerId": "7", "positionValid": False, "imagePoint": {"u": 50, "v": 50}}
        ]
    client = app.test_client()
    _login(client)
    created = client.post(
        "/api/v1/sites/pasillo-real/alerts",
        json={
            "areaId": "area-alerta", "areaName": "Prueba alerta",
            "type": "crowding", "thresholdPeople": 1,
        },
    )
    assert created.status_code == 201
    state = client.get("/api/v1/sites/pasillo-real/area-state").get_json()["items"]
    assert next(item for item in state if item["areaId"] == "area-alerta")["peopleCount"] == 1
    alerts = client.get("/api/v1/sites/pasillo-real/alerts").get_json()["items"]
    assert alerts[0]["status"] == "triggered"


def test_deleting_area_removes_area_and_related_alerts(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()
    _login(client)
    created_area = client.post(
        "/add_area",
        json={"name": "Temporal", "x1": 10, "y1": 10, "x2": 200, "y2": 200},
    ).get_json()["area"]
    client.post(
        "/api/v1/sites/pasillo-real/alerts",
        json={
            "areaId": created_area["external_id"], "areaName": "Temporal",
            "type": "crowding", "thresholdPeople": 2,
        },
    )
    assert client.delete(f"/areas/{created_area['id']}").status_code == 200
    bootstrap = client.get("/api/v1/sites/pasillo-real/bootstrap").get_json()
    assert all(a["areaId"] != created_area["external_id"] for a in bootstrap["areas"])
    alerts = client.get("/api/v1/sites/pasillo-real/alerts").get_json()["items"]
    assert all(a["areaId"] != created_area["external_id"] for a in alerts)


def test_local_user_crud_and_login_work_without_central_server(vision_config, monkeypatch):
    monkeypatch.setenv("LOCAL_DEMO_AUTH", "1")
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    client = app.test_client()
    _login(client)

    created = client.post(
        "/users/create",
        data={"username": "operador2", "password": "secreto", "is_admin": "on"},
    )
    assert created.status_code == 302
    user = app.extensions["local_user_store"].list()[0]
    updated = client.post(
        f"/users/edit/{user['id']}",
        data={"username": "operador-editado", "password": "nuevo", "is_admin": "on"},
    )
    assert updated.status_code == 302
    client.get("/logout")
    login = client.post(
        "/login", data={"username": "operador-editado", "password": "nuevo"}
    )
    assert login.status_code == 302
    with client.session_transaction() as local_session:
        assert local_session["user"]["username"] == "operador-editado"
    assert client.post(f"/users/delete/{user['id']}").status_code == 302
    assert app.extensions["local_user_store"].list() == []

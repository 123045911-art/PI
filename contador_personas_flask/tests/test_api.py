from __future__ import annotations

from app import create_app


def _install_fake_central_api(app):
    """Aísla las pruebas Flask sin depender de un FastAPI externo encendido."""
    api = app.extensions["api_client"]
    alerts = []

    def create_alert(_site_id, payload):
        item = {
            **payload,
            "id": payload.get("id", f"test-alert-{len(alerts) + 1}"),
            "status": payload.get("status", "watching"),
            "peopleCountSnapshot": payload.get("peopleCountSnapshot", 0),
        }
        alerts.insert(0, item)
        return item

    def evaluate_alerts(_site_id, counts):
        for item in alerts:
            count = int(counts.get(item["areaId"], 0))
            item["peopleCountSnapshot"] = count
            threshold = int(item.get("thresholdPeople", 0))
            item["status"] = "triggered" if count >= threshold else "watching"
        return alerts

    def sync_alert_area(external_id, *, name=None, delete=False):
        if delete:
            alerts[:] = [item for item in alerts if item["areaId"] != external_id]
        elif name:
            for item in alerts:
                if item["areaId"] == external_id:
                    item["areaName"] = name
        return True

    def delete_alert(_site_id, alert_id):
        before = len(alerts)
        alerts[:] = [item for item in alerts if item["id"] != alert_id]
        return len(alerts) != before

    api.list_alerts = lambda _site_id: list(alerts)
    api.create_alert = create_alert
    api.evaluate_alerts = evaluate_alerts
    api.delete_alert = delete_alert
    api.sync_alert_area = sync_alert_area
    api.create_area = lambda **payload: {"id": 99, **payload}
    api.delete_area = lambda _area_id: True
    return alerts


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
    assert payload["areas"] == []
    assert payload["scenes"][0]["coordinateSystem"]["unit"] == "meter"

    points = client.get("/api/v1/sites/pasillo-real/track-points")
    state = client.get("/api/v1/sites/pasillo-real/area-state")
    assert points.status_code == 200
    assert points.get_json() == {"items": [], "nextCursor": None}
    assert state.status_code == 200
    assert state.get_json()["items"] == []


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


def test_login_always_uses_central_api_even_with_demo_flag(vision_config, monkeypatch):
    monkeypatch.setenv("LOCAL_DEMO_AUTH", "1")
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    attempts = []

    def central_login(username, password):
        attempts.append((username, password))
        if (username, password) != ("admin", "visioflow123"):
            return None
        return {
            "user": {"id": 1, "username": "admin", "is_admin": True},
            "access_token": "central-token",
        }

    app.extensions["api_client"].login = central_login
    client = app.test_client()

    denied = client.post("/login", data={"username": "admin", "password": "root"})
    assert denied.status_code == 200
    with client.session_transaction() as local_session:
        assert "user" not in local_session

    accepted = client.post("/login", data={"username": "admin", "password": "visioflow123"})
    assert accepted.status_code == 302
    assert accepted.headers["Location"].endswith("/")
    assert attempts == [("admin", "root"), ("admin", "visioflow123")]
    with client.session_transaction() as local_session:
        assert local_session["user"]["username"] == "admin"
        assert local_session["is_admin"] is True
        assert local_session["access_token"] == "central-token"


def test_login_shows_central_connection_error(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    api = app.extensions["api_client"]
    api.login = lambda *_: None
    api.last_error = "No fue posible conectar con el servidor de autenticación."
    client = app.test_client()

    response = client.post("/login", data={"username": "admin", "password": "visioflow123"})
    assert response.status_code == 200
    assert b"servidor de autenticaci" in response.data
    with client.session_transaction() as local_session:
        assert "user" not in local_session


def test_area_state_and_alert_use_pixel_area_count_without_world_position(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    _install_fake_central_api(app)
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
    _install_fake_central_api(app)
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


def test_user_crud_in_flask_uses_central_api(vision_config):
    app = create_app(start_background=False, vision_config=vision_config)
    app.config.update(TESTING=True)
    api = app.extensions["api_client"]
    users = []

    def register_user(**payload):
        user = {
            "id": 7,
            "username": payload["username"],
            "is_admin": payload["is_admin_val"],
        }
        users.append(user)
        return user

    api.register_user = register_user
    api.list_users = lambda **_: list(users)
    api.get_user = lambda user_id, **_: next((u for u in users if u["id"] == user_id), None)
    api.update_user = lambda **payload: users[0].update(
        username=payload["username"], is_admin=payload["is_admin_val"]
    ) is None
    api.delete_user = lambda user_id, **_: bool(users.pop(0)) if users and users[0]["id"] == user_id else False
    api.login = lambda username, password: {
        "user": {**users[0]}, "access_token": "operator-token"
    } if users and username == users[0]["username"] and password == "Nuevo123" else None

    client = app.test_client()
    _login(client)

    created = client.post(
        "/users/create",
        data={"username": "operador2", "password": "Secreto1", "is_admin": "on"},
    )
    assert created.status_code == 302
    assert users[0]["username"] == "operador2"
    updated = client.post(
        "/users/edit/7",
        data={"username": "operador-editado", "password": "Nuevo123", "is_admin": "on"},
    )
    assert updated.status_code == 302
    client.get("/logout")
    login = client.post(
        "/login", data={"username": "operador-editado", "password": "Nuevo123"}
    )
    assert login.status_code == 302
    with client.session_transaction() as local_session:
        assert local_session["user"]["username"] == "operador-editado"
    assert client.post("/users/delete/7").status_code == 302
    assert users == []

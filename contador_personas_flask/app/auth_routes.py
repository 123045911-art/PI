import os

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash

auth_bp = Blueprint("auth", __name__)

def get_api_client():
    return current_app.extensions["api_client"]


def local_demo_login_enabled() -> bool:
    """Allow fixed demo credentials only when explicitly enabled on a local run."""
    return (
        os.getenv("APP_ENV", "production").strip().lower() == "local"
        and os.getenv("LOCAL_DEMO_AUTH", "0") == "1"
    )

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if local_demo_login_enabled() and username == "admin" and password == "root":
            result = {
                "user": {
                    "id": "local-demo-admin",
                    "username": "admin",
                    "is_admin": True,
                },
                "access_token": None,
            }
        elif local_demo_login_enabled():
            user = current_app.extensions["local_user_store"].authenticate(
                username, password
            )
            result = {"user": user, "access_token": None} if user else None
        else:
            client = get_api_client()
            result = client.login(username, password)
        
        if result and "user" in result:
            user_data = result["user"]
            access_token = result.get("access_token")
            session["user"] = user_data
            session["is_admin"] = user_data.get("is_admin", False)
            session["access_token"] = access_token
            if access_token:
                get_api_client().set_user_token(access_token)
            flash(f"Bienvenido, {user_data['username']}!", "success")
            return redirect(url_for("main.index"))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")
            
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("auth.login"))

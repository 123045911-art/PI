import os

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash, abort

user_bp = Blueprint("users", __name__, url_prefix="/users")

def get_api_client():
    return current_app.extensions["api_client"]

def local_users_enabled():
    return os.getenv("APP_ENV", "production").lower() == "local" and os.getenv("LOCAL_DEMO_AUTH", "0") == "1"

def get_local_store():
    return current_app.extensions["local_user_store"]

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Acceso denegado: Se requieren permisos de administrador.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return decorated_function

@user_bp.route("/")
@admin_required
def index():
    name_filter = request.args.get("name")
    api_users = get_api_client().list_users(name_filter=name_filter, is_admin=session.get("is_admin", False))
    local_users = get_local_store().list(name_filter)

    seen = set()
    combined = []
    for u in (api_users or []) + (local_users or []):
        uid = str(u.get("id") or u.get("username"))
        if uid not in seen:
            seen.add(uid)
            combined.append(u)

    return render_template("users/index.html", users=combined)

@user_bp.route("/create", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        is_admin = request.form.get("is_admin") == "on"
        
        result = get_api_client().register_user(
            username=username,
            password=password,
            is_admin_val=is_admin,
            current_user_is_admin=session.get("is_admin", False),
        )
        if not result:
            result = get_local_store().create(username, password, is_admin)

        if result:
            flash(f"Usuario {username} creado exitosamente.", "success")
            return redirect(url_for("users.index"))
        flash("Error al crear el usuario. El nombre puede estar en uso.", "danger")
        
    return render_template("users/edit.html", user=None)

@user_bp.route("/edit/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit(user_id):
    client = get_api_client()
    user = client.get_user(user_id, current_user_is_admin=session.get("is_admin", False)) or get_local_store().get(user_id)
    if not user:
        abort(404)
        
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password") or None
        is_admin = request.form.get("is_admin") == "on"
        
        success = client.update_user(
            user_id=user_id,
            username=username,
            password=password,
            is_admin_val=is_admin,
            current_user_is_admin=session.get("is_admin", False),
        )
        if not success:
            success = get_local_store().update(user_id, username, password, is_admin)

        if success:
            flash(f"Usuario {username} actualizado.", "success")
            return redirect(url_for("users.index"))
        flash("Error al actualizar el usuario.", "danger")
        
    return render_template("users/edit.html", user=user)

@user_bp.route("/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete(user_id):
    deleted = get_api_client().delete_user(user_id, current_user_is_admin=session.get("is_admin", False))
    if not deleted:
        deleted = get_local_store().delete(user_id)

    if deleted:
        flash("Usuario eliminado.", "success")
    else:
        flash("Error al eliminar el usuario.", "danger")
    return redirect(url_for("users.index"))

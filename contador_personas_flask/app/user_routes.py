from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash, abort

user_bp = Blueprint("users", __name__, url_prefix="/users")

def get_api_client():
    return current_app.extensions["api_client"]

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
    client = get_api_client()
    users = client.list_users(name_filter=name_filter, is_admin=session.get("is_admin", False))
    return render_template("users/index.html", users=users)

@user_bp.route("/create", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        is_admin = request.form.get("is_admin") == "on"
        
        client = get_api_client()
        result = client.register_user(
            username=username, 
            password=password, 
            is_admin_val=is_admin,
            current_user_is_admin=session.get("is_admin", False)
        )
        if result:
            flash(f"Usuario {username} creado exitosamente.", "success")
            return redirect(url_for("users.index"))
        flash("Error al crear el usuario. El nombre puede estar en uso.", "danger")
        
    return render_template("users/edit.html", user=None)

@user_bp.route("/edit/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit(user_id):
    client = get_api_client()
    user = client.get_user(user_id, current_user_is_admin=session.get("is_admin", False))
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
            current_user_is_admin=session.get("is_admin", False)
        )
        if success:
            flash(f"Usuario {username} actualizado.", "success")
            return redirect(url_for("users.index"))
        flash("Error al actualizar el usuario.", "danger")
        
    return render_template("users/edit.html", user=user)

@user_bp.route("/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete(user_id):
    client = get_api_client()
    if client.delete_user(user_id, current_user_is_admin=session.get("is_admin", False)):
        flash("Usuario eliminado.", "success")
    else:
        flash("Error al eliminar el usuario.", "danger")
    return redirect(url_for("users.index"))

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash

auth_bp = Blueprint("auth", __name__)

def get_api_client():
    return current_app.extensions["api_client"]

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        client = get_api_client()
        result = client.login(username, password)
        
        if result and "user" in result:
            user_data = result["user"]
            session["user"] = user_data
            session["is_admin"] = user_data.get("is_admin", False)
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

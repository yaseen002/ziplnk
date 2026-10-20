"""
Ziplnk - Production-grade URL shortener with Authentication
Flask application for creating and managing shortened URLs with user authentication.
"""

from flask import Flask, render_template, request, redirect, jsonify, session, url_for
import string
import random
import os
from datetime import datetime
from functools import wraps
from database import (
    init_db,
    create_user,
    get_user_by_username,
    get_user_by_id,
    verify_password,
    create_short_url,
    get_url,
    get_all_urls,
    get_user_urls,
    delete_url,
    get_stats,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Initialize database on startup
init_db()


def generate_short_code(length: int = 6) -> str:
    """Generate a random short code for URL shortening."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin access for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        
        user = get_user_by_id(session["user_id"])
        if not user or not user["is_admin"]:
            return render_template("403.html"), 403
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        if not username or not email or not password:
            return render_template("register.html", error="All fields are required")
        
        if len(username) < 3:
            return render_template("register.html", error="Username must be at least 3 characters")
        
        if len(password) < 6:
            return render_template("register.html", error="Password must be at least 6 characters")
        
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        # Create user
        if create_user(username, email, password):
            return redirect(url_for("login", success="Account created successfully! Please log in."))
        else:
            return render_template("register.html", error="Username or email already exists")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("login.html", error="Username and password are required")

        if verify_password(username, password):
            user = get_user_by_username(username)
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = user["is_admin"]
            
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password")

    success = request.args.get("success")
    return render_template("login.html", success=success)


@app.route("/logout")
def logout():
    """User logout."""
    session.clear()
    return redirect(url_for("index"))


# ============================================================================
# MAIN ROUTES
# ============================================================================

@app.route("/")
def index():
    """Home page - URL shortener form."""
    is_logged_in = "user_id" in session
    return render_template("index.html", is_logged_in=is_logged_in)


@app.route("/dashboard")
@login_required
def dashboard():
    """User dashboard - view created links."""
    user_id = session.get("user_id")
    user = get_user_by_id(user_id)
    urls = get_user_urls(user_id)
    stats = get_stats()
    
    return render_template(
        "dashboard.html",
        urls=urls,
        stats=stats,
        is_admin=False,
        username=user["username"]
    )


@app.route("/admin")
@admin_required
def admin():
    """Admin dashboard - view all links and statistics."""
    urls = get_all_urls()
    stats = get_stats()
    
    return render_template(
        "dashboard.html",
        urls=urls,
        stats=stats,
        is_admin=True,
        username=session.get("username")
    )


# ============================================================================
# API ROUTES
# ============================================================================

@app.route("/api/shorten", methods=["POST"])
def shorten_url():
    """API endpoint to create a shortened URL."""
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400

    original_url = data.get("url", "").strip()

    # Basic URL validation
    if not original_url.startswith(("http://", "https://")):
        original_url = "https://" + original_url

    if len(original_url) < 10:
        return jsonify({"error": "Invalid URL"}), 400

    # Get user_id if logged in
    user_id = session.get("user_id") if "user_id" in session else None

    # Generate unique short code
    max_attempts = 10
    for _ in range(max_attempts):
        short_code = generate_short_code()
        if create_short_url(short_code, original_url, user_id):
            return jsonify(
                {
                    "success": True,
                    "short_code": short_code,
                    "short_url": f"{request.host_url}{short_code}",
                    "original_url": original_url,
                }
            ), 201

    return jsonify({"error": "Failed to generate short code"}), 500


@app.route("/<short_code>")
def redirect_to_url(short_code: str):
    """Redirect to the original URL."""
    url_data = get_url(short_code)

    if url_data:
        return redirect(url_data["original_url"])
    else:
        return render_template("404.html", short_code=short_code), 404


@app.route("/api/urls", methods=["GET"])
@login_required
def get_urls_api():
    """API endpoint to get user's URLs."""
    user_id = session.get("user_id")
    urls = get_user_urls(user_id)
    return jsonify(urls), 200


@app.route("/api/admin/urls", methods=["GET"])
@admin_required
def get_all_urls_api():
    """API endpoint to get all URLs (admin)."""
    urls = get_all_urls()
    return jsonify(urls), 200


@app.route("/api/admin/stats", methods=["GET"])
def get_stats_api():
    """API endpoint to get statistics."""
    stats = get_stats()
    return jsonify(stats), 200


@app.route("/api/delete/<short_code>", methods=["DELETE"])
@login_required
def delete_url_api(short_code: str):
    """API endpoint to delete a shortened URL."""
    if delete_url(short_code):
        return jsonify({"success": True, "message": "URL deleted"}), 200
    else:
        return jsonify({"error": "URL not found"}), 404


@app.route("/api/url/<short_code>", methods=["GET"])
def get_url_info(short_code: str):
    """API endpoint to get information about a shortened URL."""
    url_data = get_url(short_code)

    if url_data:
        return jsonify(url_data), 200
    else:
        return jsonify({"error": "URL not found"}), 404


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors."""
    return render_template("403.html"), 403


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)

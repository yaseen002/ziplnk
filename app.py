"""
Ziplnk - Production-grade URL shortener
Flask application for creating and managing shortened URLs.
"""

from flask import Flask, render_template, request, redirect, jsonify, session
import string
import random
import os
from datetime import datetime
from database import (
    init_db,
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


@app.route("/")
def index():
    """Home page - URL shortener form."""
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    """User dashboard - view created links."""
    user_id = session.get("user_id", "anonymous")
    urls = get_user_urls(user_id)
    stats = get_stats()
    return render_template("dashboard.html", urls=urls, stats=stats, is_admin=False)


@app.route("/admin")
def admin():
    """Admin dashboard - view all links and statistics."""
    # In production, this should require authentication
    urls = get_all_urls()
    stats = get_stats()
    return render_template("dashboard.html", urls=urls, stats=stats, is_admin=True)


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

    # Generate unique short code
    max_attempts = 10
    for _ in range(max_attempts):
        short_code = generate_short_code()
        if create_short_url(short_code, original_url):
            user_id = session.get("user_id")
            if not user_id:
                user_id = f"user_{generate_short_code(8)}"
                session["user_id"] = user_id

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
def get_urls_api():
    """API endpoint to get user's URLs."""
    user_id = session.get("user_id", "anonymous")
    urls = get_user_urls(user_id)
    return jsonify(urls), 200


@app.route("/api/admin/urls", methods=["GET"])
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


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

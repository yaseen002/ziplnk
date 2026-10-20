"""
Comprehensive test suite for Ziplnk URL shortener.
Tests cover API endpoints, database operations, and error handling.
"""

import pytest
import os
import json
from app import app, generate_short_code
from database import (
    init_db,
    create_short_url,
    get_url,
    get_all_urls,
    get_user_urls,
    delete_url,
    get_stats,
    DATABASE_PATH,
)


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test."""
    # Remove existing test database if it exists
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
    
    # Initialize fresh database
    init_db()
    
    yield
    
    # Cleanup
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    # Use a test database
    app.config["TESTING"] = True
    
    with app.test_client() as client:
        yield client


class TestDatabaseOperations:
    """Test database module functions."""

    def test_create_short_url(self):
        """Test creating a new shortened URL."""
        result = create_short_url("abc123", "https://example.com/very/long/url")
        assert result is True

    def test_create_duplicate_short_code(self):
        """Test that duplicate short codes are rejected."""
        create_short_url("abc123", "https://example.com/url1")
        result = create_short_url("abc123", "https://example.com/url2")
        assert result is False

    def test_get_url(self):
        """Test retrieving a URL and incrementing click count."""
        create_short_url("test123", "https://example.com")
        url_data = get_url("test123")
        
        assert url_data is not None
        assert url_data["short_code"] == "test123"
        assert url_data["original_url"] == "https://example.com"
        assert url_data["click_count"] == 1

    def test_get_url_increments_clicks(self):
        """Test that click count increments on each retrieval."""
        create_short_url("click123", "https://example.com")
        
        get_url("click123")
        url_data1 = get_url("click123")
        assert url_data1["click_count"] == 2
        
        url_data2 = get_url("click123")
        assert url_data2["click_count"] == 3

    def test_get_nonexistent_url(self):
        """Test retrieving a non-existent URL."""
        result = get_url("nonexistent")
        assert result is None

    def test_get_all_urls(self):
        """Test retrieving all URLs."""
        create_short_url("url1", "https://example.com/1")
        create_short_url("url2", "https://example.com/2")
        create_short_url("url3", "https://example.com/3")
        
        urls = get_all_urls()
        assert len(urls) == 3

    def test_get_user_urls(self):
        """Test retrieving URLs for a specific user."""
        create_short_url("user1_url1", "https://example.com/1", "user1")
        create_short_url("user1_url2", "https://example.com/2", "user1")
        create_short_url("user2_url1", "https://example.com/3", "user2")
        
        user1_urls = get_user_urls("user1")
        user2_urls = get_user_urls("user2")
        
        assert len(user1_urls) == 2
        assert len(user2_urls) == 1

    def test_delete_url(self):
        """Test deleting a URL."""
        create_short_url("delete_me", "https://example.com")
        
        result = delete_url("delete_me")
        assert result is True
        
        url_data = get_url("delete_me")
        assert url_data is None

    def test_delete_nonexistent_url(self):
        """Test deleting a non-existent URL."""
        result = delete_url("nonexistent")
        assert result is False

    def test_get_stats(self):
        """Test getting statistics."""
        create_short_url("stat1", "https://example.com/1", "user1")
        create_short_url("stat2", "https://example.com/2", "user2")
        
        get_url("stat1")
        get_url("stat1")
        get_url("stat2")
        
        stats = get_stats()
        assert stats["total_urls"] == 2
        assert stats["total_clicks"] == 3
        assert stats["total_users"] == 2


class TestFlaskApp:
    """Test Flask application endpoints."""

    def test_index_page(self, client):
        """Test the home page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Ziplnk" in response.data

    def test_dashboard_page(self, client):
        """Test the dashboard page loads."""
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"Dashboard" in response.data

    def test_admin_page(self, client):
        """Test the admin page loads."""
        response = client.get("/admin")
        assert response.status_code == 200
        assert b"Admin Dashboard" in response.data

    def test_shorten_url_valid(self, client):
        """Test shortening a valid URL."""
        response = client.post(
            "/api/shorten",
            data=json.dumps({"url": "https://example.com/very/long/url"}),
            content_type="application/json",
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True
        assert "short_code" in data
        assert "short_url" in data
        assert data["original_url"] == "https://example.com/very/long/url"

    def test_shorten_url_without_protocol(self, client):
        """Test shortening a URL without http/https protocol."""
        response = client.post(
            "/api/shorten",
            data=json.dumps({"url": "example.com"}),
            content_type="application/json",
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True

    def test_shorten_url_missing_url(self, client):
        """Test shortening without providing a URL."""
        response = client.post(
            "/api/shorten",
            data=json.dumps({}),
            content_type="application/json",
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_shorten_url_invalid_url(self, client):
        """Test shortening an invalid URL (too short)."""
        response = client.post(
            "/api/shorten",
            data=json.dumps({"url": "a"}),
            content_type="application/json",
        )
        
        assert response.status_code == 400

    def test_redirect_to_url(self, client):
        """Test redirecting to original URL."""
        # Create a shortened URL
        create_short_url("redirect_test", "https://example.com")
        
        # Test redirect
        response = client.get("/redirect_test", follow_redirects=False)
        assert response.status_code == 302
        assert response.location == "https://example.com"

    def test_redirect_nonexistent(self, client):
        """Test redirecting to non-existent short code."""
        response = client.get("/nonexistent_code")
        assert response.status_code == 404

    def test_get_urls_api(self, client):
        """Test getting user's URLs via API."""
        create_short_url("api_url1", "https://example.com/1")
        
        response = client.get("/api/urls")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_get_all_urls_api(self, client):
        """Test getting all URLs via API."""
        create_short_url("all_url1", "https://example.com/1")
        create_short_url("all_url2", "https://example.com/2")
        
        response = client.get("/api/admin/urls")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2

    def test_get_stats_api(self, client):
        """Test getting statistics via API."""
        create_short_url("stat_url", "https://example.com")
        get_url("stat_url")
        
        response = client.get("/api/admin/stats")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "total_urls" in data
        assert "total_clicks" in data
        assert "total_users" in data

    def test_delete_url_api(self, client):
        """Test deleting a URL via API."""
        create_short_url("delete_api", "https://example.com")
        
        response = client.delete("/api/delete/delete_api")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_delete_nonexistent_url_api(self, client):
        """Test deleting a non-existent URL via API."""
        response = client.delete("/api/delete/nonexistent")
        assert response.status_code == 404

    def test_get_url_info(self, client):
        """Test getting URL info via API."""
        create_short_url("info_url", "https://example.com")
        
        response = client.get("/api/url/info_url")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["short_code"] == "info_url"
        assert data["original_url"] == "https://example.com"

    def test_get_nonexistent_url_info(self, client):
        """Test getting info for non-existent URL."""
        response = client.get("/api/url/nonexistent")
        assert response.status_code == 404


class TestUtilityFunctions:
    """Test utility functions."""

    def test_generate_short_code_length(self):
        """Test that generated short codes have correct length."""
        code = generate_short_code(6)
        assert len(code) == 6

    def test_generate_short_code_uniqueness(self):
        """Test that generated short codes are unique."""
        codes = [generate_short_code() for _ in range(100)]
        assert len(codes) == len(set(codes))

    def test_generate_short_code_characters(self):
        """Test that generated short codes contain valid characters."""
        import string
        valid_chars = string.ascii_letters + string.digits
        code = generate_short_code()
        assert all(c in valid_chars for c in code)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

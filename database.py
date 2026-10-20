"""
Database module for Ziplnk URL shortener.
Handles SQLite database operations for storing shortened URLs and user authentication.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_PATH = "ziplnk.db"


def init_db() -> None:
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0
        )
        """
    )

    # Create URLs table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            click_count INTEGER DEFAULT 0,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    # Create click history table for analytics
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS click_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT NOT NULL,
            clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_agent TEXT,
            ip_address TEXT,
            FOREIGN KEY (short_code) REFERENCES urls(short_code)
        )
        """
    )

    conn.commit()
    conn.close()


# ============================================================================
# USER AUTHENTICATION FUNCTIONS
# ============================================================================

def create_user(username: str, email: str, password: str) -> bool:
    """
    Create a new user account.

    Args:
        username: Username for the account
        email: Email address
        password: Plain text password (will be hashed)

    Returns:
        True if successful, False if user already exists
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, email, password_hash),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Get user by username.

    Args:
        username: Username to look up

    Returns:
        User data dictionary or None if not found
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, email, password_hash, created_at, is_admin
        FROM users WHERE username = ?
        """,
        (username,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "password_hash": row[3],
            "created_at": row[4],
            "is_admin": row[5],
        }
    return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get user by ID.

    Args:
        user_id: User ID to look up

    Returns:
        User data dictionary or None if not found
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, email, created_at, is_admin
        FROM users WHERE id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "created_at": row[3],
            "is_admin": row[4],
        }
    return None


def verify_password(username: str, password: str) -> bool:
    """
    Verify user password.

    Args:
        username: Username
        password: Plain text password to verify

    Returns:
        True if password is correct, False otherwise
    """
    user = get_user_by_username(username)
    if user:
        return check_password_hash(user["password_hash"], password)
    return False


# ============================================================================
# URL SHORTENING FUNCTIONS
# ============================================================================

def create_short_url(short_code: str, original_url: str, user_id: Optional[int] = None) -> bool:
    """
    Create a new shortened URL entry.

    Args:
        short_code: The short code for the URL
        original_url: The original long URL
        user_id: The user ID who created this link (None for anonymous)

    Returns:
        True if successful, False if short_code already exists
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO urls (short_code, original_url, user_id)
            VALUES (?, ?, ?)
            """,
            (short_code, original_url, user_id),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def get_url(short_code: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a URL by its short code and increment click count.

    Args:
        short_code: The short code to look up

    Returns:
        Dictionary with URL data or None if not found
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, short_code, original_url, created_at, click_count, user_id
        FROM urls WHERE short_code = ?
        """,
        (short_code,),
    )

    row = cursor.fetchone()
    if row:
        # Increment click count
        cursor.execute(
            "UPDATE urls SET click_count = click_count + 1 WHERE short_code = ?",
            (short_code,),
        )
        conn.commit()

        # Record click history
        cursor.execute(
            """
            INSERT INTO click_history (short_code, user_agent, ip_address)
            VALUES (?, ?, ?)
            """,
            (short_code, "", ""),
        )
        conn.commit()

        result = {
            "id": row[0],
            "short_code": row[1],
            "original_url": row[2],
            "created_at": row[3],
            "click_count": row[4] + 1,
            "user_id": row[5],
        }
        conn.close()
        return result

    conn.close()
    return None


def get_all_urls() -> List[Dict[str, Any]]:
    """
    Retrieve all shortened URLs (admin view).

    Returns:
        List of all URL entries
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT u.id, u.short_code, u.original_url, u.created_at, u.click_count, 
               COALESCE(us.username, 'Anonymous') as username
        FROM urls u
        LEFT JOIN users us ON u.user_id = us.id
        ORDER BY u.created_at DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "short_code": row[1],
            "original_url": row[2],
            "created_at": row[3],
            "click_count": row[4],
            "username": row[5],
        }
        for row in rows
    ]


def get_user_urls(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve all URLs created by a specific user.

    Args:
        user_id: The user ID to filter by

    Returns:
        List of URL entries for the user
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, short_code, original_url, created_at, click_count, user_id
        FROM urls WHERE user_id = ? ORDER BY created_at DESC
        """,
        (user_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "short_code": row[1],
            "original_url": row[2],
            "created_at": row[3],
            "click_count": row[4],
            "user_id": row[5],
        }
        for row in rows
    ]


def delete_url(short_code: str) -> bool:
    """
    Delete a shortened URL entry.

    Args:
        short_code: The short code to delete

    Returns:
        True if successful, False if not found
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM urls WHERE short_code = ?", (short_code,))
    conn.commit()

    deleted = cursor.rowcount > 0
    conn.close()

    return deleted


def get_stats() -> Dict[str, Any]:
    """
    Get overall statistics about the URL shortener.

    Returns:
        Dictionary with statistics
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM urls")
    total_urls = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(click_count) FROM urls")
    total_clicks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM urls WHERE user_id IS NOT NULL")
    total_users = cursor.fetchone()[0]

    conn.close()

    return {
        "total_urls": total_urls,
        "total_clicks": total_clicks,
        "total_users": total_users,
    }


def get_user_stats(user_id: int) -> Dict[str, Any]:
    """
    Get statistics for a specific user.

    Args:
        user_id: The user ID to get stats for

    Returns:
        Dictionary with user-specific statistics
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM urls WHERE user_id = ?", (user_id,))
    total_urls = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(click_count) FROM urls WHERE user_id = ?", (user_id,))
    total_clicks = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "total_urls": total_urls,
        "total_clicks": total_clicks,
    }

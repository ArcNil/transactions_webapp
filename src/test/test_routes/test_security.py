"""
Security tests — authentication bypass.

Every protected route must redirect an anonymous (unauthenticated) client to
/login with a 302 status.  These tests verify that @login_required is applied
on all routes and cannot be bypassed by crafting a direct request.
"""

import json
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assert_redirects_to_login(response):
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

def test_logout_requires_login(client):
    assert_redirects_to_login(client.get("/logout"))


# ---------------------------------------------------------------------------
# Dashboard routes
# ---------------------------------------------------------------------------

def test_root_requires_login(client):
    assert_redirects_to_login(client.get("/"))


def test_dashboard_requires_login(client):
    assert_redirects_to_login(client.get("/dashboard"))


def test_chart_api_requires_login(client):
    assert_redirects_to_login(client.get("/api/dashboard/chart"))


# ---------------------------------------------------------------------------
# POS routes
# ---------------------------------------------------------------------------

def test_pos_index_requires_login(client):
    assert_redirects_to_login(client.get("/pos/"))


def test_pos_save_requires_login(client):
    response = client.post(
        "/pos/save",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": json.dumps([{"product_id": 1, "quantity": "1"}]),
        },
    )
    assert_redirects_to_login(response)


# ---------------------------------------------------------------------------
# Products routes
# ---------------------------------------------------------------------------

def test_products_index_requires_login(client):
    assert_redirects_to_login(client.get("/products/"))


def test_products_add_requires_login(client):
    response = client.post(
        "/products/add",
        data={"name": "Water", "unit": "gallon", "price": "50.00"},
    )
    assert_redirects_to_login(response)


def test_products_edit_requires_login(client):
    response = client.post(
        "/products/1/edit",
        data={"name": "Water", "unit": "gallon", "price": "50.00"},
    )
    assert_redirects_to_login(response)


def test_products_delete_requires_login(client):
    assert_redirects_to_login(client.post("/products/1/delete"))


# ---------------------------------------------------------------------------
# Customers routes
# ---------------------------------------------------------------------------

def test_customers_index_requires_login(client):
    assert_redirects_to_login(client.get("/customers/"))


def test_customers_add_requires_login(client):
    assert_redirects_to_login(client.post("/customers/add", data={"name": "Juan"}))


def test_customers_edit_requires_login(client):
    assert_redirects_to_login(client.post("/customers/1/edit", data={"name": "Juan"}))


def test_customers_delete_requires_login(client):
    assert_redirects_to_login(client.post("/customers/1/delete"))


# ---------------------------------------------------------------------------
# Transactions routes
# ---------------------------------------------------------------------------

def test_transactions_index_requires_login(client):
    assert_redirects_to_login(client.get("/transactions/"))


def test_transactions_edit_requires_login(client):
    response = client.post(
        "/transactions/1/edit",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": json.dumps([{"product_id": 1, "quantity": "1"}]),
        },
    )
    assert_redirects_to_login(response)


# ---------------------------------------------------------------------------
# Settings routes
# ---------------------------------------------------------------------------

def test_settings_index_requires_login(client):
    assert_redirects_to_login(client.get("/settings/"))


def test_settings_change_credentials_requires_login(client):
    response = client.post(
        "/settings/change-credentials",
        data={
            "new_username": "hacker",
            "current_password": "anything",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert_redirects_to_login(response)


def test_settings_add_user_requires_login(client):
    response = client.post(
        "/settings/users/add",
        data={"username": "newuser", "password": "pass123", "confirm_password": "pass123"},
    )
    assert_redirects_to_login(response)


def test_settings_delete_user_requires_login(client):
    assert_redirects_to_login(client.post("/settings/users/1/delete"))


def test_settings_edit_user_requires_login(client):
    assert_redirects_to_login(
        client.post("/settings/users/1/edit", data={"username": "hacker", "password": ""})
    )

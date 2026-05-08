import json


def test_root_redirects_to_login_when_not_authenticated(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_dashboard_redirects_to_login_when_not_authenticated(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_dashboard_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/dashboard")
    assert response.status_code == 200
    assert b"H2O" in response.data


def test_chart_data_returns_json_with_required_keys(logged_in_client):
    response = logged_in_client.get("/api/dashboard/chart")
    assert response.status_code == 200
    payload = json.loads(response.data)
    assert "labels" in payload
    assert "revenue" in payload
    assert "expenses" in payload
    assert "net" in payload


def test_chart_data_returns_7_entries(logged_in_client):
    response = logged_in_client.get("/api/dashboard/chart")
    payload = json.loads(response.data)
    assert len(payload["labels"]) == 7
    assert len(payload["revenue"]) == 7
    assert len(payload["expenses"]) == 7
    assert len(payload["net"]) == 7


def test_chart_data_returns_correct_revenue_for_today(
    logged_in_client, sample_transaction, db_session
):
    response = logged_in_client.get("/api/dashboard/chart")
    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["revenue"][-1] == 100.0

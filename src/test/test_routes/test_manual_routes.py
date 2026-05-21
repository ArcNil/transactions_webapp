def test_manual_redirects_to_login_when_not_authenticated(client):
    response = client.get("/manual/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_manual_returns_200_for_regular_admin(logged_in_client):
    response = logged_in_client.get("/manual/")
    assert response.status_code == 200
    assert b"User Manual" in response.data


def test_manual_does_not_show_finance_section_for_regular_admin(logged_in_client):
    response = logged_in_client.get("/manual/")
    assert b'id="finance"' not in response.data


def test_manual_does_not_show_monitoring_section_for_regular_admin(logged_in_client):
    response = logged_in_client.get("/manual/")
    assert b'id="monitoring"' not in response.data


def test_manual_returns_200_for_superadmin(logged_in_superadmin_client):
    response = logged_in_superadmin_client.get("/manual/")
    assert response.status_code == 200
    assert b"User Manual" in response.data


def test_manual_shows_finance_section_for_superadmin(logged_in_superadmin_client):
    response = logged_in_superadmin_client.get("/manual/")
    assert b'id="finance"' in response.data


def test_manual_shows_monitoring_section_for_superadmin(logged_in_superadmin_client):
    response = logged_in_superadmin_client.get("/manual/")
    assert b'id="monitoring"' in response.data

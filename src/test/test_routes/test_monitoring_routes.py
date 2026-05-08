def test_monitoring_redirects_unauthenticated_user_to_login(client):
    response = client.get("/monitoring/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_monitoring_returns_403_for_admin(logged_in_client):
    response = logged_in_client.get("/monitoring/")
    assert response.status_code == 403


def test_monitoring_returns_200_for_superadmin(logged_in_superadmin_client):
    response = logged_in_superadmin_client.get("/monitoring/")
    assert response.status_code == 200
    assert b"monitoring" in response.data.lower()


def test_monitoring_stream_redirects_unauthenticated_user(client):
    response = client.get("/monitoring/stream", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_monitoring_stream_returns_403_for_admin(logged_in_client):
    response = logged_in_client.get("/monitoring/stream")
    assert response.status_code == 403


def test_monitoring_stream_returns_200_for_superadmin(logged_in_superadmin_client):
    response = logged_in_superadmin_client.get("/monitoring/stream", buffered=False)
    assert response.status_code == 200
    assert "text/event-stream" in response.content_type

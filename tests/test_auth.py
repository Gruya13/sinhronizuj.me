import pytest

def test_register_user_success(client):
    """
    Testira uspesnu registraciju korisnika.
    """
    payload = {
        "email": "testuser@sinhronizuj.me",
        "password": "Password123!"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "uspešno" in response.json()["message"]

def test_register_duplicate_email(client):
    """
    Testira registraciju sa vec postojecim emailom (treba da vrati 400).
    """
    payload = {
        "email": "testuser@sinhronizuj.me",
        "password": "Password123!"
    }
    # Prva registracija
    client.post("/api/v1/auth/register", json=payload)
    
    # Druga registracija sa istim emailom
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "već postoji" in response.json()["detail"]

def test_login_success(client):
    """
    Testira uspesan login i dobijanje JWT tokena.
    """
    # Prvo registrujemo korisnika
    register_payload = {
        "email": "loginuser@sinhronizuj.me",
        "password": "SecretPassword123"
    }
    client.post("/api/v1/auth/register", json=register_payload)
    
    # Pokusaj prijave
    login_payload = {
        "email": "loginuser@sinhronizuj.me",
        "password": "SecretPassword123"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"
    assert response.json()["user"]["email"] == "loginuser@sinhronizuj.me"

def test_login_invalid_credentials(client):
    """
    Testira prijavu sa pogresnim kredencijalima (treba da vrati 401).
    """
    login_payload = {
        "email": "nonexistent@sinhronizuj.me",
        "password": "WrongPassword123"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "Pogrešan email" in response.json()["detail"]

def test_auth_me_unauthorized(client):
    """
    Testira pristup /auth/me ruti bez tokena (treba da vrati 401).
    """
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_auth_me_success(client):
    """
    Testira uspesno preuzimanje profila sa validnim JWT tokenom.
    """
    # 1. Registracija
    email = "me_user@sinhronizuj.me"
    register_payload = {
        "email": email,
        "password": "MySecretPassword123"
    }
    client.post("/api/v1/auth/register", json=register_payload)
    
    # 2. Login
    response = client.post("/api/v1/auth/login", json=register_payload)
    token = response.json()["access_token"]
    
    # 3. Pristup /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == email
    assert "id" in response.json()

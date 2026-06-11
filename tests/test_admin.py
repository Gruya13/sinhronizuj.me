import pytest

def test_admin_routes_forbidden_for_regular_user(client):
    """
    Testira da običan ulogovani korisnik dobija 403 Forbidden za admin rute.
    """
    # 1. Registracija i prijava običnog korisnika
    email = "regular@sinhronizuj.me"
    payload = {"email": email, "password": "Password123!"}
    client.post("/api/v1/auth/register", json=payload)
    
    login_resp = client.post("/api/v1/auth/login", json=payload)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Pokušaj pristupa admin stats
    response = client.get("/api/v1/admin/stats", headers=headers)
    assert response.status_code == 403
    assert "Nemate administratorske privilegije" in response.json()["detail"]
    
    # 3. Pokušaj pristupa waitlist-i
    response = client.get("/api/v1/admin/waitlist", headers=headers)
    assert response.status_code == 403

def test_create_first_admin_and_access_routes(client):
    """
    Testira kreiranje prvog administratora i uspešan pristup admin rutama.
    """
    # 1. Kreiranje prvog admina preko endpointa
    admin_payload = {
        "email": "superadmin@sinhronizuj.me",
        "password": "SuperSecretPassword123"
    }
    response = client.post("/api/v1/admin/create-first-admin", json=admin_payload)
    assert response.status_code == 200
    assert "promovisan" in response.json()["message"]
    
    # 2. Pokušaj kreiranja još jednog prvog admina (treba da pukne sa 400)
    response2 = client.post("/api/v1/admin/create-first-admin", json={
        "email": "anotheradmin@sinhronizuj.me",
        "password": "Password123!"
    })
    assert response2.status_code == 400
    assert "Administrator već postoji" in response2.json()["detail"]
    
    # 3. Login sa admin nalogom
    login_resp = client.post("/api/v1/auth/login", json=admin_payload)
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["is_admin"] is True
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 4. Uspešan pristup admin stats
    stats_resp = client.get("/api/v1/admin/stats", headers=headers)
    assert stats_resp.status_code == 200
    assert "users" in stats_resp.json()
    assert "projects" in stats_resp.json()
    assert "costs" in stats_resp.json()

def test_waitlist_approval_flow(client):
    """
    Testira ceo tok odobravanja i odbijanja waitlist prijava.
    """
    # 1. Kreiramo admina
    admin_payload = {"email": "admin_wl@sinhronizuj.me", "password": "Password123!"}
    client.post("/api/v1/admin/create-first-admin", json=admin_payload)
    login_resp = client.post("/api/v1/auth/login", json=admin_payload)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Prijavljujemo e-mail na waitlist
    wl_email = "beta_tester@example.com"
    client.post("/api/v1/waitlist", json={"email": wl_email})
    
    # 3. Listamo waitlist kao admin
    wl_resp = client.get("/api/v1/admin/waitlist", headers=headers)
    assert wl_resp.status_code == 200
    entries = wl_resp.json()
    assert len(entries) > 0
    target_entry = [e for e in entries if e["email"] == wl_email][0]
    assert target_entry["status"] == "pending"
    
    # 4. Odobravamo prijavu
    app_resp = client.post(f"/api/v1/admin/waitlist/{target_entry['id']}/approve", headers=headers)
    assert app_resp.status_code == 200
    
    # 5. Proveravamo da je status promenjen
    wl_resp2 = client.get("/api/v1/admin/waitlist", headers=headers)
    target_entry2 = [e for e in wl_resp2.json() if e["email"] == wl_email][0]
    assert target_entry2["status"] == "approved"

def test_toggle_user_admin(client):
    """
    Testira da administrator može drugom korisniku dati admin prava.
    """
    # 1. Kreiramo prvog admina
    admin_payload = {"email": "boss@sinhronizuj.me", "password": "Password123!"}
    client.post("/api/v1/admin/create-first-admin", json=admin_payload)
    login_resp = client.post("/api/v1/auth/login", json=admin_payload)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Kreiramo običnog korisnika
    user_payload = {"email": "worker@sinhronizuj.me", "password": "Password123!"}
    client.post("/api/v1/auth/register", json=user_payload)
    
    # 3. Listamo korisnike da nađemo worker-a
    users_resp = client.get("/api/v1/admin/users", headers=headers)
    users = users_resp.json()
    worker_user = [u for u in users if u["email"] == "worker@sinhronizuj.me"][0]
    assert worker_user["is_admin"] is False
    
    # 4. Promovišemo worker-a u admina
    toggle_resp = client.post(f"/api/v1/admin/users/{worker_user['id']}/toggle-admin", headers=headers)
    assert toggle_resp.status_code == 200
    assert "administrator" in toggle_resp.json()["message"]
    
    # 5. Proveravamo da li worker sada može da se prijavi i dobije is_admin: True
    worker_login = client.post("/api/v1/auth/login", json=user_payload)
    assert worker_login.status_code == 200
    assert worker_login.json()["user"]["is_admin"] is True

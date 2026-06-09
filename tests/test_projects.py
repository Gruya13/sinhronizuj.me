import pytest

def get_auth_headers(client, email, password):
    """
    Pomocna funkcija za brzu registraciju i login i preuzimanje tokena.
    """
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_create_project_success(client):
    """
    Testira uspesno kreiranje novog projekta.
    """
    headers = get_auth_headers(client, "creator@sinhronizuj.me", "Pass12345!")
    payload = {"name": "Moj Test Projekat"}
    response = client.post("/api/v1/project", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Moj Test Projekat"
    assert response.json()["status"] == "empty"
    assert "id" in response.json()

def test_list_projects_isolation(client):
    """
    Testira da li korisnik vidi iskljucivo svoje projekte na dashboardu.
    """
    # Korisnik A kreira projekat
    headers_a = get_auth_headers(client, "user_a@sinhronizuj.me", "Pass12345!")
    client.post("/api/v1/project", json={"name": "Projekat A"}, headers=headers_a)
    
    # Korisnik B kreira projekat
    headers_b = get_auth_headers(client, "user_b@sinhronizuj.me", "Pass12345!")
    client.post("/api/v1/project", json={"name": "Projekat B"}, headers=headers_b)
    
    # Korisnik A lista projekte
    res_a = client.get("/api/v1/projects", headers=headers_a)
    assert res_a.status_code == 200
    projects_a = res_a.json()
    assert len(projects_a) == 1
    assert projects_a[0]["name"] == "Projekat A"
    
    # Korisnik B lista projekte
    res_b = client.get("/api/v1/projects", headers=headers_b)
    assert res_b.status_code == 200
    projects_b = res_b.json()
    assert len(projects_b) == 1
    assert projects_b[0]["name"] == "Projekat B"

def test_get_project_details_unauthorized_access(client):
    """
    Testira da li je blokiran pristup detaljima tudjeg projekta (treba da vrati 403).
    """
    # Korisnik A kreira projekat
    headers_a = get_auth_headers(client, "user_a@sinhronizuj.me", "Pass12345!")
    res_create = client.post("/api/v1/project", json={"name": "Tajni Projekat A"}, headers=headers_a)
    project_id = res_create.json()["id"]
    
    # Korisnik B pokusava da ucita projekat A
    headers_b = get_auth_headers(client, "user_b@sinhronizuj.me", "Pass12345!")
    response = client.get(f"/api/v1/project/{project_id}", headers=headers_b)
    assert response.status_code == 403
    assert "Nemate pravo pristupa" in response.json()["detail"]

def test_delete_project_unauthorized(client):
    """
    Testira da li je blokirano brisanje tudjeg projekta (treba da vrati 403).
    """
    # Korisnik A kreira projekat
    headers_a = get_auth_headers(client, "user_a@sinhronizuj.me", "Pass12345!")
    res_create = client.post("/api/v1/project", json={"name": "Projekat za brisanje"}, headers=headers_a)
    project_id = res_create.json()["id"]
    
    # Korisnik B pokusava da obrise projekat A
    headers_b = get_auth_headers(client, "user_b@sinhronizuj.me", "Pass12345!")
    response = client.delete(f"/api/v1/project/{project_id}", headers=headers_b)
    assert response.status_code == 403
    assert "Nemate pravo pristupa" in response.json()["detail"]

def test_delete_project_success(client):
    """
    Testira uspesno brisanje sopstvenog projekta.
    """
    headers = get_auth_headers(client, "owner@sinhronizuj.me", "Pass12345!")
    res_create = client.post("/api/v1/project", json={"name": "Moj Projekat"}, headers=headers)
    project_id = res_create.json()["id"]
    
    # Brisanje projekta
    response = client.delete(f"/api/v1/project/{project_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Provera da li je obrisan
    res_list = client.get("/api/v1/projects", headers=headers)
    assert len(res_list.json()) == 0

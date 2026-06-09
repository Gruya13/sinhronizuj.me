import random
import uuid
from locust import HttpUser, task, between

class SinhronizujUser(HttpUser):
    # Simulira vreme razmišljanja korisnika između akcija (1 do 5 sekundi)
    wait_time = between(1, 5)
    
    def on_start(self):
        """
        Pokreće se pri kreiranju svakog virtuelnog korisnika.
        Pokušava da registruje novog korisnika i zatim se prijavljuje.
        """
        self.email = f"loadtest_{uuid.uuid4().hex[:10]}@sinhronizuj.me"
        self.password = "LoadTestPass123!"
        self.auth_headers = {}
        self.project_ids = []
        self.active_project_id = None
        
        # 1. Registracija korisnika
        register_payload = {
            "email": self.email,
            "password": self.password
        }
        with self.client.post("/api/v1/auth/register", json=register_payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 400 and "već postoji" in response.text:
                # Ako korisnik već postoji, to je u redu za potrebe testa
                response.success()
            else:
                response.failure(f"Registracija neuspešna: {response.status_code} - {response.text}")
                return
                
        # 2. Prijava (Login)
        login_payload = {
            "email": self.email,
            "password": self.password
        }
        with self.client.post("/api/v1/auth/login", json=login_payload, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    token = response.json().get("access_token")
                    self.auth_headers = {"Authorization": f"Bearer {token}"}
                    response.success()
                except Exception as e:
                    response.failure(f"Greška pri parsiranju tokena: {e}")
            else:
                response.failure(f"Prijava neuspešna: {response.status_code} - {response.text}")

    @task(3)
    def view_dashboard(self):
        """
        Simulira pregled dashboard-a i listanje projekata.
        """
        if not self.auth_headers:
            return
            
        with self.client.get("/api/v1/projects", headers=self.auth_headers, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    projects = response.json()
                    self.project_ids = [p["id"] for p in projects]
                    response.success()
                except Exception as e:
                    response.failure(f"Greška pri parsiranju projekata: {e}")
            else:
                response.failure(f"Listanje projekata neuspešno: {response.status_code}")

    @task(1)
    def create_new_project(self):
        """
        Simulira kreiranje novog projekta.
        """
        if not self.auth_headers:
            return
            
        project_payload = {
            "name": f"Projekat LoadTest {uuid.uuid4().hex[:6]}"
        }
        with self.client.post("/api/v1/project", json=project_payload, headers=self.auth_headers, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    project_id = response.json().get("id")
                    if project_id:
                        self.project_ids.append(project_id)
                        self.active_project_id = project_id
                    response.success()
                except Exception as e:
                    response.failure(f"Greška pri parsiranju kreiranog projekta: {e}")
            else:
                response.failure(f"Kreiranje projekta neuspešno: {response.status_code}")

    @task(4)
    def work_in_studio(self):
        """
        Simulira rad u studiju: učitavanje projekta, čuvanje segmenata i izmenu teksta.
        """
        if not self.auth_headers or not self.project_ids:
            return
            
        # Odaberi nasumičan projekat od postojećih
        project_id = random.choice(self.project_ids)
        
        # 1. Učitavanje projekta (učitavanje nacrta i segmenta)
        with self.client.get(f"/api/v1/project/{project_id}", headers=self.auth_headers, catch_response=True) as response:
            if response.status_code == 200:
                try:
                    project_data = response.json()
                    segments = project_data.get("segments", [])
                    response.success()
                    
                    # 2. Ako projekat ima segmente, simuliraj rad na njima
                    if segments:
                        target_segment = random.choice(segments)
                        segment_id = target_segment["id"]
                        
                        # A. Simuliraj auto-save nakon izmene teksta
                        save_payload = {
                            "segments": [
                                {
                                    "id": segment_id,
                                    "start": target_segment["start"],
                                    "end": target_segment["end"],
                                    "original": target_segment["original"],
                                    "translated": f"Izmenjeni srpski prevod {uuid.uuid4().hex[:4]}",
                                    "voice_type": "clone",
                                    "volume": 0.0,
                                    "speed": 1.0,
                                    "pitch": 0.0,
                                    "bg_volume": 0.0
                                }
                            ]
                        }
                        self.client.post(
                            f"/api/v1/project/{project_id}/save",
                            json=save_payload,
                            headers=self.auth_headers
                        )
                        
                        # B. Simuliraj Magic Shorten AI lektora
                        shorten_payload = {
                            "text": target_segment["translated"]
                        }
                        self.client.post(
                            f"/api/v1/project/{project_id}/segment/{segment_id}/shorten",
                            json=shorten_payload,
                            headers=self.auth_headers
                        )
                        
                        # C. Simuliraj hot-patching preview (TTS)
                        tts_payload = {
                            "text": target_segment["translated"],
                            "voice_type": "clone",
                            "volume": 0.0,
                            "speed": 1.0,
                            "pitch": 0.0,
                            "bg_volume": 0.0
                        }
                        self.client.post(
                            f"/api/v1/project/{project_id}/segment/{segment_id}/tts",
                            json=tts_payload,
                            headers=self.auth_headers
                        )
                except Exception as e:
                    response.failure(f"Greška tokom simulacije studija: {e}")
            else:
                response.failure(f"Učitavanje projekta neuspešno: {response.status_code}")

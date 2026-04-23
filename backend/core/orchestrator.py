import requests
import json
from backend.core.config import settings

class RunPodOrchestrator:
    def __init__(self):
        self.api_key = settings.RUNPOD_API_KEY
        self.url = f"https://api.runpod.io/graphql?api_key={self.api_key}"
        self.headers = {"Content-Type": "application/json"}

    def _query(self, query):
        try:
            response = requests.post(self.url, json={'query': query}, headers=self.headers)
            return response.json()
        except Exception as e:
            print(f"RunPod Query Error: {e}")
            return None

    def list_my_pods(self):
        """
        Vraća listu svih aktivnih podova korisnika.
        """
        query = """
        query {
          myself {
            pods {
              id
              name
              runtime {
                uptimeInSeconds
                ports {
                  ip
                  isPublic
                  publicPort
                  privatePort
                }
              }
              machine {
                gpuDisplayName
              }
              desiredStatus
            }
          }
        }
        """
        data = self._query(query)
        if data and 'data' in data:
            return data['data']['myself']['pods']
        return []

    def get_pod_hw_utilization(self, pod_ip, public_port):
        """
        Pokušava da dobije HW stats direktno sa API-ja na podu (ako je aktivan).
        """
        try:
            # Pod pretpostavkom da je naš API izložen na public_port
            res = requests.get(f"http://{pod_ip}:{public_port}/api/v1/hw-stats", timeout=5)
            if res.status_code == 200:
                stats = res.json()
                # Proveravamo GPU load
                if stats['gpu'] and stats['gpu'][0]['load'] < 20:
                    return "FREE"
                return "BUSY"
        except:
            return "UNREACHABLE"
        return "UNKNOWN"

    def deploy_new_instance(self, gpu_type="NVIDIA GeForce RTX 3090"):
        """
        Automatski podiže novu RunPod instancu sa našim parametrima.
        """
        # Ovde bismo definisali templateId ili direktno parametre kontejnera
        # Za sada koristimo generičku mutaciju
        mutation = """
        mutation {
          podDeploy(input: {
            gpuTypeId: "%s",
            cloudType: SECURE,
            containerDiskSize: 40,
            volumeSize: 50,
            imageName: "pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime",
            dockerArgs: "git clone https://github.com/Gruya13/daca_dub.git /app && cd /app && docker-compose up -d",
            name: "Daca-Dub-Auto-Scale"
          }) {
            id
            desiredStatus
          }
        }
        """ % gpu_type
        
        return self._query(mutation)

    def find_best_pod(self):
        """
        Glavna logika: Nađi slobodan pod, ako nema - podigni novi.
        Vraća: {"pod_id": str, "address": str}
        """
        pods = self.list_my_pods()
        
        # 1. Tražimo pod koji je već Running i FREE
        for pod in pods:
            if pod['desiredStatus'] == 'RUNNING' and pod['runtime']:
                ports = pod['runtime']['ports']
                ip = ports[0]['ip'] if ports else None
                # Tražimo javni port koji je mapiran na 8000
                public_port = next((p['publicPort'] for p in ports if p['privatePort'] == 8000), None)
                
                if ip and public_port:
                    address = f"http://{ip}:{public_port}"
                    status = self.get_pod_hw_utilization(ip, public_port)
                    if status == "FREE":
                        print(f"[Orkestrator] Pronadjen slobodan pod: {pod['id']} na adresi {address}")
                        return {"pod_id": pod['id'], "address": address, "status": "EXISTING_FREE"}
        
        # 2. Ako nema slobodnih, podigni novi (VRAĆA ID, ali klijent će morati da sačeka IP)
        print("[Orkestrator] Svi podovi su zauzeti ili nedostupni. Podižem novu instancu...")
        new_pod_data = self.deploy_new_instance()
        new_id = new_pod_data.get('data', {}).get('podDeploy', {}).get('id')
        return {"pod_id": new_id, "address": None, "status": "DEPLOYING_NEW"}

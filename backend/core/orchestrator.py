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
                  isIpPublic
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
        # Mapiranje user-friendly imena na RunPod IDs ako je potrebno
        # RunPod obično prihvata i puno ime kao ID u nekim API verzijama
        
        mutation = """
        mutation {
          podFindAndDeployOnDemand(input: {
            cloudType: COMMUNITY,
            gpuCount: 1,
            volumeInGb: 50,
            volumeMountPath: "/workspace",
            containerDiskInGb: 40,
            minVcpuCount: 2,
            minMemoryInGb: 15,
            gpuTypeId: "%s",
            name: "Sinhronizuj-me-Nitro-%s",
            imageName: "pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime",
            dockerArgs: "bash -c 'git clone https://github.com/Gruya13/sinhronizuj_me.git /app && cd /app && pip install -r requirements.txt && uvicorn backend.main:app --host 0.0.0.0 --port 8000'"
          }) {
            id
            desiredStatus
          }
        }
        """ % (gpu_type, gpu_type.split()[-1])
        
        return self._query(mutation)

    def start_pod_safely(self, pod_id):
        """
        Pokušava da upali pod. Ako je HW zauzet na RunPod nivou (Exhausted),
        vraća grešku kako bi sistem znao da mora da traži dalje.
        """
        mutation = """
        mutation {
          podResume(input: {podId: "%s", gpuCount: 1}) {
            id
            desiredStatus
          }
        }
        """ % pod_id
        
        result = self._query(mutation)
        
        # Provera da li je RunPod vratio grešku o nedostatku resursa
        if result and 'errors' in result:
            error_msg = result['errors'][0].get('message', "").lower()
            if "not enough free gpus" in error_msg or "exhausted" in error_msg or "out of capacity" in error_msg:
                print(f"[Orkestrator] Pod {pod_id} ne može biti pokrenut: Nema slobodnog hardvera kod hosta.")
                return {"status": "EXHAUSTED", "error": "Nema slobodnih GPU resursa na host mašini za ovaj pod."}
            else:
                return {"status": "ERROR", "error": error_msg}
        
        return {"status": "SUCCESS", "data": result}

    def find_best_pod(self, gpu_type="NVIDIA GeForce RTX 3090", target_pod_id=None):
        """
        Glavna logika: Ako je target_pod_id prosleđen, koristi njega. 
        Inače, traži najbolji pod prema gpu_type ili skalira.
        """
        # Ako korisnik želi SKALIRANJE (specijalne komande iz UI)
        if target_pod_id == "NEW_3090":
            return self._deploy_and_return("NVIDIA GeForce RTX 3090")
        if target_pod_id == "NEW_4090":
            return self._deploy_and_return("NVIDIA GeForce RTX 4090")

        pods = self.list_my_pods()
        
        # 1. Tražimo specifičan pod ako je izabran
        if target_pod_id:
            pod = next((p for p in pods if p['id'] == target_pod_id), None)
            if pod:
                return self._check_and_prepare_pod(pod)

        # 2. Ako nije izabran, tražimo bilo koji slobodan koji odgovara tipu
        for pod in pods:
            pod_gpu = pod.get('machine', {}).get('gpuDisplayName', "")
            if gpu_type.lower() in pod_gpu.lower():
                res = self._check_and_prepare_pod(pod)
                if res: return res

        # 3. Ako ništa ne nađemo, skaliramo
        return self._deploy_and_return(gpu_type)

    def _check_and_prepare_pod(self, pod):
        if pod['desiredStatus'] == 'RUNNING' and pod['runtime']:
            ports = pod['runtime']['ports']
            ip = ports[0]['ip'] if ports else None
            public_port = next((p['publicPort'] for p in ports if p['privatePort'] == 8000), None)
            if ip and public_port:
                address = f"http://{ip}:{public_port}"
                if self.get_pod_hw_utilization(ip, public_port) == "FREE":
                    return {"pod_id": pod['id'], "address": address, "status": "EXISTING_FREE"}
        
        elif pod['desiredStatus'] == 'EXITED':
            start_result = self.start_pod_safely(pod['id'])
            if start_result['status'] == "SUCCESS":
                return {"pod_id": pod['id'], "address": None, "status": "WAKING_UP"}
            else:
                # Vraćamo grešku kako bismo je prikazali ili obradili
                return {"pod_id": pod['id'], "address": None, "status": start_result['status'], "error": start_result.get('error')}
        return None

    def _deploy_and_return(self, gpu_type):
        print(f"[Orkestrator] Skaliranje na novu {gpu_type} mašinu...")
        new_pod_data = self.deploy_new_instance(gpu_type)
        new_id = new_pod_data.get('data', {}).get('podFindAndDeployOnDemand', {}).get('id')
        
        if not new_id:
            print("[Orkestrator] Greška pri deploy-u:", new_pod_data)
            
        return {"pod_id": new_id, "address": None, "status": "DEPLOYING_NEW"}

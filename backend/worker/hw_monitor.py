import subprocess
import json

def get_gpu_stats():
    """
    Poziva nvidia-smi i vraća osnovne HW statistike u JSON formatu.
    """
    try:
        # nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        lines = result.stdout.strip().split("\n")
        gpu_stats = []
        
        for line in lines:
            load, mem_used, mem_total, temp = line.split(", ")
            gpu_stats.append({
                "load": int(load),
                "memory_used": int(mem_used),
                "memory_total": int(mem_total),
                "temperature": int(temp)
            })
            
        return gpu_stats
    except Exception as e:
        print(f"HW Monitor Greška: {e}")
        return []

def get_system_stats():
    """
    Dodatne sistemske informacije.
    """
    try:
        # CPU Load (jednostavna varijanta preko /proc/loadavg na Linuxu)
        with open("/proc/loadavg", "r") as f:
            load = f.read().split()[0]
        return {"cpu_load": load}
    except:
        return {"cpu_load": "N/A"}

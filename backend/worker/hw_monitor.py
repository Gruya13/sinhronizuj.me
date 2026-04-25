import subprocess
import psutil
import os

def get_gpu_stats():
    """
    Poziva nvidia-smi i vraća HW statistike. 
    Vraća praznu listu ako GPU nije prisutan ili drajver nije instaliran.
    """
    try:
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        lines = result.stdout.strip().split("\n")
        gpu_stats = []
        
        for line in lines:
            parts = line.split(", ")
            if len(parts) == 4:
                load, mem_used, mem_total, temp = parts
                gpu_stats.append({
                    "load": int(load),
                    "memory_used": int(mem_used),
                    "memory_total": int(mem_total),
                    "temperature": int(temp)
                })
        return gpu_stats
    except Exception:
        # Na Hetzner VPS-u bez GPU-a ovo će uvek biti putanja
        return []

def get_system_stats():
    """
    Vraća CPU i RAM statistiku koju frontend očekuje.
    """
    try:
        # psutil.cpu_percent(interval=None) vraća % od poslednjeg poziva
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        return {
            "cpu_usage": cpu_usage,
            "memory": {
                "percent": memory.percent,
                "used": int(memory.used / (1024 * 1024)),
                "total": int(memory.total / (1024 * 1024))
            }
        }
    except Exception as e:
        print(f"[HW MONITOR] Greška: {e}")
        return {"cpu_usage": 0, "memory": {"percent": 0}}

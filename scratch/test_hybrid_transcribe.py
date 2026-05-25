import os
import sys
from dotenv import load_dotenv

# Učitavanje okruženja
load_dotenv()

# Dodajemo koren projekta u sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.worker.transcriber import transcribe_audio
from backend.core.config import settings

def run_test():
    vocals_path = "temp_workspace/demucs_output/htdemucs/Why is an AI agent managing this store in San Francisco_ 🤔 #trendingshorts #ai #tech #future.publer.com/vocals.wav"
    
    if not os.path.exists(vocals_path):
        print(f"Fajl nije pronađen na putanji: {vocals_path}")
        return
        
    print(f"Pokrećem hibridnu transkripciju za: {vocals_path}")
    print(f"MODAL_STT_URL: {settings.MODAL_STT_URL}")
    print(f"MODAL_SENSEVOICE_URL: {settings.MODAL_SENSEVOICE_URL}")
    print(f"MODAL_LEKTOR_URL: {settings.MODAL_LEKTOR_URL}")
    
    # Dinamički initial prompt
    title = "Why is an AI agent managing this store in San Francisco_ 🤔 #trendingshorts #ai #tech #future"
    initial_prompt = f"This is a video about {title}. Please use correct punctuation: dots, commas, and capital letters. Spell names and technical terms correctly."
    
    print("\n--- Pokrećem transkripciju (ovo može potrajati oko 30-40s) ---")
    result = transcribe_audio(vocals_path, initial_prompt=initial_prompt)
    
    if result["status"] == "error":
        print(f"\nGreška pri transkripciji: {result['message']}")
    else:
        print("\n--- Uspešno završeno! ---")
        print(f"Jezik: {result['language']}")
        print(f"Puni tekst:\n{result['full_text']}\n")
        print("Segmenti (prvih 5):")
        for seg in result["segments"][:5]:
            print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s]: {seg['text']}")

if __name__ == "__main__":
    run_test()

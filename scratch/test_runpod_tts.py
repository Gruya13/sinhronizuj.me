import requests
import base64
import os

def test_tts():
    api_url = "http://localhost:8080/v1/tts"
    
    # Simple test payload
    payload = {
        "text": "Zdravo! Ovo je test Fish Speech jedan tačka pet modela na srpskom jeziku. Nadamo se da će zvučati odlično.",
        "references": [],
        "reference_id": None,
        "streaming": False,
        "format": "wav",
        "top_p": 0.7,
        "temperature": 0.7
    }
    
    print(f"Sending request to {api_url}...")
    try:
        response = requests.post(api_url, json=payload, timeout=300)
        response.raise_for_status()
        
        output_file = "test_output.wav"
        with open(output_file, "wb") as f:
            f.write(response.content)
            
        print(f"Success! Audio saved to {output_file}")
        print(f"File size: {os.path.getsize(output_file)} bytes")
        
    except Exception as e:
        print(f"Error during TTS request: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response content: {e.response.text}")

if __name__ == "__main__":
    test_tts()

import { useState, useEffect } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

// U produkciji ovaj URL bi isao preko ENV promenljive
const API_BASE_URL = "https://i8qik1kv4z44ty-8000.proxy.runpod.net";

function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState('');
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);

  // Efekat koji polluje server svake 3 sekunde da proveri status videa
  useEffect(() => {
    let interval;
    if (taskId && !videoUrl && !error) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/v1/status/${taskId}`);
          const data = await res.json();
          
          if (data.status === 'SUCCESS') {
            setVideoUrl(`${API_BASE_URL}${data.video_url}`);
            setStatus('Završeno!');
            setLoading(false);
            clearInterval(interval);
          } else if (data.status === 'FAILURE') {
            setError(data.error || 'Došlo je do greške pri obradi.');
            setStatus('Greška');
            setLoading(false);
            clearInterval(interval);
          } else {
            // Ako je pending ili started, prikazujemo
            setStatus(data.status || 'OBRADA U TOKU...');
          }
        } catch (err) {
          console.error("Greška pri proveri statusa:", err);
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [taskId, videoUrl, error]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true);
    setError(null);
    setVideoUrl(null);
    setTaskId(null);
    setStatus('POKRETANJE AI MODELA...');

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      
      const data = await res.json();
      if (data.status === 'success') {
        setTaskId(data.task_id);
      } else {
        setError(data.message || 'Greška pri slanju zahteva.');
        setLoading(false);
      }
    } catch (err) {
      setError('Nemoguće uspostaviti vezu sa serverom. Da li je API pokrenut?');
      setLoading(false);
    }
  };

  return (
    <div className="glass-container">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <h1>Daca Dub AI</h1>
        <p className="subtitle">Inteligentna sinhronizacija na srpski jezik</p>
      </motion.div>

      <form onSubmit={handleSubmit} className="input-group">
        <input 
          type="url" 
          placeholder="Unesite YouTube URL..." 
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={loading}
          required
        />
        <button type="submit" disabled={loading || !url}>
          {loading ? (
            <><Loader2 className="spinner" size={20} /> Obrađujem...</>
          ) : (
            <><Play size={20} /> Pokreni Sinhronizaciju</>
          )}
        </button>
      </form>

      <AnimatePresence>
        {(loading || status) && !videoUrl && !error && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }} 
            animate={{ opacity: 1, height: 'auto' }} 
            exit={{ opacity: 0, height: 0 }}
            className="status-card"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <Loader2 className="spinner" style={{ borderColor: 'rgba(99,102,241,0.3)', borderTopColor: '#6366f1' }} size={24} />
              <span style={{ fontWeight: 500, letterSpacing: '1px' }}>{status}</span>
            </div>
            <p style={{ marginTop: '12px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              (Ovo može potrajati nekoliko minuta. AI rutine detektuju lica, kloniraju glas i usklađuju usne...)
            </p>
          </motion.div>
        )}

        {error && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }} 
            animate={{ opacity: 1, scale: 1 }} 
            className="status-card error-text"
          >
            <AlertCircle size={24} style={{ margin: '0 auto 8px' }} />
            <p>{error}</p>
          </motion.div>
        )}

        {videoUrl && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }} 
            animate={{ opacity: 1, scale: 1 }} 
            className="video-container"
          >
            <div style={{ padding: '12px', background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 className="success-text" size={20} />
              <span className="success-text" style={{ fontWeight: 600 }}>Sinhronizacija završena!</span>
            </div>
            <video src={videoUrl} controls autoPlay />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;

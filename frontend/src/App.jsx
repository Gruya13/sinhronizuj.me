import { useState, useEffect } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

// API URL postavljen na localhost:8000 (preko SSH tunela ka RunPodu)
const API_BASE_URL = "http://localhost:8000";

function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(() => localStorage.getItem('daca_dub_task_id'));
  const [status, setStatus] = useState('');
  const [progressData, setProgressData] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);

  const STEPS = [
    "Preuzimanje završeno",
    "Vokal izolovan",
    "Govor prepoznat",
    "Tekst preveden",
    "Glas generisan",
    "Video spojen",
    "Obrada završena"
  ];

  // Inicijalno ucitavanje ako postoji task u memoriji
  useEffect(() => {
    if (taskId) {
        setLoading(true);
        setStatus('UČITAVANJE STATUSA...');
    }
  }, []);

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
            setProgressData({ percent: 100, completed_steps: STEPS });
            setLoading(false);
            localStorage.removeItem('daca_dub_task_id'); // Cistimo kad zavrsi
            clearInterval(interval);
          } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
            setError(data.error || 'Došlo je do greške pri obradi.');
            setStatus('Greška');
            setLoading(false);
            localStorage.removeItem('daca_dub_task_id');
            clearInterval(interval);
          } else {
            // Ako imamo progress_data, koristimo ga
            if (data.progress_data) {
              setProgressData(data.progress_data);
              setStatus(data.progress_data.current_step);
            } else {
              setStatus(data.status || 'ČEKANJE NA RED...');
            }
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
    setProgressData(null);
    setStatus('POKRETANJE...');

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      
      const data = await res.json();
      if (data.status === 'success') {
        setTaskId(data.task_id);
        localStorage.setItem('daca_dub_task_id', data.task_id);
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
            <div className="progress-section">
               <div className="progress-header">
                  <span className="current-step-text">{status}</span>
                  <span className="percent-text">{progressData?.percent || 0}%</span>
               </div>
               <div className="progress-bar-container">
                  <motion.div 
                    className="progress-bar-fill"
                    initial={{ width: 0 }}
                    animate={{ width: `${progressData?.percent || 0}%` }}
                  />
               </div>
            </div>

            <div className="steps-list">
              {STEPS.map((step, idx) => {
                const isCompleted = progressData?.completed_steps?.includes(step);
                const isCurrent = status.toLowerCase().includes(step.split(' ')[0].toLowerCase());
                
                return (
                  <div key={idx} className={`step-item ${isCompleted ? 'completed' : ''} ${isCurrent ? 'current' : ''}`}>
                    {isCompleted ? (
                      <CheckCircle2 size={16} className="step-icon success" />
                    ) : isCurrent ? (
                      <Loader2 size={16} className="step-icon spinner" />
                    ) : (
                      <div className="step-dot" />
                    )}
                    <span>{step}</span>
                  </div>
                );
              })}
            </div>
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

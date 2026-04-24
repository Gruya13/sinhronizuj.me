import { useState, useEffect, useRef } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle, Clock, Database, Cpu, Terminal, Eye, Zap, ArrowRight, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

const API_BASE_URL = "http://localhost:8000";

function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(() => localStorage.getItem('sinhronizuj_me_task_id'));
  const [status, setStatus] = useState('');
  const [progressData, setProgressData] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const [startTime, setStartTime] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [hwStats, setHwStats] = useState(null);
  const [logs, setLogs] = useState("");
  const [showLogs, setShowLogs] = useState(false);
  const [visualContextUrl, setVisualContextUrl] = useState(null);
  
  const feedRef = useRef(null);

  const STEPS = [
    "Preuzimanje završeno",
    "Vokal izolovan",
    "Govor prepoznat",
    "Tekst preveden",
    "Glas generisan",
    "Video spojen",
    "Obrada završena"
  ];

  // HW Monitoring polling (Local Hetzner Stats)
  useEffect(() => {
    const fetchHw = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/hw-stats`);
        const data = await res.json();
        setHwStats(data);
      } catch (err) { /* Silent fail */ }
    };
    fetchHw();
    const interval = setInterval(fetchHw, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (taskId) {
        setLoading(true);
        setStatus('UČITAVANJE...');
        setStartTime(Date.now());
    }
  }, []);

  // Tajmer za proteklo vreme
  useEffect(() => {
    let timer;
    if (loading && !videoUrl) {
      timer = setInterval(() => {
        setElapsed(Math.floor((Date.now() - (startTime || Date.now())) / 1000));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [loading, videoUrl, startTime]);

  // Scroll to bottom u feed-u
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [progressData?.segments]);

  // Polling za status zadatka
  useEffect(() => {
    let interval;
    if (taskId && !videoUrl && !error) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/v1/status/${taskId}`);
          const data = await res.json();
          
          if (data.status === 'SUCCESS') {
            setVideoUrl(`${API_BASE_URL}${data.video_url}`);
            setStatus('Sve završeno!');
            setProgressData({ percent: 100, completed_steps: STEPS });
            setLoading(false);
            localStorage.removeItem('sinhronizuj_me_task_id');
            clearInterval(interval);
          } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
            setError(data.error || 'Greška pri obradi.');
            setLoading(false);
            localStorage.removeItem('sinhronizuj_me_task_id');
            clearInterval(interval);
          } else {
            if (data.progress_data) {
              setProgressData(data.progress_data);
              setStatus(data.progress_data.current_step);
              if (data.progress_data.visual_context_url) {
                setVisualContextUrl(data.progress_data.visual_context_url);
              }
            } else {
              setStatus(data.status || 'ČEKANJE...');
            }
          }
        } catch (err) { console.error(err); }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [taskId, videoUrl, error]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true); setError(null); setVideoUrl(null); 
    setStartTime(Date.now()); setElapsed(0);
    setStatus('POVEZIVANJE SA KONTROLNOM TABLOM...');

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setTaskId(data.task_id);
        localStorage.setItem('sinhronizuj_me_task_id', data.task_id);
      } else { setError(data.message); setLoading(false); }
    } catch (err) { setError('Greška pri slanju zadatka. Proverite backend.'); setLoading(false); }
  };

  const formatTime = (s) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <>
      <div className="aurora-bg">
        <div className="aurora-blob" style={{ top: '10%', left: '10%' }}></div>
        <div className="aurora-blob" style={{ bottom: '10%', right: '10%', background: 'radial-gradient(circle, rgba(236, 72, 153, 0.15) 0%, transparent 70%)' }}></div>
      </div>

      <div className="glass-container studio-layout">
        {/* HIBRIDNI MONITOR */}
        <div className="hybrid-monitor">
          <div className="monitor-section">
            <div className="monitor-label"><ShieldCheck size={14}/> Hetzner Control</div>
            <div className="monitor-stats">
              <span>CPU: {hwStats?.cpu_usage || 0}%</span>
              <span>RAM: {hwStats?.memory?.percent || 0}%</span>
            </div>
          </div>
          <div className="monitor-divider" />
          <div className="monitor-section">
            <div className="monitor-label"><Zap size={14} className={status.includes("RunPod") ? "pulse-icon" : ""}/> RunPod Serverless</div>
            <div className="monitor-status">
              <span className={status.includes("Whisper") ? "active-worker" : ""}>Whisper</span>
              <span className={status.includes("Prevođenje") ? "active-worker" : ""}>Qwen 32B</span>
              <span className={status.includes("Sinteza") ? "active-worker" : ""}>Fish TTS</span>
            </div>
          </div>
        </div>

        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="logo-section">
            <h1>Sinhronizuj.me <span className="version-badge">HIBRID V2</span></h1>
            <p className="subtitle">AI Dubbing Studio: Hetzner Control + RunPod GPU</p>
          </div>
        </motion.div>

        {!loading && !videoUrl && (
          <form onSubmit={handleSubmit} className="input-group main-input">
            <div className="input-wrapper">
              <input 
                type="url" placeholder="Zalepite YouTube ili S3 link..." 
                value={url} onChange={(e) => setUrl(e.target.value)}
                disabled={loading} required
              />
              <button type="submit" disabled={loading || !url} className="glow-button">
                <Play size={20} /> Pokreni Sinhronizaciju
              </button>
            </div>
          </form>
        )}

        <AnimatePresence>
          {loading && !videoUrl && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="studio-interface">
              
              <div className="studio-main">
                {/* LEVA STRANA: TRANSKRIPT & PREVOD */}
                <div className="studio-content">
                   <div className="progress-section">
                    <div className="progress-header">
                      <span className="current-step-text">
                        {status.includes("RunPod") && <Zap className="pulse-icon" size={14} style={{display: 'inline', marginRight: '8px'}}/>}
                        {status}
                      </span>
                      <span className="percent-text">{progressData?.percent || 0}%</span>
                    </div>
                    <div className="progress-bar-container">
                      <motion.div className="progress-bar-fill" animate={{ width: `${progressData?.percent || 0}%` }} />
                    </div>
                  </div>

                  {progressData?.segments?.length > 0 ? (
                    <div className="segments-grid" ref={feedRef}>
                      <div className="grid-header">
                        <span>Originalni Transkript (Whisper)</span>
                        <span>AI Prevod (TOON Format)</span>
                      </div>
                      {progressData.segments.map((seg, idx) => (
                        <motion.div 
                          key={idx} 
                          initial={{ opacity: 0, y: 10 }} 
                          animate={{ opacity: 1, y: 0 }}
                          className={`segment-row ${seg.status}`}
                        >
                          <div className="seg-orig">{seg.original}</div>
                          <div className="seg-arrow"><ArrowRight size={14} /></div>
                          <div className="seg-trans">
                            {seg.translated || <span className="waiting-text">Prevođenje...</span>}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <div className="waiting-studio">
                      <Loader2 className="spinner-large" />
                      <p>Pripremam studio za obradu...</p>
                    </div>
                  )}
                </div>

                {/* DESNA STRANA: VIZUELNI KONTEKST & STATUS */}
                <div className="studio-sidebar">
                  <div className="sidebar-card">
                    <div className="card-title"><Eye size={16}/> Visual Context</div>
                    <div className="visual-preview">
                      {visualContextUrl ? (
                         <video src={visualContextUrl} autoPlay loop muted playsInline />
                      ) : (
                        <div className="preview-placeholder">
                          <Eye size={32} className="dim-icon" />
                          <span>Čekam frejmove...</span>
                        </div>
                      )}
                    </div>
                    <p className="context-hint">AI analizira ove frejmove za precizniji prevod.</p>
                  </div>

                  <div className="sidebar-card">
                    <div className="card-title"><Clock size={16}/> Vreme obrade</div>
                    <div className="time-stats">
                       <div className="time-item"><span>Proteklo:</span> <strong>{formatTime(elapsed)}</strong></div>
                       {progressData?.percent > 0 && (
                         <div className="time-item"><span>ETA:</span> <strong>{formatTime(Math.round((elapsed / progressData.percent) * (100 - progressData.percent)))}</strong></div>
                       )}
                    </div>
                  </div>

                  <div className="steps-checklist">
                    {STEPS.map((step, idx) => {
                      const isCompleted = progressData?.completed_steps?.includes(step);
                      const isCurrent = status.includes(step.split(' ')[0]);
                      return (
                        <div key={idx} className={`step-check ${isCompleted ? 'done' : ''} ${isCurrent ? 'active' : ''}`}>
                          {isCompleted ? <CheckCircle2 size={14} /> : <div className="check-dot" />}
                          <span>{step}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

            </motion.div>
          )}

          {videoUrl && (
            <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="final-result">
              <div className="success-banner">
                <ShieldCheck size={24} />
                <span>OBRADA USPEŠNO ZAVRŠENA!</span>
              </div>
              <div className="video-player-wrapper">
                <video src={videoUrl} controls autoPlay />
              </div>
              <div className="result-actions">
                <button onClick={() => window.location.reload()} className="new-task-btn">Sinhronizuj novi video</button>
                <a href={videoUrl} download className="download-btn">Preuzmi Video</a>
              </div>
            </motion.div>
          )}

          {error && (
            <div className="status-card error-card">
              <AlertCircle size={40} />
              <h3>Greška u sistemu</h3>
              <p>{error}</p>
              <button onClick={() => window.location.reload()}>Pokušaj ponovo</button>
            </div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
}

export default App;

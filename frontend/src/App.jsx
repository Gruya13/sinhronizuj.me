import { useState, useEffect, useRef } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle, Clock, Database, Cpu, Terminal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

const API_BASE_URL = "http://localhost:8000";

function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(() => localStorage.getItem('daca_dub_task_id'));
  const [status, setStatus] = useState('');
  const [progressData, setProgressData] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const [startTime, setStartTime] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [hwStats, setHwStats] = useState(null);
  const [selectedGpu, setSelectedGpu] = useState("NVIDIA GeForce RTX 3090");
  const [logs, setLogs] = useState("");
  const [showLogs, setShowLogs] = useState(false);
  const [activeApiUrl, setActiveApiUrl] = useState(API_BASE_URL);
  
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

  // HW Monitoring polling
  useEffect(() => {
    const fetchHw = async () => {
      try {
        const res = await fetch(`${activeApiUrl}/api/v1/hw-stats`);
        const data = await res.json();
        setHwStats(data);
      } catch (err) { /* Silent fail if pod is down */ }
    };
    fetchHw();
    const interval = setInterval(fetchHw, 5000);
    return () => clearInterval(interval);
  }, [activeApiUrl]);

  // Logs polling
  useEffect(() => {
    if (!showLogs) return;
    const fetchLogs = async () => {
      try {
        const res = await fetch(`${activeApiUrl}/api/v1/logs`);
        const data = await res.json();
        setLogs(data.logs || data.error);
      } catch (err) { setLogs("Greška pri čitanju logova..."); }
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [showLogs, activeApiUrl]);

  const handleStopPod = async () => {
    if (!window.confirm("Da li ste sigurni da želite da ugasite RunPod instancu?")) return;
    try {
      await fetch(`${activeApiUrl}/api/v1/runpod/stop`, { method: 'POST' });
      alert("Komanda za gašenje poslata!");
    } catch (err) { alert("Greška pri gašenju."); }
  };

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

  useEffect(() => {
    let interval;
    if (taskId && !videoUrl && !error) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${activeApiUrl}/api/v1/status/${taskId}`);
          const data = await res.json();
          
          if (data.status === 'SUCCESS') {
            setVideoUrl(`${activeApiUrl}${data.video_url}`);
            setStatus('Sve završeno!');
            setProgressData({ percent: 100, completed_steps: STEPS });
            setLoading(false);
            localStorage.removeItem('daca_dub_task_id');
            clearInterval(interval);
          } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
            setError(data.error || 'Greška pri obradi.');
            setLoading(false);
            localStorage.removeItem('daca_dub_task_id');
            clearInterval(interval);
          } else {
            if (data.progress_data) {
              setProgressData(data.progress_data);
              setStatus(data.progress_data.current_step);
            } else {
              setStatus(data.status || 'ČEKANJE...');
            }
          }
        } catch (err) { console.error(err); }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [taskId, videoUrl, error, activeApiUrl]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true); setError(null); setVideoUrl(null); 
    setStartTime(Date.now()); setElapsed(0);
    setStatus('PROVERA INFRASTRUKTURE...');

    try {
      // 1. Pitamo orkestrator za najbolji pod (šaljemo željeni GPU)
      const orchRes = await fetch(`${activeApiUrl}/api/v1/orchestrator/find-best-pod?gpu_type=${encodeURIComponent(selectedGpu)}`);
      const orchData = await orchRes.json();
      
      let targetUrl = activeApiUrl;

      if (orchData.address && orchData.address !== activeApiUrl) {
        console.log("Migracija na slobodan pod:", orchData.address);
        targetUrl = orchData.address;
        setActiveApiUrl(targetUrl);
        setStatus('MIGRACIJA NA SLOBODAN GPU...');
      } else if (orchData.status === "WAKING_UP") {
        setStatus('BUĐENJE INSTANCE (Sačekajte par sekundi)...');
        // Čekamo 5 sekundi da RunPod inicijalizuje mrežu
        await new Promise(r => setTimeout(r, 5000));
      } else if (orchData.status === "DEPLOYING_NEW") {
        setStatus('PODIZANJE NOVE INSTANCE (Skaliranje)...');
        // Ovde bismo mogli uvesti polling dok novi pod ne postane READY
        setError("Svi GPU resursi su zauzeti. Nova instanca se podiže, osvežite za par minuta.");
        setLoading(false);
        return;
      }

      // 2. Šaljemo zadatak na izabrani pod
      setStatus('POKRETANJE...');
      const res = await fetch(`${targetUrl}/api/v1/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setTaskId(data.task_id);
        localStorage.setItem('daca_dub_task_id', data.task_id);
      } else { setError(data.message); setLoading(false); }
    } catch (err) { setError('Greška pri orkestraciji. Proverite RunPod ključeve.'); setLoading(false); }
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

      <div className="glass-container">
        <div className="cloud-monitor">
          <div className="hw-group">
            <div className="gpu-selector-wrapper">
              <select 
                value={selectedGpu} 
                onChange={(e) => setSelectedGpu(e.target.value)}
                className="gpu-select"
              >
                <option value="NVIDIA GeForce RTX 3090">RTX 3090 (24GB)</option>
                <option value="NVIDIA GeForce RTX 4090">RTX 4090 (24GB)</option>
                <option value="NVIDIA RTX A6000">RTX A6000 (48GB)</option>
              </select>
              <button onClick={() => setShowLogs(!showLogs)} className="logs-toggle-btn">
                <Terminal size={14} /> Logovi
              </button>
            </div>
            {hwStats?.gpu?.map((g, i) => (
              <div key={i} className="hw-item">
                <Cpu size={14} />
                <span>GPU {i}: {g.load}% | {g.memory_used}MB / {g.memory_total}MB | {g.temperature}°C</span>
              </div>
            ))}
            {!hwStats && <span className="eta-text">Povezivanje sa RunPodom...</span>}
          </div>
          <button onClick={handleStopPod} className="stop-pod-btn" title="Ugasi RunPod">
            <AlertCircle size={16} /> Stop
          </button>
        </div>

        {showLogs && (
          <div className="log-panel">
            <div className="log-header">
              <span>Sistemski Logovi (Worker)</span>
              <button onClick={() => setShowLogs(false)}>X</button>
            </div>
            <pre className="log-content">{logs}</pre>
          </div>
        )}

        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <h1>Daca Dub AI</h1>
          <p className="subtitle">Transparentna AI Sinhronizacija v1.5</p>
        </motion.div>

        <form onSubmit={handleSubmit} className="input-group">
          <input 
            type="url" placeholder="Zalepite YouTube link..." 
            value={url} onChange={(e) => setUrl(e.target.value)}
            disabled={loading} required
          />
          <button type="submit" disabled={loading || !url}>
            {loading ? <><Loader2 className="spinner" size={20} /> Obrađujem...</> : <><Play size={20} /> Pokreni</>}
          </button>
        </form>

        <AnimatePresence>
          {loading && !videoUrl && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="status-card">
              
              {/* Progress Header */}
              <div className="progress-section">
                <div className="progress-header">
                  <span className="current-step-text">
                    {status.includes("Lektura") && <Loader2 className="spinner" size={14} style={{display: 'inline', marginRight: '8px'}}/>}
                    {status}
                  </span>
                  <span className="percent-text">{progressData?.percent || 0}%</span>
                </div>
                <div className="progress-bar-container">
                  <motion.div className="progress-bar-fill" animate={{ width: `${progressData?.percent || 0}%` }} />
                </div>
                <div style={{display: 'flex', justifyContent: 'space-between', marginTop: '10px'}}>
                  <span className="eta-text"><Clock size={12} style={{verticalAlign: 'middle'}}/> Proteklo: {formatTime(elapsed)}</span>
                  {progressData?.percent > 0 && progressData?.percent < 100 && (
                    <span className="eta-text">ETA: {formatTime(Math.round((elapsed / progressData.percent) * (100 - progressData.percent)))}</span>
                  )}
                </div>
              </div>

              {/* Multi-Instance Status */}
              <div className="instance-dots">
                {Object.entries(progressData?.active_instances || {8080: "idle", 8081: "idle", 8082: "idle"}).map(([port, state]) => (
                  <div key={port} className="instance-dot-wrapper">
                    <div className={`instance-dot ${state === 'active' ? 'active' : ''}`} />
                    <span className="instance-label">GPU:{port.slice(-1)}</span>
                  </div>
                ))}
              </div>

              {/* Live Script Feed */}
              {progressData?.segments?.length > 0 && (
                <div className="segments-feed" ref={feedRef}>
                  {progressData.segments.map((seg, idx) => (
                    <motion.div 
                      key={idx} 
                      initial={{ opacity: 0, x: -10 }} 
                      animate={{ opacity: 1, x: 0 }}
                      className={`segment-card ${seg.status} ${status.includes("Lektura") && seg.status === "pending" ? "active" : ""}`}
                    >
                      {status.includes("Lektura") && seg.status === "pending" && idx === progressData.segments.findIndex(s => s.status === "pending") && (
                        <div className="lektor-scanner" />
                      )}
                      <div className="segment-original">{seg.original}</div>
                      {seg.translated && <div className="segment-translated">{seg.translated}</div>}
                    </motion.div>
                  ))}
                </div>
              )}

              {/* Steps Checklist */}
              <div className="steps-list" style={{marginTop: '20px'}}>
                {STEPS.map((step, idx) => {
                  const isCompleted = progressData?.completed_steps?.includes(step);
                  return (
                    <div key={idx} className={`step-item ${isCompleted ? 'completed' : ''}`}>
                      {isCompleted ? <CheckCircle2 size={14} /> : <div className="step-dot" />}
                      <span>{step}</span>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}

          {videoUrl && (
            <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="video-container">
              <div style={{ padding: '15px', background: 'rgba(16, 185, 129, 0.2)', display: 'flex', justifyContent: 'center', gap: '10px' }}>
                <CheckCircle2 size={20} className="success-text" />
                <span className="success-text" style={{ fontWeight: 700 }}>SINHRONIZACIJA USPEŠNA!</span>
              </div>
              <video src={videoUrl} controls autoPlay />
              <button onClick={() => window.location.reload()} style={{marginTop: '0', borderRadius: '0'}}>Sinhronizuj novi video</button>
            </motion.div>
          )}

          {error && (
            <div className="status-card error-text">
              <AlertCircle size={30} style={{marginBottom: '10px'}}/>
              <p>{error}</p>
              <button onClick={() => window.location.reload()} style={{marginTop: '15px', background: 'var(--error-color)'}}>Pokušaj ponovo</button>
            </div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
}

export default App;


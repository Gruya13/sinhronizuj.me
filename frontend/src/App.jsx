import { useState, useEffect, useRef } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle, Clock, Database, Cpu, Terminal, Eye, Zap, ArrowRight, ShieldCheck, Paperclip, CloudUpload } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";

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
  const [modalStatus, setModalStatus] = useState({ status: 'Učitavam...', active_workers: 0 });
  const [visualContextUrl, setVisualContextUrl] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  const [terminalOpen, setTerminalOpen] = useState(true);
  const [debuggingMode, setDebuggingMode] = useState(() => localStorage.getItem('sinhronizuj_me_debug_mode') === 'true');
  
  useEffect(() => {
    localStorage.setItem('sinhronizuj_me_debug_mode', debuggingMode);
  }, [debuggingMode]);

  const [isContinuing, setIsContinuing] = useState(false);
  
  const feedRef = useRef(null);
  const terminalRef = useRef(null);
  const fileInputRef = useRef(null);
  const consecutiveErrorsRef = useRef(0);

  const resetStudio = () => {
    setTaskId(null);
    setLoading(false);
    setStatus('');
    setProgressData(null);
    setVideoUrl(null);
    setError(null);
    setUploadProgress(0);
    setVisualContextUrl(null);
    localStorage.removeItem('sinhronizuj_me_task_id');
    consecutiveErrorsRef.current = 0;
  };

  const STEPS = [
    "Preuzimanje završeno",
    "Vokal izolovan",
    "Govor prepoznat",
    "Tekst preveden",
    "Glas generisan",
    "Video spojen",
    "Obrada završena"
  ];

  useEffect(() => {
    const fetchHw = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/hw-stats`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        setHwStats(data);
      } catch (err) { /* Silent fail */ }
    };
    const fetchModal = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/modal-status`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        setModalStatus(data);
      } catch (err) { /* Silent fail */ }
    };
    fetchHw();
    fetchModal();
    const intervalHw = setInterval(fetchHw, 5000);
    const intervalMd = setInterval(fetchModal, 15000);
    return () => {
      clearInterval(intervalHw);
      clearInterval(intervalMd);
    };
  }, []);

  useEffect(() => {
    if (taskId) {
        setLoading(true);
        setStatus('UČITAVANJE...');
        setStartTime(Date.now());
    }
  }, []);

  useEffect(() => {
    let timer;
    if (loading && !videoUrl) {
      timer = setInterval(() => {
        setElapsed(Math.floor((Date.now() - (startTime || Date.now())) / 1000));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [loading, videoUrl, startTime]);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [progressData?.segments]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [progressData?.logs]);

  useEffect(() => {
    let interval;
    if (taskId && !videoUrl && !error) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/v1/status/${taskId}`);
          
          // Zadatak 1: Automatski reset ako task ne postoji (404)
          if (res.status === 404) {
            console.warn("Zadatak nije pronađen na serveru (404). Resetujem studio...");
            resetStudio();
            return;
          }

          if (!res.ok) throw new Error("Server error");
          
          const data = await res.json();
          consecutiveErrorsRef.current = 0; // Resetujemo brojač grešaka pri uspešnom pozivu
          
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
        } catch (err) { 
          consecutiveErrorsRef.current += 1;
          console.error(`Greška pri pollingu (${consecutiveErrorsRef.current}/5):`, err);
          
          // Zadatak 1: Reset nakon 5 uzastopnih grešaka (npr. server ugašen ili Redis očišćen)
          if (consecutiveErrorsRef.current >= 5) {
            setError("Veza sa serverom je izgubljena. Zadatak je verovatno prekinut.");
            setTimeout(resetStudio, 3000); // Resetuj nakon 3 sekunde da korisnik vidi grešku
          }
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [taskId, videoUrl, error]);

  const handleSubmit = async (e, customUrl = null) => {
    if (e) e.preventDefault();
    const targetUrl = customUrl || url;
    if (!targetUrl) return;

    setLoading(true); setError(null); setVideoUrl(null); 
    setStartTime(Date.now()); setElapsed(0);
    setStatus('POVEZIVANJE SA KONTROLNOM TABLOM...');

    try {
      console.log(`[SUBMIT] Slanje zadatka. Debugging: ${debuggingMode}, URL: ${targetUrl}`);
      const res = await fetch(`${API_BASE_URL}/api/v1/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl, debugging_mode: debuggingMode })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setTaskId(data.task_id);
        localStorage.setItem('sinhronizuj_me_task_id', data.task_id);
      } else { setError(data.message); setLoading(false); }
    } catch (err) { setError('Greška pri slanju zadatka. Proverite backend.'); setLoading(false); }
  };

  const handleContinue = async () => {
    if (!taskId) return;
    setIsContinuing(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/continue/${taskId}`, { method: 'POST' });
      if (!res.ok) throw new Error();
      // Polling će preuzeti promenu statusa
    } catch (err) {
      console.error("Greška pri slanju signala za nastavak");
    } finally {
      setTimeout(() => setIsContinuing(false), 2000);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setLoading(true);
    setStatus(`PRIPREMA UPLOADA: ${file.name}...`);
    setError(null);
    setUploadProgress(1);

    try {
      // 1. Dobavi Presigned URL koristeći nativni fetch
      const urlRes = await fetch(`${API_BASE_URL}/api/v1/storage/upload_url?filename=${encodeURIComponent(file.name)}&content_type=${encodeURIComponent(file.type)}`);
      const { upload_url, s3_url } = await urlRes.json();

      // 2. Upload na MinIO koristeći XMLHttpRequest (za progress tracking)
      setStatus(`UPLOADOVANJE NA S3 STORAGE...`);
      
      const xhr = new XMLHttpRequest();
      
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentCompleted = Math.round((event.loaded * 100) / event.total);
          setUploadProgress(percentCompleted);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploadProgress(0);
          handleSubmit(null, s3_url);
        } else {
          setError(`Greška pri uploadu: ${xhr.statusText}`);
          setLoading(false);
          setUploadProgress(0);
        }
      };

      xhr.onerror = () => {
        setError("Greška pri mreži tokom uploada.");
        setLoading(false);
        setUploadProgress(0);
      };

      xhr.open('PUT', upload_url);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);

    } catch (err) {
      setError(`Greška: ${err.message}`);
      setLoading(false);
      setUploadProgress(0);
    }
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
            <div className="monitor-label">
              <Zap size={14} className={modalStatus.status === "Spreman" ? "pulse-icon" : ""}/> 
              Modal Serverless 
              <span className={`status-badge ${modalStatus.status === "Spreman" ? 'active' : 'asleep'}`}>
                {modalStatus.status === "Spreman" ? `AKTIVAN (${modalStatus.active_workers})` : "SPAVA"}
              </span>
            </div>
            <div className="monitor-status">
              <span className={status.includes("Whisper") ? "active-worker" : ""}>Whisper</span>
              <span className={status.includes("Prevođenje") ? "active-worker" : ""}>Qwen 32B</span>
              <span className={status.includes("Sinteza") ? "active-worker" : ""}>Fish TTS</span>
            </div>
          </div>
        </div>

        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="logo-section">
            <h1>Sinhronizuj.me <span className="version-badge">MODAL V1</span></h1>
            <p className="subtitle">AI Dubbing Studio: Hetzner Control + Modal Serverless</p>
          </div>
        </motion.div>

        {!loading && !videoUrl && (
          <div className="input-area">
             <form onSubmit={handleSubmit} className="input-group main-input">
                <div className="input-wrapper">
                <input 
                    type="url" placeholder="Zalepite YouTube ili S3 link..." 
                    value={url} onChange={(e) => setUrl(e.target.value)}
                    disabled={loading} required
                />
                <button 
                    type="button" 
                    className="icon-btn" 
                    onClick={() => fileInputRef.current.click()}
                    title="Uploaduj lokalni fajl"
                >
                    <Paperclip size={20} />
                </button>
                <button type="submit" disabled={loading || !url} className="glow-button">
                    <Play size={20} /> Sinhronizuj
                </button>
                </div>
            </form>
            <input 
                type="file" 
                ref={fileInputRef} 
                style={{ display: 'none' }} 
                accept="video/*" 
                onChange={handleFileUpload}
            />
            <p className="upload-hint">Podržani formati: MP4, MKV, AVI. Max 500MB.</p>
            
            <div className="debug-toggle-container">
              <label className="debug-label">
                <Terminal size={14} /> Debugging Mode (Step-by-step)
              </label>
              <label className="switch">
                <input 
                  type="checkbox" 
                  checked={debuggingMode} 
                  onChange={(e) => setDebuggingMode(e.target.checked)} 
                />
                <span className="slider"></span>
              </label>
            </div>
          </div>
        )}

        <AnimatePresence>
          {loading && !videoUrl && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="studio-interface">
              
              <div className="studio-main">
                <div className="studio-content">
                   <div className="progress-section">
                    <div className="progress-header">
                      <span className="current-step-text">
                        {uploadProgress > 0 ? (
                           <><CloudUpload size={14} className="pulse-icon" style={{display: 'inline', marginRight: '8px'}}/> Upload na S3: {uploadProgress}%</>
                        ) : (
                          <>
                             {status.includes("Modal") && <Zap className="pulse-icon" size={14} style={{display: 'inline', marginRight: '8px'}}/>}
                            {status}
                          </>
                        )}
                      </span>
                      <div className="progress-actions">
                        <span className="percent-text">{uploadProgress > 0 ? uploadProgress : (progressData?.percent || 0)}%</span>
                        <button 
                          className="cancel-task-btn" 
                          onClick={resetStudio}
                          title="Prekini i resetuj studio"
                        >
                          ✕
                        </button>
                      </div>
                    </div>

                    {progressData?.detail?.includes("Cold Start") && (
                      <div className="cold-start-indicator">
                        <div className="cold-start-header">
                          <div className="flex items-center gap-2">
                             <Zap size={14} className="pulse-icon" />
                             <span>MODAL_COLD_START: Podižem radno okruženje...</span>
                          </div>
                          <span className="opacity-60">Očekivano ~20s</span>
                        </div>
                        <div className="cold-start-bar-container">
                          <div className="cold-start-bar-fill"></div>
                        </div>
                      </div>
                    )}

                    <div className="progress-bar-container">
                      <motion.div 
                        className={`progress-bar-fill ${uploadProgress > 0 ? 'uploading' : ''}`} 
                        animate={{ width: `${uploadProgress > 0 ? uploadProgress : (progressData?.percent || 0)}%` }} 
                      />
                    </div>

                    {progressData?.detail && (
                      <div className="sub-status-detail">
                        {progressData.detail.includes("Cold Start") ? <Loader2 size={14} className="spinner-icon" /> : <Clock size={14} />}
                        <span>{progressData.detail}</span>
                      </div>
                    )}
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
                    {progressData?.waiting_for_user && (
                      <div className="continue-btn-container">
                        <button 
                          className="continue-btn" 
                          onClick={handleContinue}
                          disabled={isContinuing}
                        >
                          {isContinuing ? <Loader2 size={20} className="spinner-icon" /> : <Play size={20} />}
                          Nastavi na sledeći korak
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                    <div className="waiting-studio">
                      <Loader2 className="spinner-large" />
                      <p>{uploadProgress > 0 ? 'Slanje fajla u oblak...' : 'Pripremam studio za obradu...'}</p>
                    </div>
                  )}

                  {/* Terminal Log Feed */}
                  <div className="terminal-section">
                    <div className="terminal-header" onClick={() => setTerminalOpen(!terminalOpen)}>
                      <div className="flex items-center gap-2">
                        <Terminal size={14} />
                        <span>WORKER_LOG_FEED</span>
                      </div>
                      <span>{terminalOpen ? '−' : '+'}</span>
                    </div>
                    {terminalOpen && (
                      <div className="terminal-body" ref={terminalRef}>
                        {progressData?.logs?.length > 0 ? (
                          progressData.logs.map((log, i) => {
                            const [ts, ...msgParts] = log.split(' ');
                            const msg = msgParts.join(' ');
                            return (
                              <div key={i} className="log-entry">
                                <span className="log-ts">{ts}</span>
                                <span className="log-msg">{msg}</span>
                              </div>
                            );
                          })
                        ) : (
                          <div className="log-entry opacity-40">Čekam prve mikro-statuse...</div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

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

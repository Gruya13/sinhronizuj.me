import { useState, useEffect, useRef } from 'react';
import { Play, Loader2, CheckCircle2, AlertCircle, Clock, Database, Cpu, Terminal, Eye, Zap, ArrowRight, ShieldCheck, Paperclip, CloudUpload, RefreshCw } from 'lucide-react';
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
  const [videoError, setVideoError] = useState(null);
  const [startTime, setStartTime] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [hwStats, setHwStats] = useState(null);
  const [modalStatus, setModalStatus] = useState({ status: 'Učitavam...', active_workers: 0 });
  const [visualContextUrl, setVisualContextUrl] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  const [previewFile, setPreviewFile] = useState(null);
  const [uploadState, setUploadState] = useState('idle'); // idle, uploading, completed, error

  const [terminalOpen, setTerminalOpen] = useState(true);
  const [debuggingMode, setDebuggingMode] = useState(() => {
    const saved = localStorage.getItem('sinhronizuj_me_debug_mode');
    return saved === null ? true : saved === 'true';
  });

  // Interaktivni Studio v2 state-ovi
  const [editedSegments, setEditedSegments] = useState([]);
  const [bgVolume, setBgVolume] = useState(-5);
  const [dubVolume, setDubVolume] = useState(0);
  const [selectedVoice, setSelectedVoice] = useState("clone");
  
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
    setVideoError(null);
    setUploadProgress(0);
    setVisualContextUrl(null);
    setPreviewFile(null);
    setUploadState('idle');
    localStorage.removeItem('sinhronizuj_me_task_id');
    consecutiveErrorsRef.current = 0;
    setEditedSegments([]);
  };

  const STEPS = [
    "Preuzimanje završeno",
    "Vokal izolovan",
    "Govor prepoznat",
    "Tekst preveden",
    "Lektura završena",
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
    const isStepAwaiting = progressData?.waiting_for_user && 
      (progressData?.waiting_step === "Prevođenje" || progressData?.waiting_step === "TTS Sinteza");
    if (isStepAwaiting) {
      if (progressData.segments && editedSegments.length === 0) {
        console.log("[STUDIO] Ucitavam segmente za izmenu:", progressData.segments.length);
        setEditedSegments(progressData.segments.map(s => ({
          id: s.id,
          original: s.original,
          translated: s.translated || '',
          status: s.status
        })));
      }
    } else {
      if (editedSegments.length > 0) {
        setEditedSegments([]);
      }
    }
  }, [progressData?.waiting_for_user, progressData?.waiting_step, progressData?.segments]);

  // Isključujemo auto-scroll za segmente da bi korisnik mogao na miru da čita
  // useEffect(() => {
  //   if (feedRef.current) {
  //     feedRef.current.scrollTop = feedRef.current.scrollHeight;
  //   }
  // }, [progressData?.segments]);

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
            // Ne čistimo progressData ovde
            setLoading(false);
            localStorage.removeItem('sinhronizuj_me_task_id');
            clearInterval(interval);
          } else {
            if (data.progress_data) {
              console.log(`[POLL] Status: ${data.status}, Segments: ${data.progress_data.segments?.length || 0}`, data.progress_data);
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

  const handleLoadUrl = (e) => {
    if (e) e.preventDefault();
    if (!url) return;

    setError(null);

    // Provera da li je YouTube link
    const ytMatch = url.match(/(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?([^&\s]+)/);
    if (ytMatch) {
      const videoId = ytMatch[1];
      const embedUrl = `https://www.youtube.com/embed/${videoId}`;
      setPreviewFile({
        name: "YouTube Video",
        type: "youtube",
        url: embedUrl,
        rawUrl: url
      });
      setUploadState("completed");
      return;
    }

    // Provera da li je direktan video URL
    if (url.match(/\.(mp4|webm|ogg|mov|mkv)(?:\?|$)/i) || url.startsWith("s3://")) {
      setPreviewFile({
        name: "Eksterni Video",
        type: "direct_url",
        url: url,
        rawUrl: url
      });
      setUploadState("completed");
      return;
    }

    // Ako nije prepoznat specifičan format, i dalje dozvoljavamo preview/sinhronizaciju
    setPreviewFile({
      name: "Eksterni Resurs",
      type: "unknown",
      url: url,
      rawUrl: url
    });
    setUploadState("completed");
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!previewFile) return;

    const targetUrl = previewFile.type === "local" ? previewFile.s3Url : previewFile.rawUrl;
    if (!targetUrl) return;

    setLoading(true); setError(null); setVideoUrl(null); setVideoError(null); setUploadProgress(0);
    setStartTime(Date.now()); setElapsed(0);
    setStatus('POVEZIVANJE SA KONTROLNOM TABLOM...');

    try {
      console.log(`[SUBMIT] Slanje zadatka. Debugging: ${debuggingMode}, URL: ${targetUrl}`);
      const res = await fetch(`${API_BASE_URL}/api/v1/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl, debug: debuggingMode })
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
      // 1. Ako je korisnik vrsio izmene na segmentima, posalji ih backendu
      if (editedSegments.length > 0) {
        console.log("[STUDIO] Snimam izmenjene segmente...", editedSegments);
        await fetch(`${API_BASE_URL}/api/v1/edit-segments/${taskId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ segments: editedSegments })
        });
      }
      
      // 2. Posalji podesavanja miksera
      console.log("[STUDIO] Snimam podesavanja miksera...", { background_volume: bgVolume, dubbed_volume: dubVolume });
      await fetch(`${API_BASE_URL}/api/v1/mixer-settings/${taskId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ background_volume: bgVolume, dubbed_volume: dubVolume })
      });

      // 2.5 Posalji podesavanja glasa ako smo u fazi Prevodjenje ili TTS Sinteza
      if (progressData?.waiting_step === "Prevođenje" || progressData?.waiting_step === "TTS Sinteza") {
        console.log("[STUDIO] Snimam podesavanja glasa...", { voice: selectedVoice });
        await fetch(`${API_BASE_URL}/api/v1/voice-settings/${taskId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ voice: selectedVoice })
        });
      }
 
      // 3. Posalji signal za nastavak
      const res = await fetch(`${API_BASE_URL}/api/v1/continue/${taskId}`, { method: 'POST' });
      if (!res.ok) throw new Error();
      
    } catch (err) {
      console.error("Greska pri slanju podataka i nastavku:", err);
    } finally {
      setTimeout(() => setIsContinuing(false), 2000);
    }
  };

  const handleRegenerateTTS = async () => {
    if (!taskId) return;
    setIsContinuing(true);
    try {
      // 1. Ako je korisnik vrsio izmene na segmentima, posalji ih backendu
      if (editedSegments.length > 0) {
        console.log("[STUDIO] Snimam izmenjene segmente za regeneraciju...", editedSegments);
        await fetch(`${API_BASE_URL}/api/v1/edit-segments/${taskId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ segments: editedSegments })
        });
      }
      
      // 2. Posalji podesavanja glasa
      console.log("[STUDIO] Snimam podesavanja glasa za regeneraciju...", { voice: selectedVoice });
      await fetch(`${API_BASE_URL}/api/v1/voice-settings/${taskId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice: selectedVoice })
      });

      // 3. Posalji signal za regeneraciju
      console.log("[STUDIO] Slanje zahteva za regeneraciju TTS...");
      const res = await fetch(`${API_BASE_URL}/api/v1/regenerate-tts/${taskId}`, { method: 'POST' });
      if (!res.ok) throw new Error();
      
      // Ocisti lokalne segmente za izmenu kako bi se ponovo ucitali sa servera kada se zavrsi sinteza
      setEditedSegments([]);
      
    } catch (err) {
      console.error("Greska pri regeneraciji TTS-a:", err);
    } finally {
      setTimeout(() => setIsContinuing(false), 2000);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const objectUrl = URL.createObjectURL(file);
    setPreviewFile({
      name: file.name,
      size: file.size,
      type: "local",
      url: objectUrl,
      s3Url: null
    });
    setUploadState("uploading");
    setUploadProgress(1);
    setError(null);

    try {
      // 1. Dobavi Presigned URL koristeći nativni fetch
      const urlRes = await fetch(`${API_BASE_URL}/api/v1/storage/upload_url?filename=${encodeURIComponent(file.name)}&content_type=${encodeURIComponent(file.type)}`);
      if (!urlRes.ok) throw new Error("Neuspešno dobavljanje upload URL-a.");
      const { upload_url, s3_url } = await urlRes.json();

      // 2. Upload na MinIO koristeći XMLHttpRequest (za progress tracking)
      const xhr = new XMLHttpRequest();
      
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentCompleted = Math.round((event.loaded * 100) / event.total);
          setUploadProgress(percentCompleted);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploadProgress(100);
          setUploadState("completed");
          setPreviewFile(prev => ({
            ...prev,
            s3Url: s3_url
          }));
        } else {
          setError(`Greška pri uploadu: ${xhr.statusText}`);
          setUploadState("error");
        }
      };

      xhr.onerror = () => {
        setError("Greška pri mreži tokom uploada.");
        setUploadState("error");
      };

      xhr.open('PUT', upload_url);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);

    } catch (err) {
      setError(`Greška: ${err.message}`);
      setUploadState("error");
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

        {!loading && !videoUrl && !previewFile && (
          <div className="input-area">
             <form onSubmit={handleLoadUrl} className="input-group main-input">
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
                    <ArrowRight size={20} /> Učitaj video
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

        {!loading && !videoUrl && previewFile && (
          <div className="preview-pane-container">
            {/* Leva strana: Video Player */}
            <div className="preview-video-wrapper">
              {previewFile.type === "youtube" ? (
                <iframe 
                  src={previewFile.url} 
                  className="preview-media" 
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                  allowFullScreen 
                  title="YouTube Preview"
                />
              ) : previewFile.type === "local" || previewFile.type === "direct_url" ? (
                <video 
                  src={previewFile.url} 
                  controls 
                  className="preview-media" 
                />
              ) : (
                <div className="preview-placeholder">
                  <Eye size={48} className="dim-icon text-slate-600" />
                  <span>Preview nije dostupan za ovaj format</span>
                </div>
              )}
            </div>

            {/* Desna strana: Detalji i Akcije */}
            <div className="preview-details-panel">
              <div>
                <h3 className="preview-title">Priprema videa</h3>
                <p className="text-sm text-slate-400 mb-6" style={{ marginBottom: '24px' }}>Pregledajte video pre nego što započnete inteligentnu sinhronizaciju.</p>
                
                <div className="file-info-list">
                  <div className="file-info-item">
                    <span>Naziv:</span>
                    <span>{previewFile.name}</span>
                  </div>
                  {previewFile.size && (
                    <div className="file-info-item">
                      <span>Veličina:</span>
                      <span>{(previewFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                    </div>
                  )}
                  <div className="file-info-item">
                    <span>Tip izvora:</span>
                    <span className="capitalize" style={{ textTransform: 'capitalize' }}>
                      {previewFile.type === "local" ? "Lokalni fajl" : previewFile.type === "youtube" ? "YouTube video" : "Eksterni URL"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Status uploada */}
              {previewFile.type === "local" && (
                <div className="upload-status-box">
                  <div className="status-text-row">
                    <span>Status prenosa:</span>
                    {uploadState === "uploading" ? (
                      <span className="status-uploading">
                        <Loader2 size={14} className="spinner-icon pulse-icon" style={{ display: 'inline', marginRight: '6px' }} /> Prenos na storage...
                      </span>
                    ) : uploadState === "completed" ? (
                      <span className="status-completed">
                        <CheckCircle2 size={14} style={{ display: 'inline', marginRight: '6px' }} /> Spreman na storage-u
                      </span>
                    ) : uploadState === "error" ? (
                      <span className="status-error">
                        <AlertCircle size={14} style={{ display: 'inline', marginRight: '6px' }} /> Greška pri prenosu
                      </span>
                    ) : (
                      <span>U mirovanju</span>
                    )}
                  </div>
                  
                  {uploadState === "uploading" && (
                    <div className="progress-bar-container" style={{ marginTop: '8px' }}>
                      <div 
                        className="progress-bar-fill uploading" 
                        style={{ width: `${uploadProgress}%` }} 
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Studio Mod Toggle */}
              <div className="debug-toggle-container" style={{ margin: '15px 0 20px 0', justifyContent: 'flex-start', width: '100%', padding: '10px 14px' }}>
                <label className="debug-label" style={{ cursor: 'pointer' }}>
                  <Terminal size={14} style={{ marginRight: '6px' }} /> Korak-po-korak pregled (Studio mod)
                </label>
                <label className="switch" style={{ marginLeft: 'auto' }}>
                  <input 
                    type="checkbox" 
                    checked={debuggingMode} 
                    onChange={(e) => setDebuggingMode(e.target.checked)} 
                  />
                  <span className="slider"></span>
                </label>
              </div>

              {/* Akcije */}
              <div className="preview-actions-row">
                <button onClick={resetStudio} className="back-btn">
                  Nazad
                </button>
                <button 
                  onClick={handleSubmit} 
                  disabled={previewFile.type === "local" && uploadState !== "completed"} 
                  className="glow-button"
                >
                  <Play size={18} /> Sinhronizuj
                </button>
              </div>
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

                    {progressData?.waiting_for_user && (
                      <motion.div 
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="continue-btn-container"
                        style={{ flexDirection: 'column', alignItems: 'center', gap: '16px' }}
                      >
                        {progressData?.waiting_step === "TTS Sinteza" && (
                          <div className="mixer-panel">
                            <h4 className="mixer-title">🎛️ Audio Mikser za Finalni Mix</h4>
                            <div className="mixer-controls">
                              <div className="mixer-control">
                                <label>
                                  <span>🎵 Jačina originalne pozadine:</span>
                                  <strong>{bgVolume > 0 ? `+${bgVolume}` : bgVolume} dB</strong>
                                </label>
                                <input 
                                  type="range" 
                                  min="-30" 
                                  max="10" 
                                  step="1"
                                  value={bgVolume} 
                                  onChange={(e) => setBgVolume(parseInt(e.target.value))} 
                                />
                              </div>
                              <div className="mixer-control">
                                <label>
                                  <span>🎙️ Jačina novog srpskog AI glasa:</span>
                                  <strong>{dubVolume > 0 ? `+${dubVolume}` : dubVolume} dB</strong>
                                </label>
                                <input 
                                  type="range" 
                                  min="-15" 
                                  max="15" 
                                  step="1"
                                  value={dubVolume} 
                                  onChange={(e) => setDubVolume(parseInt(e.target.value))} 
                                />
                              </div>
                            </div>

                            {progressData?.dubbed_audio_url && (
                              <div className="audio-preview-section" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '15px', marginTop: '10px' }}>
                                <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span>🎧</span> Preslušajte generisani srpski glas (pre spajanja sa videom):
                                </p>
                                <audio 
                                  src={`${API_BASE_URL}${progressData.dubbed_audio_url}`} 
                                  controls 
                                  style={{ width: '100%', height: '40px', borderRadius: '8px' }}
                                />
                              </div>
                            )}
                          </div>
                        )}

                        {(progressData?.waiting_step === "Prevođenje" || progressData?.waiting_step === "TTS Sinteza") && (
                          <div className="voice-selection-box" style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.05)', marginBottom: '15px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                              <span style={{ fontSize: '1.2rem' }}>🎙️</span>
                              <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: '#f8fafc', margin: 0 }}>Glasovna sinteza i kloniranje</h3>
                            </div>
                            <p style={{ fontSize: '0.82rem', color: '#94a3b8', margin: 0, lineHeight: '1.4' }}>
                              Sinteza govora se vrši korišćenjem proverenog srpskog modela (Marko Piper) uz napredno kloniranje boje glasa originalnog govornika iz videa.
                            </p>
                          </div>
                        )}

                        <div style={{ display: 'flex', flexDirection: 'column', width: '100%', gap: '10px', alignItems: 'center' }}>
                          <button 
                            className="continue-btn" 
                            onClick={handleContinue}
                            disabled={isContinuing}
                            style={{ width: '100%', maxWidth: '350px', justifyContent: 'center' }}
                          >
                            {isContinuing ? <Loader2 size={20} className="spinner-icon" /> : <Play size={20} />}
                            {progressData?.waiting_step === "Prevođenje" 
                              ? "Potvrdi prevod i pokreni sintezu" 
                              : progressData?.waiting_step === "TTS Sinteza"
                                ? "Potvrdi miks i pokreni spajanje videa"
                                : "Nastavi obradu"}
                          </button>

                          {progressData?.waiting_step === "TTS Sinteza" && (
                            <button 
                              className="regenerate-btn" 
                              onClick={handleRegenerateTTS}
                              disabled={isContinuing}
                              style={{ width: '100%', maxWidth: '350px', justifyContent: 'center' }}
                            >
                              {isContinuing ? <Loader2 size={20} className="spinner-icon" /> : <RefreshCw size={16} />}
                              <span>Ponovo generiši glas sa novim podešavanjima/tekstom</span>
                            </button>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </div>

                  {progressData?.id || uploadProgress > 0 ? (
                    <>
                      {progressData?.segments?.length > 0 && (
                        <div className="segments-grid" ref={feedRef}>
                          <div className="grid-header">
                            <span>Originalni Transkript (Whisper)</span>
                            <span>AI Prevod (TOON Format)</span>
                          </div>
                          {progressData.segments.map((seg, idx) => {
                            const isReview = progressData?.waiting_for_user && (progressData?.waiting_step === "Prevođenje" || progressData?.waiting_step === "TTS Sinteza") && editedSegments.length > 0;
                            return (
                              <motion.div 
                                key={idx} 
                                initial={{ opacity: 0, y: 10 }} 
                                animate={{ opacity: 1, y: 0 }}
                                className={`segment-row ${isReview ? 'waiting-review' : seg.status}`}
                              >
                                <div className="seg-orig">{seg.original}</div>
                                <div className="seg-arrow"><ArrowRight size={14} /></div>
                                <div className="seg-trans">
                                  {isReview ? (
                                    <textarea
                                      value={editedSegments[idx]?.translated ?? ''}
                                      onChange={(e) => {
                                        const newVal = e.target.value;
                                        setEditedSegments(prev => prev.map((item, i) => i === idx ? { ...item, translated: newVal } : item));
                                      }}
                                      className="edit-segment-textarea"
                                      placeholder="Unesite prevod..."
                                    />
                                  ) : (
                                    seg.translated || <span className="waiting-text">Prevođenje...</span>
                                  )}
                                </div>
                              </motion.div>
                            );
                          })}
                        </div>
                      )}
                    </>
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
                <video 
                  src={videoUrl} 
                  controls 
                  autoPlay 
                  muted 
                  onError={(e) => {
                    const mediaError = e.target.error;
                    console.error("Video error details:", mediaError);
                    let errMsg = "Nepoznata greška pri učitavanju videa.";
                    if (mediaError) {
                      switch (mediaError.code) {
                        case 1: errMsg = "Učitavanje videa je prekinuto (aborted)."; break;
                        case 2: errMsg = "Mrežna greška pri preuzimanju videa."; break;
                        case 3: errMsg = "Dekodiranje videa nije uspelo (moguće neispravan kodek)."; break;
                        case 4: errMsg = "Format videa ili kodek nisu podržani u vašem pretraživaču."; break;
                      }
                      if (mediaError.message) {
                        errMsg += ` Detalji: ${mediaError.message}`;
                      }
                    }
                    setVideoError(errMsg);
                  }}
                />
              </div>
              {videoError && (
                <div style={{ color: "#ff4d4f", marginTop: "12px", textAlign: "center", fontSize: "14px", fontWeight: "600", background: "rgba(255,77,79,0.1)", padding: "10px", borderRadius: "8px", border: "1px solid rgba(255,77,79,0.2)" }}>
                  ⚠️ Greška plejera: {videoError}
                </div>
              )}
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

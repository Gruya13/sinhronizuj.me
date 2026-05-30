import { useState, useEffect, useRef } from 'react';
import { 
  Play, Pause, Loader2, CheckCircle2, AlertCircle, Clock, 
  Database, Cpu, Terminal, Eye, Zap, ArrowRight, ShieldCheck, 
  Paperclip, CloudUpload, RefreshCw, Trash2, Volume2, Save, Video, Film, Music, Mic
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";

function App() {
  // Glavni tokovi stanja
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
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadState, setUploadState] = useState('idle'); // idle, uploading, completed, error
  const [previewFile, setPreviewFile] = useState(null);

  // Studio v2 specifična stanja
  const [project, setProject] = useState(null);
  const [selectedSegmentId, setSelectedSegmentId] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [bgVolume, setBgVolume] = useState(-5);
  const [dubVolume, setDubVolume] = useState(0);
  const [selectedVoice, setSelectedVoice] = useState("clone");
  const [probniAudios, setProbniAudios] = useState({});
  const [loadingSegmentTTS, setLoadingSegmentTTS] = useState({});
  const [savingProject, setSavingProject] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderTaskId, setRenderTaskId] = useState(null);
  const [costs, setCosts] = useState(null);
  const [activeAudioSource, setActiveAudioSource] = useState("original"); // original or dubbed
  const [generatingAllTTS, setGeneratingAllTTS] = useState(false);

  const videoRef = useRef(null);
  const timelineRef = useRef(null);
  const fileInputRef = useRef(null);
  const consecutiveErrorsRef = useRef(0);
  const playheadIntervalRef = useRef(null);
  const dubbedAudioRef = useRef(null);

  // Monitor resursa
  useEffect(() => {
    const fetchHw = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/hw-stats`);
        if (res.ok) {
          const data = await res.json();
          setHwStats(data);
        }
      } catch (err) { /* Silent fail */ }
    };
    const fetchModal = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/modal-status`);
        if (res.ok) {
          const data = await res.json();
          setModalStatus(data);
        }
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

  // Provera starog Task ID-ja kod učitavanja
  useEffect(() => {
    if (taskId) {
      setLoading(true);
      setStatus('UČITAVANJE PROJEKTA...');
      setStartTime(Date.now());
    }
  }, [taskId]);

  // Tajmer za trajanje obrade
  useEffect(() => {
    let timer;
    if (loading && !videoUrl) {
      timer = setInterval(() => {
        setElapsed(Math.floor((Date.now() - (startTime || Date.now())) / 1000));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [loading, videoUrl, startTime]);

  // Polling za Fazu 1 (Analiza) ili Fazu 2 (Render)
  useEffect(() => {
    let interval;
    const currentTask = renderTaskId || taskId;
    if (currentTask && !videoUrl && !error) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/v1/status/${currentTask}`);
          if (res.status === 404) {
            console.warn("Zadatak nije pronađen (404).");
            resetStudio();
            return;
          }
          if (!res.ok) throw new Error("Server error");
          
          const data = await res.json();
          consecutiveErrorsRef.current = 0;
          
          if (data.status === 'SUCCESS') {
            if (renderTaskId) {
              // Faza 2 završena
              setVideoUrl(`${API_BASE_URL}${data.video_url}`);
              setRendering(false);
              setLoading(false);
              if (data.costs) setCosts(data.costs);
              localStorage.removeItem('sinhronizuj_me_task_id');
              setRenderTaskId(null);
              clearInterval(interval);
            } else {
              // Faza 1 završena, prelazimo u Studio mod
              setProgressData(null);
              setLoading(false);
              loadProjectData(taskId);
              clearInterval(interval);
            }
          } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
            setError(data.error || 'Greška pri obradi.');
            setLoading(false);
            setRendering(false);
            localStorage.removeItem('sinhronizuj_me_task_id');
            setRenderTaskId(null);
            clearInterval(interval);
          } else {
            // PROGRESS status
            if (data.progress_data) {
              setProgressData(data.progress_data);
              setStatus(data.progress_data.current_step);
            } else {
              setStatus(data.status || 'OBRADA...');
            }
            if (data.costs) setCosts(data.costs);
          }
        } catch (err) {
          consecutiveErrorsRef.current += 1;
          if (consecutiveErrorsRef.current >= 5) {
            setError("Veza sa serverom je izgubljena. Zadatak je verovatno prekinut.");
            setTimeout(resetStudio, 3000);
          }
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [taskId, renderTaskId, videoUrl, error]);

  // Učitavanje podataka o projektu iz Redisa
  const loadProjectData = async (projId) => {
    try {
      setStatus('Učitavam radni prostor...');
      const res = await fetch(`${API_BASE_URL}/api/v1/project/${projId}`);
      if (!res.ok) throw new Error("Neuspešno učitavanje projekta.");
      const data = await res.json();
      setProject(data);
      if (data.costs) setCosts(data.costs);
      
      // Keširamo probne audije ako ih ima iz baze
      const audios = {};
      data.segments.forEach(s => {
        if (s.tts_path) {
          const filename = s.tts_path.split('/').pop();
          audios[s.id] = `${API_BASE_URL}/videos/${filename}`;
        }
      });
      setProbniAudios(audios);
    } catch (err) {
      setError("Greška pri učitavanju projekta: " + err.message);
    }
  };

  const handleFlushRedis = async () => {
    if (!window.confirm("Da li ste sigurni da želite da očistite kompletnu Redis bazu? Ovo će prekinuti sve aktivne zadatke.")) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/redis/flush`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        alert(data.message || "Redis baza je uspešno očišćena.");
        resetStudio();
      } else {
        alert("Greška: " + (data.detail || "Neuspešno čišćenje."));
      }
    } catch (err) {
      alert("Mrežna greška: " + err.message);
    }
  };

  const resetStudio = () => {
    setTaskId(null);
    setRenderTaskId(null);
    setLoading(false);
    setRendering(false);
    setStatus('');
    setProgressData(null);
    setVideoUrl(null);
    setError(null);
    setUploadProgress(0);
    setPreviewFile(null);
    setUploadState('idle');
    setProject(null);
    setProbniAudios({});
    setLoadingSegmentTTS({});
    localStorage.removeItem('sinhronizuj_me_task_id');
    consecutiveErrorsRef.current = 0;
    setCosts(null);
  };

  // Učitavanje spoljnog URL-a
  const handleLoadUrl = (e) => {
    if (e) e.preventDefault();
    if (!url) return;
    setError(null);

    const ytMatch = url.match(/(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?([^&\s]+)/);
    if (ytMatch) {
      const videoId = ytMatch[1];
      setPreviewFile({
        name: "YouTube Video",
        type: "youtube",
        url: `https://www.youtube.com/embed/${videoId}`,
        rawUrl: url
      });
      setUploadState("completed");
      return;
    }

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

    setPreviewFile({
      name: "Eksterni Resurs",
      type: "unknown",
      url: url,
      rawUrl: url
    });
    setUploadState("completed");
  };

  // Slanje videa na Fazu 1 (Analizu)
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!previewFile) return;

    const targetUrl = previewFile.type === "local" ? previewFile.s3Url : previewFile.rawUrl;
    if (!targetUrl) return;

    setLoading(true);
    setError(null);
    setVideoUrl(null);
    setUploadProgress(0);
    setStartTime(Date.now());
    setElapsed(0);
    setStatus('POKRETANJE ANALIZE VIDEA...');

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/process-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl, debug: false })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setTaskId(data.task_id);
        localStorage.setItem('sinhronizuj_me_task_id', data.task_id);
      } else {
        setError(data.message);
        setLoading(false);
      }
    } catch (err) {
      setError('Mrežna greška pri pokretanju analize.');
      setLoading(false);
    }
  };

  // Upload lokalnog fajla
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
      const urlRes = await fetch(`${API_BASE_URL}/api/v1/storage/upload_url?filename=${encodeURIComponent(file.name)}&content_type=${encodeURIComponent(file.type)}`);
      if (!urlRes.ok) throw new Error("Neuspešno dobavljanje upload URL-a.");
      const { upload_url, s3_url } = await urlRes.json();

      const xhr = new XMLHttpRequest();
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          setUploadProgress(Math.round((event.loaded * 100) / event.total));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploadProgress(100);
          setUploadState("completed");
          setPreviewFile(prev => ({ ...prev, s3Url: s3_url }));
        } else {
          setError(`Greška pri prenosu: ${xhr.statusText}`);
          setUploadState("error");
        }
      };

      xhr.onerror = () => {
        setError("Mrežna greška pri uploadu.");
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

  // Čuvanje nacrta izmena na backendu
  const handleSaveDraft = async () => {
    if (!project) return;
    setSavingProject(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/project/${project.project_id}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segments: project.segments })
      });
      if (!res.ok) throw new Error();
      console.log("[STUDIO] Draft uspešno sačuvan.");
    } catch (err) {
      console.error("Greška pri čuvanju nacrta:", err);
    } finally {
      setSavingProject(false);
    }
  };

  // Probna sinteza jednog segmenta
  const handleTestSegmentTTS = async (segId, text, voiceType) => {
    if (!project) return;
    setLoadingSegmentTTS(prev => ({ ...prev, [segId]: true }));
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/project/${project.project_id}/segment/${segId}/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_type: voiceType || "clone" })
      });
      if (!res.ok) {
        let errorMsg = "TTS failed";
        try {
          const errData = await res.json();
          if (errData && errData.detail) {
            errorMsg = errData.detail;
          }
        } catch (_) {}
        throw new Error(errorMsg);
      }
      const data = await res.json();
      
      // Ažuriramo zvučni fajl za preslušavanje
      const fullAudioUrl = `${API_BASE_URL}${data.audio_url}`;
      setProbniAudios(prev => ({ ...prev, [segId]: fullAudioUrl }));
      
      // Ažuriramo trajanje segmenta lokalno u projektu
      const updatedSegments = project.segments.map(s => {
        if (s.id === segId) {
          return { ...s, translated: text, voice_type: voiceType || "clone", tts_duration: data.duration, status: "previewed" };
        }
        return s;
      });
      setProject({ ...project, segments: updatedSegments });

      // Odmah pusti zvuk da korisnik čuje
      const audio = new Audio(fullAudioUrl);
      audio.play();
    } catch (err) {
      alert("TTS greška: " + err.message);
    } finally {
      setLoadingSegmentTTS(prev => ({ ...prev, [segId]: false }));
    }
  };

  // Generiši glas za ceo video
  const handleGenerateAllTTS = async () => {
    if (!project) return;
    setGeneratingAllTTS(true);
    try {
      // Prvo sačuvamo nacrt
      await handleSaveDraft();
      
      const res = await fetch(`${API_BASE_URL}/api/v1/project/${project.project_id}/generate-all-tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice_type: selectedVoice })
      });
      if (!res.ok) {
        let errorMsg = "Sinteza celog videa nije uspela";
        try {
          const errData = await res.json();
          if (errData && errData.detail) {
            errorMsg = errData.detail;
          }
        } catch (_) {}
        throw new Error(errorMsg);
      }
      const data = await res.json();
      
      // Ažuriramo segmente i putanju za dubbed audio
      setProject(prev => ({
        ...prev,
        segments: data.segments,
        dubbed_audio_path: data.dubbed_audio_url
      }));
      
      // Keširamo sve generisane zvučne fajlove za pojedinačne segmente
      const audios = {};
      data.segments.forEach(s => {
        if (s.tts_path) {
          const filename = s.tts_path.split('/').pop();
          audios[s.id] = `${API_BASE_URL}/videos/${filename}`;
        }
      });
      setProbniAudios(audios);
      
      alert("Uspešno izgenerisan glas za ceo video! Sada možete prebaciti zvuk na vremenskoj liniji na 'Srpski glas (TTS)' da preslušate sinhronizaciju.");
    } catch (err) {
      alert("Greška pri generisanju celog videa: " + err.message);
    } finally {
      setGeneratingAllTTS(false);
    }
  };

  // Slanje projekta na Fazu 2 (Render)
  const handleRenderProject = async () => {
    if (!project) return;
    setRendering(true);
    setLoading(true);
    setStatus("RENDERING FINALNOG VIDEA...");
    setStartTime(Date.now());
    setElapsed(0);
    setError(null);
    
    // Prvo sačuvamo nacrt
    await handleSaveDraft();

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/project/${project.project_id}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voice_type: selectedVoice,
          background_volume: bgVolume,
          dubbed_volume: dubVolume
        })
      });
      if (!res.ok) throw new Error("Render request failed");
      const data = await res.json();
      setRenderTaskId(data.task_id);
      setProject(null); // Zatvaramo studio editor
    } catch (err) {
      setError("Render greška: " + err.message);
      setLoading(false);
      setRendering(false);
    }
  };

  // Vremenska skala i pomeranje playheada
  const getVideoDuration = () => {
    if (!project || !project.segments.length) return 30;
    const lastSeg = project.segments[project.segments.length - 1];
    return Math.max(lastSeg.end + 5, 10);
  };

  const handleTimelineClick = (e) => {
    if (!timelineRef.current || !videoRef.current) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = clickX / rect.width;
    const targetTime = percentage * getVideoDuration();
    
    videoRef.current.currentTime = targetTime;
    setCurrentTime(targetTime);
    
    // Auto-select segment na osnovu vremena
    const matchingSeg = project.segments.find(s => targetTime >= s.start && targetTime <= s.end);
    if (matchingSeg) {
      setSelectedSegmentId(matchingSeg.id);
    }
  };

  // Praćenje vremena video reprodukcije
  useEffect(() => {
    if (isPlaying && videoRef.current) {
      playheadIntervalRef.current = setInterval(() => {
        if (videoRef.current) {
          const t = videoRef.current.currentTime;
          setCurrentTime(t);

          // Resinhronizacija audia ako pobegne za više od 150ms
          if (activeAudioSource === "dubbed" && dubbedAudioRef.current) {
            const diff = Math.abs(videoRef.current.currentTime - dubbedAudioRef.current.currentTime);
            if (diff > 0.15) {
              dubbedAudioRef.current.currentTime = videoRef.current.currentTime;
            }
          }

          // Sinhronizuj selekciju segmenta u realnom vremenu
          const matchingSeg = project?.segments.find(s => t >= s.start && t <= s.end);
          if (matchingSeg && matchingSeg.id !== selectedSegmentId) {
            setSelectedSegmentId(matchingSeg.id);
          }
        }
      }, 50);
    } else {
      clearInterval(playheadIntervalRef.current);
    }
    return () => clearInterval(playheadIntervalRef.current);
  }, [isPlaying, project, selectedSegmentId, activeAudioSource]);

  // Izvedena vrednost za putanju dubbed zvuka
  const dubbedFilename = project?.dubbed_audio_path ? project.dubbed_audio_path.split('/').pop() : null;
  const dubbedAudioUrl = dubbedFilename ? `${API_BASE_URL}/videos/${dubbedFilename}` : null;

  // Sinhronizacija mute stanja i reprodukcije u odnosu na selektovani izvor zvuka
  useEffect(() => {
    const video = videoRef.current;
    const audio = dubbedAudioRef.current;
    if (!video) return;

    if (activeAudioSource === "dubbed" && dubbedAudioUrl) {
      video.muted = true;
      if (audio) {
        if (isPlaying) {
          audio.currentTime = video.currentTime;
          audio.play().catch(err => console.error("Greška pri reprodukciji probnog miksa:", err));
        } else {
          audio.pause();
        }
      }
    } else {
      video.muted = false;
      if (audio) {
        audio.pause();
      }
    }
  }, [activeAudioSource, isPlaying, dubbedAudioUrl]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      if (dubbedAudioRef.current) {
        dubbedAudioRef.current.pause();
      }
    } else {
      videoRef.current.play();
      if (activeAudioSource === "dubbed" && dubbedAudioRef.current) {
        dubbedAudioRef.current.currentTime = videoRef.current.currentTime;
        dubbedAudioRef.current.play().catch(err => console.error("Greška pri reprodukciji probnog miksa:", err));
      }
    }
    setIsPlaying(!isPlaying);
  };

  // Prečica za Spacebar play/pause
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.code === 'Space') {
        const active = document.activeElement;
        if (active && (
          active.tagName === 'INPUT' || 
          active.tagName === 'TEXTAREA' || 
          active.isContentEditable
        )) {
          return;
        }
        e.preventDefault();
        togglePlay();
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPlaying, project, activeAudioSource]);

  // Pomoćna funkcija za iscrtavanje waveform barova u SVG-u
  const generateWaveformBars = (duration, id) => {
    // Koristimo deterministički generator baziran na ID-ju segmenta
    const numBars = Math.max(Math.floor(duration * 6), 5);
    const bars = [];
    let seed = id * 5.7;
    for (let i = 0; i < numBars; i++) {
      seed = (seed * 9301 + 49297) % 233280;
      const height = 15 + (seed / 233280.0) * 35; // Visine između 15px i 50px
      bars.push(height);
    }
    return bars;
  };

  const formatTime = (s) => {
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    const ms = Math.floor((s % 1) * 10);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  return (
    <>
      <div className="aurora-bg">
        <div className="aurora-blob" style={{ top: '10%', left: '10%' }}></div>
        <div className="aurora-blob" style={{ bottom: '10%', right: '10%', background: 'radial-gradient(circle, rgba(236, 72, 153, 0.15) 0%, transparent 70%)' }}></div>
      </div>

      <div className="glass-container studio-layout" style={{ maxWidth: project ? '1400px' : '1200px' }}>
        
        {/* TOP STATUS BAR */}
        <div className="hybrid-monitor">
          <div className="monitor-section">
            <div className="monitor-label"><ShieldCheck size={14}/> Hetzner VPS</div>
            <div className="monitor-stats">
              <span>CPU: {hwStats?.cpu_usage || 0}%</span>
              <span>RAM: {hwStats?.memory?.percent || 0}%</span>
            </div>
          </div>
          <div className="monitor-divider" />
          <div className="monitor-section">
            <div className="monitor-label">
              <Zap size={14} className={modalStatus.status === "Spreman" ? "pulse-icon" : ""}/> 
              Modal GPU
              <span className={`status-badge ${modalStatus.status === "Spreman" ? 'active' : 'asleep'}`}>
                {modalStatus.status === "Spreman" ? `SPREMAN (Auto-scale)` : "SPAVA"}
              </span>
            </div>
            <div className="monitor-status">
              <span className={status.includes("Whisper") ? "active-worker" : ""}>Whisper</span>
              <span className={status.includes("Prevođenje") || status.includes("Lektura") ? "active-worker" : ""}>Qwen</span>
              <span className={status.includes("Sinteza") || status.includes("TTS") ? "active-worker" : ""}>OpenVoice</span>
            </div>
          </div>
          <div className="monitor-divider" />
          <div className="monitor-section" style={{ justifyContent: 'center' }}>
            <button onClick={handleFlushRedis} className="flush-redis-btn" style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '4px 10px', borderRadius: '6px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px', transition: 'all 0.2s', fontFamily: 'inherit' }}>
              <Trash2 size={12} /> Očisti Redis
            </button>
          </div>
        </div>

        {/* LOGO */}
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="logo-section">
            <h1>Sinhronizuj.me <span className="version-badge">STUDIO V2</span></h1>
            <p className="subtitle">Inteligentna sinhronizacija na srpski jezik uz dvofazni pipeline i timeline kontrolu</p>
          </div>
        </motion.div>

        {/* FAZA 0: UNOS VIDEA */}
        {!loading && !videoUrl && !previewFile && !project && (
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
                    title="Uploaduj lokalni video"
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
            <p className="upload-hint">Podržani formati: MP4, WebM, MKV. Maksimalno 500MB.</p>
          </div>
        )}

        {/* PREVIEW NAKON UČITAVANJA PRE ANALIZE */}
        {!loading && !videoUrl && previewFile && !project && (
          <div className="preview-pane-container">
            <div className="preview-video-wrapper">
              {previewFile.type === "youtube" ? (
                <iframe src={previewFile.url} className="preview-media" allowFullScreen title="YouTube Preview"/>
              ) : (
                <video src={previewFile.url} controls className="preview-media" />
              )}
            </div>

            <div className="preview-details-panel">
              <div>
                <h3 className="preview-title" style={{ fontSize: '1.25rem', fontWeight: '700', marginBottom: '8px' }}>Priprema za Analizu (Faza 1)</h3>
                <p className="text-sm text-slate-400 mb-6" style={{ marginBottom: '24px', color: '#94a3b8', fontSize: '0.9rem' }}>
                  Video je uspešno učitan. Prvi korak će analizirati video, izdvojiti audio trake, transkribovati govor na engleskom i kreirati prvi prevod.
                </p>
                
                <div className="file-info-list" style={{ background: 'rgba(0,0,0,0.15)', borderRadius: '12px', padding: '15px', display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
                  <div className="file-info-item" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: '#64748b' }}>Naziv:</span>
                    <span style={{ fontWeight: '600' }}>{previewFile.name}</span>
                  </div>
                  <div className="file-info-item" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: '#64748b' }}>Izvor:</span>
                    <span style={{ fontWeight: '600' }}>{previewFile.type === "local" ? "Lokalni Upload" : "Mrežni URL"}</span>
                  </div>
                </div>
              </div>

              {previewFile.type === "local" && (
                <div className="upload-status-box" style={{ background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '20px' }}>
                  <div className="status-text-row" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span>S3 Transfer:</span>
                    <span style={{ color: uploadState === 'completed' ? '#4ade80' : '#38bdf8', fontWeight: 'bold' }}>
                      {uploadState === 'uploading' ? `Slanje (${uploadProgress}%)` : 'Završeno'}
                    </span>
                  </div>
                </div>
              )}

              <div className="preview-actions-row" style={{ display: 'flex', gap: '12px', marginTop: 'auto' }}>
                <button onClick={resetStudio} className="back-btn" style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '12px', borderRadius: '12px', cursor: 'pointer' }}>
                  Nazad
                </button>
                <button 
                  onClick={handleSubmit} 
                  disabled={previewFile.type === "local" && uploadState !== "completed"} 
                  className="glow-button"
                  style={{ flex: 2, justifyContent: 'center' }}
                >
                  <Play size={18} /> Započni Analizu
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ASINHRONI PROGRES EKRAN (FAZA 1 ILI FAZA 2 RENDER) */}
        {loading && !videoUrl && !project && (
          <div className="studio-interface">
            <div className="studio-content" style={{ maxWidth: '600px', margin: '0 auto' }}>
              <div className="progress-section">
                <div className="progress-header">
                  <span className="current-step-text" style={{ fontSize: '1.2rem', fontWeight: '700' }}>
                    {rendering ? "🎨 Rendering sinhronizacije (Faza 2)" : "🔍 Analiza videa (Faza 1)"}
                  </span>
                  <span className="percent-text">{progressData?.percent || 0}%</span>
                </div>
                
                <div className="progress-bar-container" style={{ margin: '15px 0' }}>
                  <div className="progress-bar-fill" style={{ width: `${progressData?.percent || 0}%` }}></div>
                </div>

                <div className="sub-status-detail" style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem' }}>
                  <Loader2 size={16} className="spinner-icon pulse-icon" />
                  <span>{status || "Inicijalizacija..."}</span>
                </div>

                {progressData?.detail && (
                  <p style={{ fontSize: '0.85rem', color: '#64748b', textAlign: 'center', marginTop: '10px' }}>
                    {progressData.detail}
                  </p>
                )}

                <div style={{ marginTop: '20px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '20px', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Proteklo vreme: {formatTime(elapsed)}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* FAZA 1.5: INTERAKTIVNI STUDIO EDITOR (DRAFT MOD STATUS) */}
        {project && !loading && !videoUrl && (
          <div className="studio-v2-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Gornji radni blok: Video i Forma */}
            <div className="studio-workspace" style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
              
              {/* Leva strana: Preview Player */}
              <div className="video-preview-card" style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div className="video-frame" style={{ width: '100%', aspectRatio: '16/9', background: '#000', borderRadius: '12px', overflow: 'hidden' }}>
                  <video 
                    ref={videoRef}
                    src={`${API_BASE_URL}/videos/${project.video_path.split('/').pop()}`}
                    className="w-full h-full"
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                    onTimeUpdate={() => {
                      if (videoRef.current && !isPlaying) {
                        setCurrentTime(videoRef.current.currentTime);
                      }
                    }}
                  />
                  {dubbedAudioUrl && (
                    <audio 
                      ref={dubbedAudioRef} 
                      src={dubbedAudioUrl} 
                      style={{ display: 'none' }} 
                    />
                  )}
                </div>
                
                {/* Kontrole plejera */}
                <div className="video-player-controls" style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '5px 10px' }}>
                  <button 
                    onClick={togglePlay} 
                    className="play-pause-btn"
                    style={{ background: 'var(--primary)', color: '#fff', border: 'none', width: '38px', height: '38px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                  >
                    {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: '2px' }} />}
                  </button>
                  
                  <div className="time-display" style={{ fontFamily: 'monospace', fontSize: '0.9rem', color: '#94a3b8' }}>
                    {formatTime(currentTime)} / {formatTime(videoRef.current?.duration || getVideoDuration())}
                  </div>

                  {/* Biranje primarnog audia za preslušavanje */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', padding: '4px 8px', borderRadius: '8px', marginLeft: '12px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: '600' }}>Primarni zvuk:</span>
                    <button
                      onClick={() => setActiveAudioSource("original")}
                      style={{
                        background: activeAudioSource === "original" ? 'rgba(139, 92, 246, 0.25)' : 'transparent',
                        border: activeAudioSource === "original" ? '1px solid #8b5cf6' : '1px solid transparent',
                        color: activeAudioSource === "original" ? '#c084fc' : '#94a3b8',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        fontWeight: 'bold',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      Original (ENG)
                    </button>
                    <button
                      onClick={() => {
                        if (!dubbedAudioUrl) {
                          alert("Molimo vas da prvo generišete glas za ceo video klikom na 'Generiši Glas za Ceo Video' na dnu desnog panela.");
                          return;
                        }
                        setActiveAudioSource("dubbed");
                      }}
                      style={{
                        background: activeAudioSource === "dubbed" ? 'rgba(34, 197, 94, 0.25)' : 'transparent',
                        border: activeAudioSource === "dubbed" ? '1px solid #22c55e' : '1px solid transparent',
                        color: activeAudioSource === "dubbed" ? '#4ade80' : '#94a3b8',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        fontWeight: 'bold',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      AI Sinhronizovano (SR)
                    </button>
                  </div>

                  <span style={{ fontSize: '0.8rem', background: 'rgba(255,255,255,0.05)', padding: '4px 10px', borderRadius: '6px', marginLeft: 'auto', border: '1px solid rgba(255,255,255,0.08)' }}>
                    💡 Klikni na vremensku osu ispod da premotaš
                  </span>
                </div>
              </div>

              {/* Desna strana: Detaljan Editor Selektovanog Segmenta */}
              {(() => {
                const activeSegment = project.segments.find(s => s.id === selectedSegmentId) || project.segments[0] || {};
                return (
                  <div className="segment-editor-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Mic size={18} className="text-violet-400" /> Uređivanje Segmenta [{selectedSegmentId}]
                      </h3>
                      <span style={{ fontSize: '0.8rem', color: '#64748b', background: 'rgba(0,0,0,0.2)', padding: '3px 8px', borderRadius: '6px' }}>
                        Trajanje: {((activeSegment.end || 0) - (activeSegment.start || 0)).toFixed(2)}s
                      </span>
                    </div>

                    {/* Originalni tekst */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Original (Engleski):</span>
                      <div style={{ background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)', fontSize: '0.9rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                        "{activeSegment.original}"
                      </div>
                    </div>

                    {/* Prevod tekst (Editabilno) */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Prevod na Srpski:</span>
                      <textarea
                        className="edit-segment-textarea"
                        value={activeSegment.translated || ""}
                        onChange={(e) => {
                          const updated = project.segments.map(s => {
                            if (s.id === selectedSegmentId) {
                              return { ...s, translated: e.target.value, status: "edited" };
                            }
                            return s;
                          });
                          setProject({ ...project, segments: updated });
                        }}
                      />
                      
                      {/* Karakteri limit vizuelni indikator */}
                      {(() => {
                        const dur = (activeSegment.end || 0) - (activeSegment.start || 0);
                        const limit = Math.floor(dur * 20);
                        const currentLen = (activeSegment.translated || "").length;
                        const isOver = currentLen > limit;
                        return (
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginTop: '4px' }}>
                            <span style={{ color: isOver ? '#ef4444' : '#64748b' }}>
                              {isOver ? `⚠️ Prekoračen preporučeni limit za ${currentLen - limit} karaktera!` : `Preporučeno do ${limit} karaktera.`}
                            </span>
                            <span style={{ color: isOver ? '#ef4444' : '#cbd5e1', fontWeight: '600' }}>
                              {currentLen} / {limit}
                            </span>
                          </div>
                        );
                      })()}
                    </div>

                    {/* Odabir glasa za ovaj segment */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Glas za ovaj segment:</span>
                      <select
                        value={activeSegment.voice_type || "clone"}
                        onChange={(e) => {
                          const updated = project.segments.map(s => {
                            if (s.id === selectedSegmentId) {
                              return { ...s, voice_type: e.target.value, status: "edited" };
                            }
                            return s;
                          });
                          setProject({ ...project, segments: updated });
                        }}
                        style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', padding: '8px 12px', borderRadius: '8px', outline: 'none', fontSize: '0.85rem', cursor: 'pointer' }}
                      >
                        <option value="clone">Kloniraj originalni glas (OpenVoice V2)</option>
                        <option value="male">Muški glas (Piper - sr_Marko)</option>
                      </select>
                    </div>

                    {/* Akcije za segment */}
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: 'auto', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '15px' }}>
                      {/* Preslušavanje probnog TTS-a */}
                      {probniAudios[selectedSegmentId] ? (
                        <div style={{ flex: 1 }}>
                          <audio src={probniAudios[selectedSegmentId]} controls style={{ width: '100%', height: '36px' }} />
                        </div>
                      ) : (
                        <span style={{ flex: 1, fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic' }}>
                          Glas nije generisan za ovaj segment. Klikni "Generiši Probni Glas".
                        </span>
                      )}
                      
                      <button 
                        onClick={() => handleTestSegmentTTS(selectedSegmentId, activeSegment.translated || "", activeSegment.voice_type)}
                        disabled={loadingSegmentTTS[selectedSegmentId]}
                        className="glow-button"
                        style={{ background: '#3b82f6', boxShadow: 'none', padding: '10px 16px', fontSize: '0.85rem' }}
                      >
                        {loadingSegmentTTS[selectedSegmentId] ? (
                          <Loader2 size={16} className="spinner-icon pulse-icon" />
                        ) : (
                          "🎙️ Generiši Probni Glas"
                        )}
                      </button>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* TIMELINE (VREMENSKA LINIJA SA TRAKAMA) */}
            <div 
              className="timeline-card" 
              style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '20px', overflowX: 'auto' }}
            >
              <h4 style={{ fontSize: '0.9rem', fontWeight: '700', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Film size={16} /> Vremenski Editor (Timeline)
              </h4>

              {/* Vremenska skala i kontejner traka */}
              <div 
                ref={timelineRef}
                onClick={handleTimelineClick}
                style={{ minWidth: '800px', position: 'relative', cursor: 'ew-resize', display: 'flex', flexDirection: 'column', gap: '4px' }}
              >
                {/* 1. Skala sekundi */}
                <div style={{ height: '24px', position: 'relative', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#475569', fontSize: '0.75rem' }}>
                  {(() => {
                    const dur = getVideoDuration();
                    const ticks = [];
                    const step = dur > 60 ? 10 : 5; // Ticks na svakih 5 ili 10 sekundi
                    for (let i = 0; i <= dur; i += step) {
                      const leftPercent = (i / dur) * 100;
                      ticks.push(
                        <div key={i} style={{ position: 'absolute', left: `${leftPercent}%`, transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                          <span>{i}s</span>
                          <div style={{ width: '1px', height: '4px', background: '#475569', marginTop: '2px' }} />
                        </div>
                      );
                    }
                    return ticks;
                  })()}
                </div>

                {/* 2. TRAKA: VIDEO SLIČICE (Frame list) */}
                <div style={{ height: '36px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.03)', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center' }}>
                  <div style={{ position: 'absolute', left: '10px', fontSize: '0.7rem', color: '#475569', zIndex: 5, pointerEvents: 'none', textTransform: 'uppercase', fontWeight: 'bold' }}>
                    <Video size={10} style={{ display: 'inline', marginRight: '4px' }} /> Video Sličice
                  </div>
                  {project.visual_context_url && (
                    <img 
                      src={project.visual_context_url} 
                      style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.25, pointerEvents: 'none' }} 
                      alt="Visual keyframes timeline"
                    />
                  )}
                </div>

                {/* 3. TRAKA: ORIGINALNI GOVOR (Engleski) */}
                <div style={{ height: '54px', background: 'rgba(139, 92, 246, 0.03)', borderRadius: '6px', border: '1px solid rgba(139, 92, 246, 0.08)', position: 'relative' }}>
                  <div style={{ position: 'absolute', left: '10px', top: '5px', zIndex: 5, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button 
                      onClick={(e) => { e.stopPropagation(); setActiveAudioSource("original"); }}
                      style={{ 
                        background: activeAudioSource === "original" ? 'rgba(139, 92, 246, 0.8)' : 'rgba(0,0,0,0.5)', 
                        border: '1px solid rgba(139, 92, 246, 0.4)', 
                        borderRadius: '4px', 
                        color: '#fff', 
                        fontSize: '0.65rem', 
                        padding: '2px 8px', 
                        cursor: 'pointer',
                        fontWeight: 'bold',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        outline: 'none',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: activeAudioSource === "original" ? '#fff' : 'transparent', border: '1px solid #fff' }} />
                      <Mic size={10} /> Originalni ENG Vokal {activeAudioSource === "original" ? "(Aktivno)" : ""}
                    </button>
                  </div>
                  
                  {/* Renderujemo regione segmenata */}
                  {project.segments.map(seg => {
                    const dur = getVideoDuration();
                    const left = (seg.start / dur) * 100;
                    const width = ((seg.end - seg.start) / dur) * 100;
                    const isActive = selectedSegmentId === seg.id;
                    return (
                      <div 
                        key={seg.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSegmentId(seg.id);
                          if (videoRef.current) {
                            videoRef.current.currentTime = seg.start;
                            if (activeAudioSource === "dubbed" && dubbedAudioRef.current) {
                              dubbedAudioRef.current.currentTime = seg.start;
                            }
                          }
                        }}
                        style={{
                          position: 'absolute',
                          left: `${left}%`,
                          width: `${width}%`,
                          height: '36px',
                          bottom: '4px',
                          background: isActive ? 'rgba(139, 92, 246, 0.25)' : 'rgba(139, 92, 246, 0.08)',
                          border: isActive ? '2px solid #8b5cf6' : '1px solid rgba(139, 92, 246, 0.2)',
                          borderRadius: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          overflow: 'hidden',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {/* Custom Waveform u pozadini */}
                        <div style={{ position: 'absolute', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 4px', opacity: isActive ? 0.45 : 0.25 }}>
                          {generateWaveformBars(seg.end - seg.start, seg.id).map((h, i) => (
                            <div key={i} style={{ width: '2px', height: `${h}%`, background: '#8b5cf6', borderRadius: '1px' }} />
                          ))}
                        </div>
                        <span style={{ fontSize: '0.65rem', color: '#c084fc', fontWeight: 'bold', zIndex: 10, pointerEvents: 'none' }}>
                          #{seg.id}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* 4. TRAKA: SRPSKI SINHRONIZOVANI GLAS */}
                <div style={{ height: '54px', background: 'rgba(34, 197, 94, 0.02)', borderRadius: '6px', border: '1px solid rgba(34, 197, 94, 0.08)', position: 'relative' }}>
                  <div style={{ position: 'absolute', left: '10px', top: '5px', zIndex: 5, display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button 
                      onClick={(e) => { 
                        e.stopPropagation(); 
                        if (!dubbedAudioUrl) {
                          alert("Molimo vas da prvo generišete glas za ceo video klikom na 'Generiši Glas za Ceo Video'.");
                          return;
                        }
                        setActiveAudioSource("dubbed"); 
                      }}
                      style={{ 
                        background: activeAudioSource === "dubbed" ? 'rgba(34, 197, 94, 0.8)' : 'rgba(0,0,0,0.5)', 
                        border: '1px solid rgba(34, 197, 94, 0.4)', 
                        borderRadius: '4px', 
                        color: '#fff', 
                        fontSize: '0.65rem', 
                        padding: '2px 8px', 
                        cursor: 'pointer',
                        fontWeight: 'bold',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        outline: 'none',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: activeAudioSource === "dubbed" ? '#fff' : 'transparent', border: '1px solid #fff' }} />
                      <Volume2 size={10} /> Srpski glas (TTS) {activeAudioSource === "dubbed" ? "(Aktivno)" : ""}
                    </button>
                    {!dubbedAudioUrl && (
                      <span style={{ fontSize: '0.65rem', color: '#64748b', fontStyle: 'italic' }}>(Potrebno generisati ceo glas)</span>
                    )}
                  </div>
                  
                  {project.segments.map(seg => {
                    const dur = getVideoDuration();
                    const left = (seg.start / dur) * 100;
                    const origWidth = ((seg.end - seg.start) / dur) * 100;
                    
                    // Ako imamo generisan tts_duration, koristimo njega da vidimo da li je duži
                    const ttsDur = seg.tts_duration || (seg.end - seg.start);
                    const ttsWidth = (ttsDur / dur) * 100;
                    const isLonger = seg.tts_duration && (seg.tts_duration > (seg.end - seg.start));
                    const isActive = selectedSegmentId === seg.id;
                    
                    return (
                      <div 
                        key={seg.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSegmentId(seg.id);
                          if (videoRef.current) {
                            videoRef.current.currentTime = seg.start;
                            if (activeAudioSource === "dubbed" && dubbedAudioRef.current) {
                              dubbedAudioRef.current.currentTime = seg.start;
                            }
                          }
                        }}
                        style={{
                          position: 'absolute',
                          left: `${left}%`,
                          width: `${Math.max(origWidth, ttsWidth)}%`,
                          height: '36px',
                          bottom: '4px',
                          borderRadius: '4px',
                          display: 'flex',
                          alignItems: 'center',
                          overflow: 'hidden',
                          border: isActive ? '2px solid #22c55e' : '1px solid rgba(34, 197, 94, 0.15)',
                          background: isActive ? 'rgba(34, 197, 94, 0.2)' : 'rgba(34, 197, 94, 0.05)',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {/* Ako je duži, obeležavamo crvenom pozadinom višak trajanja */}
                        {isLonger && (
                          <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${((seg.tts_duration - (seg.end - seg.start)) / seg.tts_duration) * 100}%`, background: 'rgba(239, 68, 68, 0.35)', borderLeft: '1px dashed #ef4444' }} title="Predugačko! Biće primenjeno usporavanje videa." />
                        )}
 
                        {/* Waveform */}
                        <div style={{ position: 'absolute', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 4px', opacity: isActive ? 0.5 : 0.25 }}>
                          {generateWaveformBars(ttsDur, seg.id + 10).map((h, i) => (
                            <div key={i} style={{ width: '2px', height: `${h}%`, background: isLonger ? '#f87171' : '#4ade80', borderRadius: '1px' }} />
                          ))}
                        </div>

                        <span style={{ fontSize: '0.65rem', color: isLonger ? '#f87171' : '#86efac', fontWeight: 'bold', marginLeft: '6px', zIndex: 10 }}>
                          #{seg.id} {isLonger ? `(⚠️ +${(seg.tts_duration - (seg.end - seg.start)).toFixed(1)}s)` : ''}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* 5. TRAKA: POZADINSKA MUZIKA */}
                <div style={{ height: '40px', background: 'rgba(255,255,255,0.01)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.05)', position: 'relative' }}>
                  <div style={{ position: 'absolute', left: '10px', top: '4px', fontSize: '0.7rem', color: '#475569', zIndex: 5, pointerEvents: 'none', textTransform: 'uppercase', fontWeight: 'bold' }}>
                    <Music size={10} style={{ display: 'inline', marginRight: '4px' }} /> Pozadinski zvuk (Muzika / Efekti)
                  </div>
                  {/* Crtamo talasni oblik celom dužinom */}
                  <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 10px', opacity: 0.1, pointerEvents: 'none' }}>
                    {Array.from({ length: 80 }).map((_, i) => (
                      <div key={i} style={{ width: '2px', height: `${20 + Math.sin(i * 0.3) * 15}%`, background: '#cbd5e1', borderRadius: '1px' }} />
                    ))}
                  </div>
                </div>

                {/* KURSOR (PLAYHEAD) KOJI KLIZI */}
                {(() => {
                  const dur = getVideoDuration();
                  const leftPercent = (currentTime / dur) * 100;
                  return (
                    <div 
                      style={{
                        position: 'absolute',
                        left: `${leftPercent}%`,
                        top: '24px',
                        bottom: 0,
                        width: '2px',
                        background: '#ef4444',
                        boxShadow: '0 0 10px #ef4444',
                        zIndex: 100,
                        pointerEvents: 'none'
                      }}
                    >
                      <div style={{ position: 'absolute', top: '-6px', left: '-5px', width: '12px', height: '12px', borderRadius: '50%', background: '#ef4444', border: '2px solid #fff' }} />
                    </div>
                  );
                })()}

              </div>
            </div>

            {/* Donji kontrolni blok: Mikser i Podešavanje glasa + Render dugme */}
            <div 
              className="studio-controls-row" 
              style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '24px' }}
            >
              {/* Leva strana: Mixer i odabir glasa */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <h4 style={{ fontSize: '0.9rem', fontWeight: '700', textTransform: 'uppercase', color: '#94a3b8' }}>🎛️ Audio Mikser & Podešavanje glasa</h4>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {/* Jačina pozadine */}
                  <div className="mixer-control" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Muzika i efekti:</span>
                      <strong>{bgVolume} dB</strong>
                    </label>
                    <input 
                      type="range" min="-30" max="10" step="1" value={bgVolume} 
                      onChange={(e) => setBgVolume(parseInt(e.target.value))}
                      style={{ width: '100%', accentColor: 'var(--primary)' }}
                    />
                  </div>
                  {/* Jačina srpskog glasa */}
                  <div className="mixer-control" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Srpski AI glas:</span>
                      <strong>{dubVolume} dB</strong>
                    </label>
                    <input 
                      type="range" min="-15" max="15" step="1" value={dubVolume} 
                      onChange={(e) => setDubVolume(parseInt(e.target.value))}
                      style={{ width: '100%', accentColor: 'var(--primary)' }}
                    />
                  </div>
                </div>

                {/* Izbor glasa */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Odabir TTS Glasa:</label>
                  <select 
                    value={selectedVoice} 
                    onChange={(e) => setSelectedVoice(e.target.value)}
                    style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', color: '#fff', padding: '10px', borderRadius: '8px', outline: 'none' }}
                  >
                    <option value="clone">Kloniraj originalni glas (OpenVoice V2)</option>
                    <option value="male">Muški glas (Piper - sr_Marko)</option>
                  </select>
                </div>
              </div>

              {/* Desna strana: Glavna akcija (Render) */}
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '15px', borderLeft: '1px solid rgba(255,255,255,0.05)', paddingLeft: '24px' }}>
                <div style={{ textAlign: 'center' }}>
                  <h4 style={{ fontSize: '1rem', fontWeight: '700', color: '#fff', marginBottom: '6px' }}>Spremni za Finalni Render?</h4>
                  <p style={{ fontSize: '0.8rem', color: '#64748b', lineHeight: '1.4', maxWidth: '300px' }}>
                    Sve izmene na prevodu biće sačuvane, a sistem će primeniti dynamic time stretching i Wav2Lip za fotorealističnu sinhronizaciju.
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '100%', maxWidth: '300px' }}>
                  <button 
                    onClick={handleGenerateAllTTS}
                    disabled={generatingAllTTS}
                    className="glow-button"
                    style={{ background: 'var(--primary)', justifyContent: 'center', fontSize: '0.85rem', width: '100%' }}
                  >
                    {generatingAllTTS ? <Loader2 size={16} className="spinner-icon pulse-icon" /> : <Mic size={16} />} Generiši Glas za Ceo Video
                  </button>
                  
                  <div style={{ display: 'flex', gap: '12px', width: '100%' }}>
                    <button 
                      onClick={handleSaveDraft}
                      disabled={savingProject}
                      className="new-task-btn"
                      style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '0.85rem' }}
                    >
                      {savingProject ? <Loader2 size={14} className="spinner-icon pulse-icon" /> : <Save size={14} />} Sačuvaj
                    </button>
                    <button 
                      onClick={handleRenderProject}
                      className="glow-button"
                      style={{ flex: 2, justifyContent: 'center', fontSize: '0.85rem', background: '#22c55e', boxShadow: '0 0 10px rgba(34, 197, 94, 0.3)' }}
                    >
                      <Zap size={16} /> Renderuj Video
                    </button>
                  </div>
                </div>
              </div>

            </div>

          </div>
        )}

        {/* REZULTAT (ZAVRŠENO) */}
        {videoUrl && !loading && (
          <div className="final-result">
            <div className="success-banner">
              <CheckCircle2 size={24} /> SINHRONIZACIJA USPEŠNO ZAVRŠENA!
            </div>
            
            <div className="video-player-wrapper">
              <video src={videoUrl} controls autoPlay />
            </div>

            {/* Prikaz troškova */}
            {costs && (
              <div className="costs-report" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '24px', maxWidth: '600px', margin: '0 auto', textAlign: 'left' }}>
                <h4 style={{ fontSize: '0.9rem', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '15px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '10px' }}>
                  📊 Izveštaj o GPU potrošnji i troškovima
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {Object.entries(costs.phases || {}).map(([key, value]) => (
                    <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span style={{ color: '#cbd5e1' }}>{value.name} ({value.gpu}):</span>
                      <span style={{ fontFamily: 'monospace' }}>{value.duration_sec}s / ${value.cost_usd.toFixed(4)}</span>
                    </div>
                  ))}
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.95rem', fontWeight: 'bold', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '10px', marginTop: '10px', color: '#4ade80' }}>
                    <span>Ukupni troškovi obrade:</span>
                    <span>${costs.total_usd?.toFixed(4)} USD</span>
                  </div>
                </div>
              </div>
            )}

            <div className="result-actions">
              <button onClick={resetStudio} className="new-task-btn">
                Učitaj novi video
              </button>
              <a href={videoUrl} download className="download-btn">
                Preuzmi video
              </a>
            </div>
          </div>
        )}

      </div>
    </>
  );
}

export default App;

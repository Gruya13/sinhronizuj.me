/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useRef } from 'react';
import { api } from '../services/api';

const StudioContext = createContext();

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";

export function StudioProvider({ children }) {
  // Stanja za autentifikaciju
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('sinhronizuj_me_token'));

  // Stanja za listu projekata i pretragu
  const [projects, setProjects] = useState([]);
  const [showProjectsList, setShowProjectsList] = useState(true);
  const [newProjectName, setNewProjectName] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [currentProjectId, setCurrentProjectId] = useState(null);

  // Globalni tokovi stanja za učitavanje i obradu
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
  const [url, setUrl] = useState('');

  // Studio v2 specifična stanja
  const [project, setProject] = useState(null);
  const [selectedSegmentId, setSelectedSegmentIdState] = useState(0);
  const [selectedSegmentIds, setSelectedSegmentIds] = useState([]);

  const setSelectedSegmentId = (id) => {
    setSelectedSegmentIdState(id);
    setSelectedSegmentIds(prev => {
      if (prev.includes(id) && prev.length === 1) return prev;
      return [id];
    });
  };

  // Undo/Redo istorija
  const [historyStack, setHistoryStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);

  const saveToHistory = (segmentsToSave) => {
    if (!segmentsToSave) return;
    const copy = JSON.parse(JSON.stringify(segmentsToSave));
    setHistoryStack(prev => {
      const next = [...prev, copy];
      if (next.length > 50) {
        next.shift();
      }
      return next;
    });
    setRedoStack([]);
  };

  const handleUndo = () => {
    if (historyStack.length === 0 || !project) return;
    const currentSegs = JSON.parse(JSON.stringify(project.segments));
    setHistoryStack(prev => {
      const nextStack = [...prev];
      const prevSegs = nextStack.pop();
      setRedoStack(redo => [...redo, currentSegs]);
      setProject(prevProj => ({
        ...prevProj,
        segments: prevSegs
      }));
      // Sinhronizuj selektovani segment ako je stari id nestao ili se promenio
      if (prevSegs.length > 0) {
        const stillExists = prevSegs.some(s => s.id === selectedSegmentId);
        if (!stillExists) {
          setSelectedSegmentIdState(prevSegs[0].id);
          setSelectedSegmentIds([prevSegs[0].id]);
        }
      }
      return nextStack;
    });
  };

  const handleRedo = () => {
    if (redoStack.length === 0 || !project) return;
    const currentSegs = JSON.parse(JSON.stringify(project.segments));
    setRedoStack(prev => {
      const nextStack = [...prev];
      const nextSegs = nextStack.pop();
      setHistoryStack(history => [...history, currentSegs]);
      setProject(prevProj => ({
        ...prevProj,
        segments: nextSegs
      }));
      if (nextSegs.length > 0) {
        const stillExists = nextSegs.some(s => s.id === selectedSegmentId);
        if (!stillExists) {
          setSelectedSegmentIdState(nextSegs[0].id);
          setSelectedSegmentIds([nextSegs[0].id]);
        }
      }
      return nextStack;
    });
  };
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [bgVolume, setBgVolume] = useState(-5);
  const [dubVolume, setDubVolume] = useState(0);
  const [selectedVoice, setSelectedVoice] = useState("clone");
  const [probniAudios, setProbniAudios] = useState({});
  const [loadingSegmentTTS, setLoadingSegmentTTS] = useState({});
  const [shorteningActive, setShorteningActive] = useState({});
  const [savingProject, setSavingProject] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderTaskId, setRenderTaskId] = useState(null);
  const [costs, setCosts] = useState(null);
  const [activeAudioSource, setActiveAudioSource] = useState("original"); // original or dubbed
  const [generatingAllTTS, setGeneratingAllTTS] = useState(false);
  const [dubbedBuster, setDubbedBuster] = useState(() => Date.now());
  const [segmentEditorTab, setSegmentEditorTab] = useState("text"); // text or audio
  const [activeDubbedAudioUrl, setActiveDubbedAudioUrl] = useState(null);
  const [applyAudioToAll, setApplyAudioToAll] = useState(false);
  const [visualContextError, setVisualContextError] = useState(false);
  const [hoveredSegmentId, setHoveredSegmentId] = useState(null);
  const [shouldFocusTextarea, setShouldFocusTextarea] = useState(false);

  // Reference za audio/video
  const videoRef = useRef(null);
  const timelineRef = useRef(null);
  const fileInputRef = useRef(null);
  const consecutiveErrorsRef = useRef(0);
  const playheadIntervalRef = useRef(null);
  const dubbedAudioRef = useRef(null);
  const bgAudioRef = useRef(null);

  const getVideoDuration = () => {
    if (!project || !project.segments || !project.segments.length) return 30;
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
    
    if (activeAudioSource === "dubbed") {
      if (dubbedAudioRef.current) dubbedAudioRef.current.currentTime = targetTime;
      if (bgAudioRef.current) bgAudioRef.current.currentTime = targetTime;
    }
    
    // Auto-select segment na osnovu vremena
    const matchingSeg = project.segments.find(s => targetTime >= s.start && targetTime <= s.end);
    if (matchingSeg) {
      setSelectedSegmentId(matchingSeg.id);
    }
  };

  const handleLogin = async (email, password) => {
    try {
      const data = await api.login(email, password);
      setToken(data.access_token);
      setUser(data.user);
      setError(null);
    } catch (err) {
      setError(err.message || "Neuspešna prijava");
      throw err;
    }
  };

  const handleRegister = async (email, password) => {
    try {
      await api.register(email, password);
      setError(null);
    } catch (err) {
      setError(err.message || "Neuspešna registracija");
      throw err;
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('sinhronizuj_me_token');
    setToken(null);
    setUser(null);
    resetStudio();
  };

  // Automatska provera sesije
  useEffect(() => {
    const checkAuth = async () => {
      if (token) {
        try {
          const userData = await api.getMe();
          setUser(userData);
          fetchProjects();
        } catch (err) {
          console.error("Greška pri verifikaciji sesije:", err);
          handleLogout();
        }
      } else {
        setUser(null);
      }
    };
    checkAuth();
  }, [token]);

  // Listanje projekata
  async function fetchProjects() {
    if (!localStorage.getItem('sinhronizuj_me_token')) return;
    try {
      const data = await api.getProjects();
      setProjects(data);
    } catch (err) {
      console.error("Greška pri listanju projekata:", err);
      if (err.status === 401) {
        handleLogout();
      }
    }
  };

  // Monitor resursa (samo kada je korisnik autentifikovan)
  useEffect(() => {
    if (!token) {
      setHwStats(null);
      setModalStatus(null);
      return;
    }

    const fetchHw = async () => {
      try {
        const data = await api.getHwStats();
        setHwStats(data);
      } catch (_) { /* Silent fail */ }
    };
    const fetchModal = async () => {
      try {
        const data = await api.getModalStatus();
        setModalStatus(data);
      } catch (_) { /* Silent fail */ }
    };
    fetchHw();
    fetchModal();
    const intervalHw = setInterval(fetchHw, 5000);
    const intervalMd = setInterval(fetchModal, 15000);
    return () => {
      clearInterval(intervalHw);
      clearInterval(intervalMd);
    };
  }, [token]);

  // Tajmer za trajanje obrade (sat)
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
          const data = await api.getTaskStatus(currentTask);
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
              fetchProjects();
            } else {
              // Faza 1 završena, prelazimo u Studio mod
              setProgressData(null);
              setLoading(false);
              const targetProjId = data.project_id || taskId;
              setCurrentProjectId(targetProjId);
              loadProjectData(targetProjId);
              clearInterval(interval);
              fetchProjects();
            }
          } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
            setError(data.error || 'Greška pri obradi.');
            setLoading(false);
            setRendering(false);
            localStorage.removeItem('sinhronizuj_me_task_id');
            setRenderTaskId(null);
            clearInterval(interval);
            fetchProjects();
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
          if (err.name === "ApiError" && err.status === 404) {
            console.warn("Zadatak nije pronađen (404).");
            resetStudio();
            return;
          }
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

  // Resetovanje studija
  function resetStudio() {
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
    setHistoryStack([]);
    setRedoStack([]);
    setSelectedSegmentIds([]);
    
    // Povratak na projekte
    setCurrentProjectId(null);
    setShowProjectsList(true);
    fetchProjects();
  };

  // Učitavanje podataka o projektu
  const loadProjectData = async (projId) => {
    try {
      setStatus('Učitavam radni prostor...');
      const data = await api.getProject(projId);
      if (data.segments) {
        data.segments = data.segments.map(s => ({
          ...s,
          volume: s.volume !== undefined ? s.volume : 0.0,
          speed: s.speed !== undefined ? s.speed : 1.0,
          pitch: s.pitch !== undefined ? s.pitch : 0.0,
          bg_volume: s.bg_volume !== undefined ? s.bg_volume : 0.0,
          last_generated_volume: s.volume !== undefined ? s.volume : 0.0,
          last_generated_speed: s.speed !== undefined ? s.speed : 1.0,
          last_generated_bg_volume: s.bg_volume !== undefined ? s.bg_volume : 0.0
        }));
      }
      setProject(data);
      setHistoryStack([]);
      setRedoStack([]);
      if (data.costs) setCosts(data.costs);
      if (data.segments && data.segments.length > 0) {
        setSelectedSegmentId(data.segments[0].id);
      }
      
      // Keširamo probne audije
      const audios = {};
      data.segments.forEach(s => {
        if (s.tts_path) {
          if (s.tts_path.startsWith('http://') || s.tts_path.startsWith('https://')) {
            audios[s.id] = s.tts_path;
          } else {
            const filename = s.tts_path.split('/').pop();
            audios[s.id] = `${API_BASE_URL}/videos/${filename}`;
          }
        }
      });
      setProbniAudios(audios);
    } catch (err) {
      setError("Greška pri učitavanju projekta: " + err.message);
    }
  };

  const handleSelectProject = (proj) => {
    setCurrentProjectId(proj.id);
    setShowProjectsList(false);
    setError(null);
    setVideoUrl(null);
    setPreviewFile(null);
    setProject(null);

    if (proj.status === 'empty') {
      setLoading(false);
    } else if (proj.status === 'analyzing') {
      setLoading(true);
      setStatus('Projekat se analizira u pozadini...');
      loadProjectData(proj.id);
    } else if (proj.status === 'ready' || proj.status === 'completed') {
      loadProjectData(proj.id);
    }
  };

  const handleCreateProject = async (e) => {
    if (e) e.preventDefault();
    if (!newProjectName.trim()) return;
    setCreatingProject(true);
    try {
      const newProj = await api.createProject(newProjectName);
      setProjects(prev => [newProj, ...prev]);
      setNewProjectName('');
      setIsCreateModalOpen(false);
      handleSelectProject(newProj);
    } catch (err) {
      alert("Greška pri kreiranju projekta: " + err.message);
    } finally {
      setCreatingProject(false);
    }
  };

  const handleDeleteProject = async (e, projId) => {
    e.stopPropagation();
    if (!window.confirm("Da li ste sigurni da želite da obrišete ovaj projekat i sve njegove fajlove?")) {
      return;
    }
    try {
      await api.deleteProject(projId);
      setProjects(prev => prev.filter(p => p.id !== projId));
      if (currentProjectId === projId) {
        resetStudio();
      }
    } catch (err) {
      alert("Greška pri brisanju projekta: " + err.message);
    }
  };

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
      const data = await api.processVideo(targetUrl, currentProjectId);
      setTaskId(data.task_id);
      localStorage.setItem('sinhronizuj_me_task_id', data.task_id);
    } catch (err) {
      setError('Greška pri pokretanju analize: ' + err.message);
      setLoading(false);
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
      const { upload_url, s3_url } = await api.getUploadUrl(file.name, file.type);

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

  // Čuvanje nacrta (save draft)
  const handleSaveDraft = async () => {
    if (!project) return;
    setSavingProject(true);
    try {
      await api.saveProjectDraft(project.project_id, project.segments);
      console.log("[STUDIO] Draft uspešno sačuvan.");
    } catch (err) {
      console.error("Greška pri čuvanju nacrta:", err);
    } finally {
      setSavingProject(false);
    }
  };

  // Magično skraćivanje teksta
  const handleMagicShorten = async (segId) => {
    if (!project) return;
    const seg = project.segments.find(s => s.id === segId);
    if (!seg) return;
    
    setShorteningActive(prev => ({ ...prev, [segId]: true }));
    try {
      await handleSaveDraft();
      const data = await api.shortenSegment(project.project_id, segId, seg.translated || "");
      
      const updatedSegments = project.segments.map(s => {
        if (s.id === segId) {
          return { 
            ...s, 
            translated: data.shortened_text, 
            status: "edited" 
          };
        }
        return s;
      });
      setProject({ ...project, segments: updatedSegments });
    } catch (err) {
      alert(`Greška pri skraćivanju: ${err.message}`);
    } finally {
      setShorteningActive(prev => ({ ...prev, [segId]: false }));
    }
  };

  // Probna sinteza jednog segmenta
  const handleTestSegmentTTS = async (segId, text, voiceType, volume = 0.0, speed = 1.0, pitch = 0.0, bgVolume = 0.0, autoplay = true) => {
    if (!project) return;
    setLoadingSegmentTTS(prev => ({ ...prev, [segId]: true }));
    try {
      const data = await api.generateSegmentTTS(
        project.project_id,
        segId,
        text,
        voiceType || "clone",
        volume !== undefined ? volume : 0.0,
        speed !== undefined ? speed : 1.0,
        pitch !== undefined ? pitch : 0.0,
        bgVolume !== undefined ? bgVolume : 0.0
      );
      
      const fullAudioUrl = `${API_BASE_URL}${data.audio_url}?cb=${Date.now()}`;
      setProbniAudios(prev => ({ ...prev, [segId]: fullAudioUrl }));
      
      const updatedSegments = project.segments.map(s => {
        if (s.id === segId) {
          return { 
            ...s, 
            translated: text, 
            voice_type: voiceType || "clone", 
            tts_duration: data.duration, 
            volume, 
            speed, 
            pitch, 
            bg_volume: bgVolume,
            last_generated_volume: volume,
            last_generated_speed: speed,
            last_generated_bg_volume: bgVolume,
            status: "previewed" 
          };
        }
        return s;
      });
      setProject({ ...project, segments: updatedSegments });
      setDubbedBuster(Date.now());

      if (autoplay && !isPlaying) {
        const audio = new Audio(fullAudioUrl);
        audio.play().catch(err => console.error("Greška pri reprodukciji probnog segmenta:", err));
      }
    } catch (err) {
      alert("TTS greška: " + err.message);
    } finally {
      setLoadingSegmentTTS(prev => ({ ...prev, [segId]: false }));
    }
  };

  // Generisanje glasa za ceo video
  const handleGenerateAllTTS = async () => {
    if (!project) return;
    setGeneratingAllTTS(true);
    try {
      await handleSaveDraft();
      const data = await api.generateAllTTS(project.project_id, selectedVoice);
      
      const mappedSegs = data.segments.map(s => ({
        ...s,
        last_generated_volume: s.volume !== undefined ? s.volume : 0.0,
        last_generated_speed: s.speed !== undefined ? s.speed : 1.0
      }));
      setProject(prev => ({
        ...prev,
        segments: mappedSegs,
        dubbed_audio_path: data.dubbed_audio_url
      }));
      setDubbedBuster(Date.now());
      
      const audios = {};
      data.segments.forEach(s => {
        if (s.tts_path) {
          if (s.tts_path.startsWith('http://') || s.tts_path.startsWith('https://')) {
            audios[s.id] = s.tts_path;
          } else {
            const filename = s.tts_path.split('/').pop();
            audios[s.id] = `${API_BASE_URL}/videos/${filename}?cb=${Date.now()}`;
          }
        }
      });
      setProbniAudios(audios);
      
      alert("Uspešno izgenerisan glas za ceo video!");
    } catch (err) {
      alert("Greška pri generisanju celog videa: " + err.message);
    } finally {
      setGeneratingAllTTS(false);
    }
  };

  // Pokretanje finalnog renderovanja
  const handleRenderProject = async () => {
    if (!project) return;
    setRendering(true);
    setLoading(true);
    setStatus("RENDERING FINALNOG VIDEA...");
    setStartTime(Date.now());
    setElapsed(0);
    setError(null);
    
    await handleSaveDraft();
    try {
      const data = await api.renderProject(
        project.project_id,
        selectedVoice,
        bgVolume,
        dubVolume
      );
      setRenderTaskId(data.task_id);
      setProject(null);
    } catch (err) {
      setError("Render greška: " + err.message);
      setLoading(false);
      setRendering(false);
    }
  };

  // Čišćenje Redis keša
  const handleFlushRedis = async () => {
    if (window.confirm("Da li ste sigurni da želite da očistite Redis keš? Ovo će obrisati sve neaktivne projekte stare preko 7 dana.")) {
      try {
        await api.flushRedis();
        alert("Redis keš uspešno očišćen!");
        fetchProjects();
      } catch (err) {
        alert("Greška pri čišćenju Redis-a: " + err.message);
      }
    }
  };

  return (
    <StudioContext.Provider value={{
      user, setUser,
      token, setToken,
      handleLogin, handleRegister, handleLogout,
      projects, setProjects,
      showProjectsList, setShowProjectsList,
      newProjectName, setNewProjectName,
      isCreateModalOpen, setIsCreateModalOpen,
      creatingProject, setCreatingProject,
      currentProjectId, setCurrentProjectId,
      loading, setLoading,
      taskId, setTaskId,
      status, setStatus,
      progressData, setProgressData,
      videoUrl, setVideoUrl,
      error, setError,
      startTime, setStartTime,
      elapsed, setElapsed,
      hwStats, setHwStats,
      modalStatus, setModalStatus,
      uploadProgress, setUploadProgress,
      uploadState, setUploadState,
      previewFile, setPreviewFile,
      project, setProject,
      selectedSegmentId, setSelectedSegmentId,
      selectedSegmentIds, setSelectedSegmentIds,
      historyStack, redoStack,
      saveToHistory, handleUndo, handleRedo,
      currentTime, setCurrentTime,
      isPlaying, setIsPlaying,
      bgVolume, setBgVolume,
      dubVolume, setDubVolume,
      selectedVoice, setSelectedVoice,
      probniAudios, setProbniAudios,
      loadingSegmentTTS, setLoadingSegmentTTS,
      shorteningActive, setShorteningActive,
      savingProject, setSavingProject,
      rendering, setRendering,
      renderTaskId, setRenderTaskId,
      costs, setCosts,
      activeAudioSource, setActiveAudioSource,
      generatingAllTTS, setGeneratingAllTTS,
      dubbedBuster, setDubbedBuster,
      segmentEditorTab, setSegmentEditorTab,
      activeDubbedAudioUrl, setActiveDubbedAudioUrl,
      applyAudioToAll, setApplyAudioToAll,
      visualContextError, setVisualContextError,
      hoveredSegmentId, setHoveredSegmentId,
      shouldFocusTextarea, setShouldFocusTextarea,
      url, setUrl,
      videoRef,
      timelineRef,
      fileInputRef,
      consecutiveErrorsRef,
      playheadIntervalRef,
      dubbedAudioRef,
      bgAudioRef,
      fetchProjects,
      resetStudio,
      loadProjectData,
      handleSelectProject,
      handleCreateProject,
      handleDeleteProject,
      handleLoadUrl,
      handleSubmit,
      handleFileUpload,
      getVideoDuration,
      handleTimelineClick,
      handleSaveDraft,
      handleMagicShorten,
      handleTestSegmentTTS,
      handleGenerateAllTTS,
      handleRenderProject,
      handleFlushRedis
    }}>
      {children}
    </StudioContext.Provider>
  );
}

export function useStudio() {
  const context = useContext(StudioContext);
  if (!context) {
    throw new Error("useStudio mora biti korišćen unutar StudioProvider-a");
  }
  return context;
}

import { useEffect, useState, useRef } from 'react';
import { 
  Play, Pause, Loader2, CheckCircle2, Paperclip, ArrowRight, Video,
  FolderOpen, Plus, ChevronDown, Check, LayoutDashboard
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStudio } from './context/StudioContext';
import './index.css';

// Uvoz modularnih komponenti
import Header from './components/Common/Header';
import HardwareMonitor from './components/Common/HardwareMonitor';
import DashboardView from './components/Dashboard/DashboardView';
import StudioTimeline from './components/Studio/StudioTimeline';
import SegmentEditor from './components/Studio/SegmentEditor';
import AudioMixer from './components/Studio/AudioMixer';
import LoginRegister from './components/Auth/LoginRegister';
import LandingPage from './components/Landing/LandingPage';
import AdminPanel from './components/Admin/AdminPanel';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";

function App() {
  const [showLogin, setShowLogin] = useState(false);
  const {
    user,
    showProjectsList,
    isAdminMode,
    newProjectName, setNewProjectName,
    isCreateModalOpen, setIsCreateModalOpen,
    creatingProject,
    loading,
    status,
    progressData,
    videoUrl,
    error,
    elapsed,
    uploadProgress,
    uploadState,
    previewFile,
    project,
    selectedSegmentId, setSelectedSegmentId,
    selectedSegmentIds, setSelectedSegmentIds,
    historyStack, redoStack,
    saveToHistory, handleUndo, handleRedo,
    shouldFocusTextarea, setShouldFocusTextarea,
    currentTime, setCurrentTime,
    isPlaying, setIsPlaying,
    bgVolume, setBgVolume,
    dubVolume, setDubVolume,
    handleRenderProject,
    probniAudios,
    projects,
    handleSelectProject,
    costs,
    activeAudioSource, setActiveAudioSource,
    videoRef,
    fileInputRef,
    playheadIntervalRef,
    dubbedAudioRef,
    bgAudioRef,
    resetStudio,
    loadProjectData,
    handleCreateProject,
    handleLoadUrl,
    handleSubmit,
    handleFileUpload,
    getVideoDuration,
    handleSaveDraft
  } = useStudio();

  // Lokalna klijentska stanja za pretragu/unos URL-a
  const { url, setUrl } = useStudio();
  const [videoDuration, setVideoDuration] = useState(0);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const projectDropdownRef = useRef(null);

  // Zatvaranje dropdown-a za projekte klikom van njega
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(e.target)) {
        setProjectDropdownOpen(false);
      }
    };
    if (projectDropdownOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [projectDropdownOpen]);

  // Praćenje vremena video reprodukcije i sinhronizacija zvuka
  useEffect(() => {
    if (isPlaying && videoRef.current) {
      playheadIntervalRef.current = setInterval(() => {
        if (videoRef.current) {
          const t = videoRef.current.currentTime;
          setCurrentTime(t);

          // Realtime podešavanje jačine zvuka i brzine na osnovu aktivnog segmenta i delte na slajderu
          const currentSeg = project?.segments?.find(s => t >= s.start && t <= s.end);

          if (activeAudioSource === "dubbed" && dubbedAudioRef.current) {
            const baseVolumeLinear = Math.min(Math.max(Math.pow(10, dubVolume / 20), 0), 1);
            let finalVolume = baseVolumeLinear;
            let finalSpeed = 1.0;

            if (currentSeg) {
              // Delta volume
              const currentVol = currentSeg.volume !== undefined ? currentSeg.volume : 0.0;
              const lastGenVol = currentSeg.last_generated_volume !== undefined ? currentSeg.last_generated_volume : 0.0;
              const deltaVol = currentVol - lastGenVol;
              if (deltaVol !== 0) {
                const deltaVolLinear = Math.pow(10, deltaVol / 20);
                finalVolume = Math.min(Math.max(baseVolumeLinear * deltaVolLinear, 0), 1);
              }

              // Delta speed
              const currentSpeed = currentSeg.speed !== undefined ? currentSeg.speed : 1.0;
              const lastGenSpeed = currentSeg.last_generated_speed !== undefined ? currentSeg.last_generated_speed : 1.0;
              const deltaSpeed = currentSpeed / lastGenSpeed;
              if (deltaSpeed !== 1.0) {
                finalSpeed = deltaSpeed;
              }
            }

            if (dubbedAudioRef.current.volume !== finalVolume) {
              dubbedAudioRef.current.volume = finalVolume;
            }

            if (dubbedAudioRef.current.playbackRate !== finalSpeed) {
              dubbedAudioRef.current.playbackRate = finalSpeed;
            }

            // Realtime podešavanje jačine i brzine pozadinske muzike (bgAudioRef)
            if (bgAudioRef.current) {
              const segBgVolDb = currentSeg && currentSeg.bg_volume !== undefined ? currentSeg.bg_volume : 0.0;
              const combinedBgVolDb = bgVolume + segBgVolDb;
              const bgVolLinear = Math.min(Math.max(Math.pow(10, combinedBgVolDb / 20), 0), 1);
              if (bgAudioRef.current.volume !== bgVolLinear) {
                bgAudioRef.current.volume = bgVolLinear;
              }
              if (bgAudioRef.current.playbackRate !== finalSpeed) {
                bgAudioRef.current.playbackRate = finalSpeed;
              }
            }

            if (videoRef.current.playbackRate !== finalSpeed) {
              videoRef.current.playbackRate = finalSpeed;
            }

            // Resinhronizacija audia ako pobegne za više od 150ms
            const diff = Math.abs(videoRef.current.currentTime - dubbedAudioRef.current.currentTime);
            if (diff > 0.15) {
              dubbedAudioRef.current.currentTime = videoRef.current.currentTime;
            }

            // Resinhronizacija pozadinske muzike
            if (bgAudioRef.current) {
              const diffBg = Math.abs(videoRef.current.currentTime - bgAudioRef.current.currentTime);
              if (diffBg > 0.15) {
                bgAudioRef.current.currentTime = videoRef.current.currentTime;
              }
            }
          } else {
            // Ako nismo na dubbed izvoru, vratimo playbackRate videa na 1.0
            if (videoRef.current.playbackRate !== 1.0) {
              videoRef.current.playbackRate = 1.0;
            }
          }

          // Sinhronizuj selekciju segmenta u realnom vremenu
          if (currentSeg && currentSeg.id !== selectedSegmentId) {
            setSelectedSegmentId(currentSeg.id);
          }
        }
      }, 50);
    } else {
      clearInterval(playheadIntervalRef.current);
      if (videoRef.current && videoRef.current.playbackRate !== 1.0) {
        videoRef.current.playbackRate = 1.0;
      }
      if (dubbedAudioRef.current && dubbedAudioRef.current.playbackRate !== 1.0) {
        dubbedAudioRef.current.playbackRate = 1.0;
      }
      if (bgAudioRef.current && bgAudioRef.current.playbackRate !== 1.0) {
        bgAudioRef.current.playbackRate = 1.0;
      }
    }
    return () => clearInterval(playheadIntervalRef.current);
  }, [isPlaying, project, selectedSegmentId, activeAudioSource, dubVolume, bgVolume, setSelectedSegmentId, setCurrentTime, videoRef, dubbedAudioRef, bgAudioRef, playheadIntervalRef]);

  // Sinhronizacija mute stanja i reprodukcije u odnosu na selektovani izvor zvuka
  useEffect(() => {
    const video = videoRef.current;
    const audio = dubbedAudioRef.current;
    const bgAudio = bgAudioRef.current;
    if (!video) return;

    // Izvedena vrednost za putanju dubbed zvuka
    const dubbedFilename = project?.dubbed_audio_path ? project.dubbed_audio_path.split('/').pop() : null;
    const dubbedAudioUrl = project?.dubbed_audio_url || (dubbedFilename ? `${API_BASE_URL}/videos/${dubbedFilename}` : null);
    const noVocalsFilename = project?.no_vocals_path ? project.no_vocals_path.split('/').pop() : null;
    const noVocalsAudioUrl = project?.no_vocals_url || (noVocalsFilename ? `${API_BASE_URL}/videos/${noVocalsFilename}` : null);

    if (activeAudioSource === "dubbed" && dubbedAudioUrl) {
      video.muted = true;
      if (audio) {
        if (isPlaying) {
          audio.currentTime = video.currentTime;
          audio.play().catch(err => console.error("Greška pri reprodukciji srpskog tona:", err));
        } else {
          audio.pause();
        }
      }
      if (bgAudio && noVocalsAudioUrl) {
        if (isPlaying) {
          bgAudio.currentTime = video.currentTime;
          bgAudio.play().catch(err => console.error("Greška pri reprodukciji pozadinske muzike:", err));
        } else {
          bgAudio.pause();
        }
      }
    } else {
      video.muted = false;
      if (audio) audio.pause();
      if (bgAudio) bgAudio.pause();
    }
  }, [activeAudioSource, isPlaying, project, videoRef, dubbedAudioRef, bgAudioRef]);

  // Sinhronizacija jačine zvuka sinhronizovane trake (AI Glas) u realnom vremenu
  useEffect(() => {
    if (dubbedAudioRef.current) {
      const linearVol = Math.min(Math.max(Math.pow(10, dubVolume / 20), 0), 1);
      dubbedAudioRef.current.volume = linearVol;
    }
  }, [dubVolume, dubbedAudioRef]);

  // Sinhronizacija jačine zvuka pozadinske muzike i efekata u realnom vremenu
  useEffect(() => {
    if (bgAudioRef.current) {
      const t = videoRef.current ? videoRef.current.currentTime : 0;
      const currentSeg = project?.segments?.find(s => t >= s.start && t <= s.end);
      const segBgVolDb = currentSeg && currentSeg.bg_volume !== undefined ? currentSeg.bg_volume : 0.0;
      const combinedBgVolDb = bgVolume + segBgVolDb;
      const linearVol = Math.min(Math.max(Math.pow(10, combinedBgVolDb / 20), 0), 1);
      bgAudioRef.current.volume = linearVol;
    }
  }, [bgVolume, project, bgAudioRef, videoRef]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      if (dubbedAudioRef.current) {
        dubbedAudioRef.current.pause();
      }
      if (bgAudioRef.current) {
        bgAudioRef.current.pause();
      }
    } else {
      videoRef.current.play();
      if (activeAudioSource === "dubbed") {
        if (dubbedAudioRef.current) {
          dubbedAudioRef.current.currentTime = videoRef.current.currentTime;
          dubbedAudioRef.current.play().catch(err => console.error("Greška pri reprodukciji srpskog tona:", err));
        }
        if (bgAudioRef.current) {
          bgAudioRef.current.currentTime = videoRef.current.currentTime;
          bgAudioRef.current.play().catch(err => console.error("Greška pri reprodukciji pozadinske muzike:", err));
        }
      }
    }
    setIsPlaying(!isPlaying);
  };

  // Globalne prečice na tastaturi (Space, Tab, Shift+Tab, Ctrl+Z, Ctrl+Y, Esc)
  useEffect(() => {
    const handleKeyDown = (e) => {
      const active = document.activeElement;
      const isTextInput = active && (
        (active.tagName === 'INPUT' && !['range', 'checkbox', 'radio', 'button', 'submit', 'image', 'reset'].includes(active.type)) || 
        active.tagName === 'TEXTAREA' || 
        active.isContentEditable
      );

      // 1. SPACEBAR: Play/Pause reprodukcija
      if (e.code === 'Space') {
        if (isTextInput) return;
        e.preventDefault();
        if (active && typeof active.blur === 'function') {
          active.blur();
        }
        togglePlay();
        return;
      }

      // 2. ESCAPE: Blur iz inputa/textarea
      if (e.code === 'Escape') {
        if (active && typeof active.blur === 'function') {
          e.preventDefault();
          active.blur();
        }
        return;
      }

      // 3. CTRL + Z: Undo istorije
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        handleUndo();
        return;
      }

      // 4. CTRL + Y: Redo istorije
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        handleRedo();
        return;
      }

      // 5. TAB / SHIFT + TAB: Navigacija kroz segmente na vremenskoj liniji
      if (e.code === 'Tab') {
        if (!project || !project.segments || project.segments.length === 0) return;
        
        e.preventDefault();
        
        // Pronađi indeks trenutnog segmenta
        const currentIdx = project.segments.findIndex(s => s.id === selectedSegmentId);
        if (currentIdx === -1) return;

        let nextIdx;
        if (e.shiftKey) {
          // Shift + Tab ide unazad
          nextIdx = currentIdx - 1;
          if (nextIdx < 0) nextIdx = project.segments.length - 1;
        } else {
          // Tab ide unapred
          nextIdx = currentIdx + 1;
          if (nextIdx >= project.segments.length) nextIdx = 0;
        }

        const nextSeg = project.segments[nextIdx];
        
        // Postavi selekciju
        setSelectedSegmentId(nextSeg.id);
        
        // Premotaj video na početak novog segmenta
        if (videoRef.current) {
          videoRef.current.currentTime = nextSeg.start;
          if (activeAudioSource === "dubbed") {
            if (dubbedAudioRef.current) dubbedAudioRef.current.currentTime = nextSeg.start;
            if (bgAudioRef.current) bgAudioRef.current.currentTime = nextSeg.start;
          }
        }

        // Ako smo bili u tekstualnom polju, trigeruj automatski fokus na novo
        if (isTextInput) {
          setShouldFocusTextarea(true);
        }
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPlaying, project, selectedSegmentId, activeAudioSource, handleUndo, handleRedo, setSelectedSegmentId, setShouldFocusTextarea, videoRef, dubbedAudioRef, bgAudioRef]);

  const formatTime = (s) => {
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    const ms = Math.floor((s % 1) * 10);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`;
  };

  // Izvedene putanje za video i audio
  const dubbedFilename = project?.dubbed_audio_path ? project.dubbed_audio_path.split('/').pop() : null;
  const dubbedAudioUrl = project?.dubbed_audio_url || (dubbedFilename ? `${API_BASE_URL}/videos/${dubbedFilename}` : null);
  const noVocalsFilename = project?.no_vocals_path ? project.no_vocals_path.split('/').pop() : null;
  const noVocalsAudioUrl = project?.no_vocals_url || (noVocalsFilename ? `${API_BASE_URL}/videos/${noVocalsFilename}` : null);

  if (!user) {
    if (showLogin) {
      return <LoginRegister onBack={() => setShowLogin(false)} />;
    }
    return <LandingPage onEnterLogin={() => setShowLogin(true)} />;
  }

  const inStudioMode = project && !loading && !videoUrl;

  return (
    <>
      <div className="aurora-bg">
        <div className="aurora-blob aurora-blob-1"></div>
        <div className="aurora-blob aurora-blob-2"></div>
        <div className="aurora-blob aurora-blob-3"></div>
      </div>

      <div 
        className={`glass-container studio-layout ${inStudioMode ? 'studio-mode-active' : 'studio-mode-inactive'}`}
      >
        
        {/* GLOBALNI HEADER (NAVBAR) */}
        <Header />

        {/* GREŠKA */}
        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '12px', padding: '15px', color: '#f87171', fontSize: '0.9rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>⚠️ {error}</span>
          </div>
        )}

        <AnimatePresence mode="wait">
          {/* ADMIN PANEL */}
          {isAdminMode && user?.is_admin && (
            <motion.div
              key="admin-panel"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              style={{ width: '100%', height: '100%' }}
            >
              <AdminPanel />
            </motion.div>
          )}

          {/* DASHBOARD I UNOS VIDEA */}
          {!isAdminMode && !loading && !videoUrl && !project && (
            <DashboardView />
          )}

          {/* ASINHRONI PROGRES EKRAN (FAZA 1 ILI FAZA 2 RENDER) */}
          {!isAdminMode && loading && !videoUrl && !project && (
            <motion.div
              key="progress-screen"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="studio-interface"
            >
              <div className="studio-content" style={{ maxWidth: '600px', margin: '0 auto' }}>
                <div className="progress-section">
                  <div className="progress-header">
                    <span className="current-step-text" style={{ fontSize: '1.2rem', fontWeight: '700' }}>
                      {status.includes("RENDERING") ? "🎨 Rendering sinhronizacije (Faza 2)" : "🔍 Analiza videa (Faza 1)"}
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

                  <div style={{ marginTop: '20px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Proteklo vreme: {formatTime(elapsed)}</span>
                    <button 
                      onClick={resetStudio} 
                      className="back-btn" 
                      style={{ 
                        padding: '8px 16px', 
                        borderRadius: '8px', 
                        fontSize: '0.85rem', 
                        background: 'rgba(239, 68, 68, 0.1)', 
                        border: '1px solid rgba(239, 68, 68, 0.2)', 
                        color: '#f87171', 
                        cursor: 'pointer', 
                        transition: 'all 0.2s',
                        marginTop: '5px'
                      }}
                    >
                      Prekini i nazad na projekte
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* FAZA 1.5: INTERAKTIVNI STUDIO EDITOR (DRAFT MOD STATUS) */}
          {!isAdminMode && project && !loading && !videoUrl && (
            <motion.div
              key="studio-editor"
              initial={{ opacity: 0, scale: 0.99 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.99 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="studio-v2-container" 
              style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: '1 1 0%', overflow: 'hidden', height: '100%' }}
            >
              
              {/* STUDIO HEADER SA AKCIJAMA I DUGMETOM NAZAD */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.02)', padding: '8px 16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {/* Dropdown za projekte */}
                  <div ref={projectDropdownRef} style={{ position: 'relative' }}>
                    <button
                      onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
                      style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: '8px',
                        padding: '6px 12px',
                        color: '#fff',
                        fontFamily: 'Outfit',
                        fontWeight: '600',
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        transition: 'all 0.2s',
                        outline: 'none'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                        e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.3)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                      }}
                    >
                      <FolderOpen size={14} className="text-violet-400" />
                      <span style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {project ? project.name : "Bez naziva"}
                      </span>
                      <ChevronDown size={12} style={{ transform: projectDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                    </button>

                    <AnimatePresence>
                      {projectDropdownOpen && (
                        <motion.div
                          initial={{ opacity: 0, y: 8, scale: 0.96 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 8, scale: 0.96 }}
                          transition={{ duration: 0.15 }}
                          style={{
                            position: 'absolute',
                            top: 'calc(100% + 6px)',
                            left: 0,
                            width: '260px',
                            background: 'rgba(15, 23, 42, 0.95)',
                            backdropFilter: 'blur(16px)',
                            border: '1px solid rgba(255, 255, 255, 0.08)',
                            borderRadius: '12px',
                            padding: '6px',
                            boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.7), 0 0 20px rgba(139, 92, 246, 0.03)',
                            zIndex: 1000,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '2px'
                          }}
                        >
                          {/* STAVKA: DASHBOARD */}
                          <button
                            onClick={() => {
                              resetStudio();
                              setProjectDropdownOpen(false);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '10px',
                              width: '100%',
                              background: 'transparent',
                              border: 'none',
                              color: '#94a3b8',
                              padding: '8px 12px',
                              borderRadius: '8px',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                              fontWeight: '600',
                              textAlign: 'left',
                              transition: 'all 0.15s'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                              e.currentTarget.style.color = '#fff';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.color = '#94a3b8';
                            }}
                          >
                            <LayoutDashboard size={14} />
                            <span>Svi Projekti (Dashboard)</span>
                          </button>

                          <div style={{ height: '1px', background: 'rgba(255, 255, 255, 0.05)', margin: '4px 2px' }} />

                          {/* LISTA PROJEKATA */}
                          <div 
                            style={{ 
                              maxHeight: '200px', 
                              overflowY: 'auto',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '2px',
                              paddingRight: '2px'
                            }}
                          >
                            {projects && projects.length === 0 ? (
                              <div style={{ padding: '12px', textAlign: 'center', fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic' }}>
                                Nema kreiranih projekata
                              </div>
                            ) : (
                              projects && projects.map((proj) => {
                                const isActive = project && project.project_id === proj.id;
                                let statusColor = '#94a3b8';
                                if (proj.status === 'analyzing') statusColor = '#06b6d4';
                                else if (proj.status === 'ready') statusColor = '#8b5cf6';
                                else if (proj.status === 'completed') statusColor = '#10b981';

                                return (
                                  <button
                                    key={proj.id}
                                    onClick={() => {
                                      handleSelectProject(proj);
                                      setProjectDropdownOpen(false);
                                    }}
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '10px',
                                      width: '100%',
                                      background: isActive ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
                                      border: 'none',
                                      color: isActive ? '#c084fc' : '#cbd5e1',
                                      padding: '8px 12px',
                                      borderRadius: '8px',
                                      cursor: 'pointer',
                                      fontSize: '0.8rem',
                                      fontWeight: isActive ? '700' : '500',
                                      textAlign: 'left',
                                      transition: 'all 0.15s',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      whiteSpace: 'nowrap'
                                    }}
                                    onMouseEnter={(e) => {
                                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                                      e.currentTarget.style.color = '#fff';
                                    }}
                                    onMouseLeave={(e) => {
                                      e.currentTarget.style.background = isActive ? 'rgba(139, 92, 246, 0.1)' : 'transparent';
                                      e.currentTarget.style.color = isActive ? '#c084fc' : '#cbd5e1';
                                    }}
                                  >
                                    <div 
                                      style={{ 
                                        width: '6px', 
                                        height: '6px', 
                                        borderRadius: '50%', 
                                        background: statusColor,
                                        flexShrink: 0
                                      }} 
                                    />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                      {proj.name}
                                    </span>
                                    {isActive && <Check size={12} style={{ flexShrink: 0 }} />}
                                  </button>
                                );
                              })
                            )}
                          </div>

                          <div style={{ height: '1px', background: 'rgba(255, 255, 255, 0.05)', margin: '4px 2px' }} />

                          {/* KREIRAJ NOVI */}
                          <button
                            onClick={() => {
                              setIsCreateModalOpen(true);
                              setProjectDropdownOpen(false);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '10px',
                              width: '100%',
                              background: 'rgba(139, 92, 246, 0.1)',
                              border: '1px dashed rgba(139, 92, 246, 0.3)',
                              color: '#a78bfa',
                              padding: '8px 12px',
                              borderRadius: '8px',
                              cursor: 'pointer',
                              fontSize: '0.8rem',
                              fontWeight: '600',
                              textAlign: 'left',
                              transition: 'all 0.15s'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'rgba(139, 92, 246, 0.2)';
                              e.currentTarget.style.color = '#fff';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'rgba(139, 92, 246, 0.1)';
                              e.currentTarget.style.color = '#a78bfa';
                            }}
                          >
                            <Plus size={14} />
                            <span>Novi Projekat...</span>
                          </button>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                  
                  <span className="status-badge active" style={{ fontSize: '9px', padding: '2px 6px' }}>Studio</span>
                </div>
                
                {/* AKCIJE NA DESNOJ STRANI */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {/* Renderuj video dugme */}
                  <button 
                    onClick={handleRenderProject}
                    className="glow-button"
                    style={{ background: '#22c55e', fontSize: '0.75rem', padding: '6px 12px', borderRadius: '8px', boxShadow: '0 0 10px rgba(34, 197, 94, 0.2)' }}
                  >
                    Renderuj Video
                  </button>

                  <div style={{ width: '1px', height: '18px', background: 'rgba(255,255,255,0.1)', margin: '0 4px' }} />

                  {/* Nazad dugme */}
                  <button onClick={resetStudio} className="back-btn" style={{ padding: '6px 12px', borderRadius: '8px', fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer', transition: 'all 0.2s' }}>
                    Nazad
                  </button>
                </div>
              </div>
              
              {/* Gornji radni blok: Video i Forma */}
              <div className="studio-workspace">
                
                {/* Leva strana: Preview Player */}
                <div className="video-preview-card" style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px', height: '100%', overflow: 'hidden', minWidth: 0 }}>
                  <div className="video-frame" style={{ width: '100%', flex: '1 1 0%', minHeight: 0, background: '#000', borderRadius: '12px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                    <video 
                      ref={videoRef}
                      src={project.video_url || `${API_BASE_URL}/videos/${project.video_path.split('/').pop()}`}
                      className="w-full h-full"
                      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      onTimeUpdate={() => {
                        if (videoRef.current && !isPlaying) {
                          setCurrentTime(videoRef.current.currentTime);
                        }
                      }}
                      onDurationChange={(e) => setVideoDuration(e.target.duration)}
                    />
                    {dubbedAudioUrl && (
                      <audio 
                        ref={dubbedAudioRef} 
                        src={dubbedAudioUrl} 
                        style={{ display: 'none' }} 
                      />
                    )}
                    {noVocalsAudioUrl && (
                      <audio 
                        ref={bgAudioRef} 
                        src={noVocalsAudioUrl} 
                        style={{ display: 'none' }} 
                      />
                    )}
                  </div>
                  
                  {/* Kontrole plejera */}
                  <div className="video-player-controls" style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '2px 4px' }}>
                    <button 
                      onClick={togglePlay} 
                      className="play-pause-btn"
                      style={{ background: 'var(--primary)', color: '#fff', border: 'none', width: '38px', height: '38px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                    >
                      {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: '2px' }} />}
                    </button>
                    
                    <div className="time-display" style={{ fontFamily: 'monospace', fontSize: '0.9rem', color: '#94a3b8' }}>
                      {formatTime(currentTime)} / {formatTime(videoDuration || getVideoDuration())}
                    </div>

                    {/* Mikser jačine zvuka integrisan u plejer */}
                    <AudioMixer />
                  </div>
                </div>

                {/* Desna strana: Detaljan Editor Selektovanog Segmenta */}
                <SegmentEditor />
              </div>

              {/* TIMELINE (VREMENSKA LINIJA SA TRAKAMA) */}
              <StudioTimeline />



            </motion.div>
          )}

          {/* REZULTAT (ZAVRŠENO) */}
          {videoUrl && !loading && (
            <motion.div
              key="final-result"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="final-result"
            >
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
            </motion.div>
          )}
        </AnimatePresence>
      </div>


    </>
  );
}

export default App;

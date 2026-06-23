import { useEffect, useRef, useState } from 'react';
import { Film, Video, Mic, Volume2, Music } from 'lucide-react';
import WaveSurfer from 'wavesurfer.js';
import { useStudio } from '../../context/StudioContext';

export default function StudioTimeline() {
  const {
    project,
    setProject,
    timelineRef,
    handleTimelineClick,
    getVideoDuration,
    currentTime,
    visualContextError,
    setVisualContextError,
    activeAudioSource,
    setActiveAudioSource,
    selectedSegmentId,
    setSelectedSegmentId,
    selectedSegmentIds,
    setSelectedSegmentIds,
    videoRef,
    dubbedAudioRef,
    bgAudioRef,
    hoveredSegmentId,
    setHoveredSegmentId,
    dubbedBuster,
    saveToHistory,
    handleSaveDraft,
    probniAudios
  } = useStudio();

  // Reference za wavesurfer.js
  const musicWaveformRef = useRef(null);
  const musicWavesurfer = useRef(null);
  const dubbedWaveformRef = useRef(null);
  const dubbedWavesurfer = useRef(null);

  // Informacije o prevlačenju (drag-and-drop)
  const dragInfoRef = useRef(null);

  // Optimizacija seek/scrubbing-a
  const [localCurrentTime, setLocalCurrentTime] = useState(currentTime);
  const isScrubbingRef = useRef(false);
  const selectedSegmentIdRef = useRef(selectedSegmentId);

  // Zoom vremenske linije
  const [zoomWidth, setZoomWidth] = useState(1000); // Početna širina u pikselima (ekvivalent 100% u DAW modu)
  const containerRef = useRef(null);

  // Praćenje stanja drag-skrolovanja za promenu kursora
  const [isGrabbing, setIsGrabbing] = useState(false);

  useEffect(() => {
    if (isGrabbing) {
      document.body.style.cursor = 'grabbing';
    } else {
      document.body.style.cursor = '';
    }
    return () => {
      document.body.style.cursor = '';
    };
  }, [isGrabbing]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e) => {
      if (e.ctrlKey) {
        e.preventDefault(); // Sprečava zumiranje pretraživača
        
        const currentClientWidth = container.clientWidth;
        let baseWidth = zoomWidth;
        if (zoomWidth < currentClientWidth) {
          baseWidth = currentClientWidth;
        }

        const zoomFactor = 1.1;
        let newWidth;
        if (e.deltaY < 0) {
          // Zoom In
          newWidth = Math.min(baseWidth * zoomFactor, 6000);
        } else {
          // Zoom Out
          newWidth = Math.max(baseWidth / zoomFactor, 800);
        }
        
        setZoomWidth(Math.round(newWidth));
      } else {
        // Običan scroll točkićem miša prevodimo u horizontalno skrolovanje
        e.preventDefault();
        container.scrollLeft += e.deltaY;
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, [zoomWidth]);

  useEffect(() => {
    selectedSegmentIdRef.current = selectedSegmentId;
  }, [selectedSegmentId]);

  useEffect(() => {
    if (!isScrubbingRef.current) {
      setLocalCurrentTime(currentTime);
    }
  }, [currentTime]);

  // Izvedene vrednosti za putanje zvuka
  const dubbedFilename = project?.dubbed_audio_path ? project.dubbed_audio_path.split('/').pop() : null;
  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://12.34.56.78:8000";
  const dubbedAudioUrl = project?.dubbed_audio_url || (dubbedFilename ? `${API_BASE_URL}/videos/${dubbedFilename}?cb=${dubbedBuster}` : null);

  const noVocalsFilename = project?.no_vocals_path ? project.no_vocals_path.split('/').pop() : null;
  const noVocalsAudioUrl = project?.no_vocals_url || (noVocalsFilename ? `${API_BASE_URL}/videos/${noVocalsFilename}` : null);

  // 1. Wavesurfer za pozadinsku muziku
  useEffect(() => {
    if (!musicWaveformRef.current || !noVocalsAudioUrl) return;

    try {
      musicWavesurfer.current = WaveSurfer.create({
        container: musicWaveformRef.current,
        waveColor: 'rgba(203, 213, 225, 0.1)',
        progressColor: 'rgba(139, 92, 246, 0.15)',
        cursorColor: 'transparent',
        height: 38,
        responsive: true,
        interact: false,
      });

      musicWavesurfer.current.load(noVocalsAudioUrl).catch(err => {
        if (err.name !== 'AbortError') {
          console.error("Greška pri učitavanju wavesurfer muzike:", err);
        }
      });
    } catch (err) {
      console.error("Greška pri inicijalizaciji Wavesurfer-a za muziku:", err);
    }

    return () => {
      if (musicWavesurfer.current) {
        try {
          musicWavesurfer.current.destroy();
        } catch (_) {
          // ignore
        }
      }
    };
  }, [noVocalsAudioUrl]);

  // 2. Wavesurfer za srpski sinhronizovani glas (kada je izgenerisan)
  useEffect(() => {
    if (!dubbedWaveformRef.current || !dubbedAudioUrl) return;

    try {
      if (dubbedWavesurfer.current) {
        dubbedWavesurfer.current.destroy();
      }

      dubbedWavesurfer.current = WaveSurfer.create({
        container: dubbedWaveformRef.current,
        waveColor: 'rgba(34, 197, 94, 0.08)',
        progressColor: 'rgba(34, 197, 94, 0.18)',
        cursorColor: 'transparent',
        height: 52,
        responsive: true,
        interact: false,
      });

      dubbedWavesurfer.current.load(dubbedAudioUrl).catch(err => {
        if (err.name !== 'AbortError') {
          console.error("Greška pri učitavanju wavesurfer srpskog glasa:", err);
        }
      });
    } catch (err) {
      console.error("Greška pri inicijalizaciji Wavesurfer-a za srpski glas:", err);
    }

    return () => {
      if (dubbedWavesurfer.current) {
        try {
          dubbedWavesurfer.current.destroy();
        } catch (_) {
          // ignore
        }
      }
    };
  }, [dubbedAudioUrl]);

  // Sinhronizacija wavesurfer-a sa vremenom reprodukcije
  useEffect(() => {
    if (musicWavesurfer.current && typeof musicWavesurfer.current.setTime === 'function') {
      try {
        musicWavesurfer.current.setTime(localCurrentTime);
      } catch (_) {
        // ignore
      }
    }
    if (dubbedWavesurfer.current && typeof dubbedWavesurfer.current.setTime === 'function') {
      try {
        dubbedWavesurfer.current.setTime(localCurrentTime);
      } catch (_) {
        // ignore
      }
    }
  }, [localCurrentTime]);

  // Reaktivno ponovno iscrtavanje wavesurfer-a pri promeni zumiranja (zoomWidth) u realnom vremenu
  useEffect(() => {
    if (musicWavesurfer.current) {
      try {
        musicWavesurfer.current.redraw();
      } catch (_) {
        // Ignorišemo greške pri brzom ponovnom iscrtavanju talasa
      }
    }
    if (dubbedWavesurfer.current) {
      try {
        dubbedWavesurfer.current.redraw();
      } catch (_) {
        // Ignorišemo greške pri brzom ponovnom iscrtavanju talasa
      }
    }
  }, [zoomWidth]);

  // Pomoćna funkcija za iscrtavanje lažnog waveform barova (fallback ako nema wavesurfer-a)
  const generateWaveformBars = (duration, id) => {
    const numBars = Math.max(Math.floor(duration * 6), 5);
    const bars = [];
    let seed = id * 5.7;
    for (let i = 0; i < numBars; i++) {
      seed = (seed * 9301 + 49297) % 233280;
      const height = 15 + (seed / 233280.0) * 35; 
      bars.push(height);
    }
    return bars;
  };

  const handleStartDragScroll = (e) => {
    e.stopPropagation();
    e.preventDefault();
    const container = containerRef.current;
    if (!container) return;

    const startX = e.clientX;
    const startScrollLeft = container.scrollLeft;

    setIsGrabbing(true);

    const handleMouseMove = (moveEvent) => {
      const deltaX = moveEvent.clientX - startX;
      container.scrollLeft = startScrollLeft - deltaX;
    };

    const handleMouseUp = () => {
      setIsGrabbing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  // DRAG AND DROP I RESIZE LOGIKA
  const handleStartResizeLeft = (e, seg) => {
    if (e.shiftKey) {
      handleStartDragScroll(e);
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    if (!timelineRef.current) return;
    saveToHistory(project.segments); // Sačuvaj pre početka pomeranja

    const rect = timelineRef.current.getBoundingClientRect();
    dragInfoRef.current = {
      type: 'resize-start',
      segId: seg.id,
      startX: e.clientX,
      startVal: seg.start,
      endVal: seg.end,
      timelineWidth: rect.width,
      videoDuration: getVideoDuration()
    };
    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', handleGlobalMouseUp);
  };

  const handleStartResizeRight = (e, seg) => {
    if (e.shiftKey) {
      handleStartDragScroll(e);
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    if (!timelineRef.current) return;
    saveToHistory(project.segments); // Sačuvaj pre početka pomeranja

    const rect = timelineRef.current.getBoundingClientRect();
    dragInfoRef.current = {
      type: 'resize-end',
      segId: seg.id,
      startX: e.clientX,
      startVal: seg.start,
      endVal: seg.end,
      timelineWidth: rect.width,
      videoDuration: getVideoDuration()
    };
    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', handleGlobalMouseUp);
  };

  const handleStartDragMove = (e, seg) => {
    if (e.shiftKey) {
      handleStartDragScroll(e);
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    if (!timelineRef.current) return;
    saveToHistory(project.segments); // Sačuvaj pre početka pomeranja

    const rect = timelineRef.current.getBoundingClientRect();
    dragInfoRef.current = {
      type: 'move',
      segId: seg.id,
      startX: e.clientX,
      startVal: seg.start,
      endVal: seg.end,
      timelineWidth: rect.width,
      videoDuration: getVideoDuration()
    };
    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', handleGlobalMouseUp);
  };

  const handleGlobalMouseMove = (e) => {
    if (!dragInfoRef.current) return;
    const info = dragInfoRef.current;
    const deltaX = e.clientX - info.startX;
    const deltaSeconds = (deltaX / info.timelineWidth) * info.videoDuration;

    let newStart = info.startVal;
    let newEnd = info.endVal;

    if (info.type === 'move') {
      const length = info.endVal - info.startVal;
      newStart = Math.max(0, info.startVal + deltaSeconds);
      newEnd = newStart + length;
      
      const maxDur = info.videoDuration;
      if (newEnd > maxDur) {
        newEnd = maxDur;
        newStart = Math.max(0, maxDur - length);
      }
    } else if (info.type === 'resize-start') {
      newStart = Math.max(0, Math.min(info.startVal + deltaSeconds, info.endVal - 0.2));
    } else if (info.type === 'resize-end') {
      newEnd = Math.max(info.startVal + 0.2, Math.min(info.endVal + deltaSeconds, info.videoDuration));
    }

    setProject(prevProj => {
      if (!prevProj) return prevProj;
      const updated = prevProj.segments.map(s => {
        if (s.id === info.segId) {
          return { 
            ...s, 
            start: parseFloat(newStart.toFixed(2)), 
            end: parseFloat(newEnd.toFixed(2)),
            status: 'edited'
          };
        }
        return s;
      });
      return { ...prevProj, segments: updated };
    });
  };

  const handleGlobalMouseUp = () => {
    if (!dragInfoRef.current) return;
    handleSaveDraft();
    dragInfoRef.current = null;
    document.removeEventListener('mousemove', handleGlobalMouseMove);
    document.removeEventListener('mouseup', handleGlobalMouseUp);
  };

  const handleStartTtsResizeLeft = (e, seg) => {
    if (e.shiftKey) {
      handleStartDragScroll(e);
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    if (!timelineRef.current) return;
    saveToHistory(project.segments); // Sačuvaj pre početka

    const rect = timelineRef.current.getBoundingClientRect();
    const baseTtsDuration = seg.tts_duration || (seg.end - seg.start);
    const lastGenSpeed = seg.last_generated_speed || 1.0;
    const startSpeed = seg.speed || 1.0;
    const startEstimatedTtsDuration = baseTtsDuration * (lastGenSpeed / startSpeed);

    dragInfoRef.current = {
      type: 'tts-resize-start',
      segId: seg.id,
      startX: e.clientX,
      baseTtsDuration,
      lastGenSpeed,
      startEstimatedTtsDuration,
      timelineWidth: rect.width,
      videoDuration: getVideoDuration()
    };
    document.addEventListener('mousemove', handleGlobalTtsMouseMove);
    document.addEventListener('mouseup', handleGlobalTtsMouseUp);
  };

  const handleStartTtsResizeRight = (e, seg) => {
    if (e.shiftKey) {
      handleStartDragScroll(e);
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    if (!timelineRef.current) return;
    saveToHistory(project.segments); // Sačuvaj pre početka

    const rect = timelineRef.current.getBoundingClientRect();
    const baseTtsDuration = seg.tts_duration || (seg.end - seg.start);
    const lastGenSpeed = seg.last_generated_speed || 1.0;
    const startSpeed = seg.speed || 1.0;
    const startEstimatedTtsDuration = baseTtsDuration * (lastGenSpeed / startSpeed);

    dragInfoRef.current = {
      type: 'tts-resize-end',
      segId: seg.id,
      startX: e.clientX,
      baseTtsDuration,
      lastGenSpeed,
      startEstimatedTtsDuration,
      timelineWidth: rect.width,
      videoDuration: getVideoDuration()
    };
    document.addEventListener('mousemove', handleGlobalTtsMouseMove);
    document.addEventListener('mouseup', handleGlobalTtsMouseUp);
  };

  const handleGlobalTtsMouseMove = (e) => {
    if (!dragInfoRef.current) return;
    const info = dragInfoRef.current;
    const deltaX = e.clientX - info.startX;
    const deltaSeconds = (deltaX / info.timelineWidth) * info.videoDuration;

    let newEstimatedTtsDuration = info.startEstimatedTtsDuration;

    if (info.type === 'tts-resize-start') {
      newEstimatedTtsDuration = Math.max(0.2, info.startEstimatedTtsDuration - deltaSeconds);
    } else if (info.type === 'tts-resize-end') {
      newEstimatedTtsDuration = Math.max(0.2, info.startEstimatedTtsDuration + deltaSeconds);
    }

    // Izračunavamo novu brzinu
    let newSpeed = (info.baseTtsDuration * info.lastGenSpeed) / newEstimatedTtsDuration;
    
    // Ograničavamo brzinu na opseg [0.5, 2.0]
    newSpeed = Math.max(0.5, Math.min(2.0, newSpeed));

    setProject(prevProj => {
      if (!prevProj) return prevProj;
      const updated = prevProj.segments.map(s => {
        if (s.id === info.segId) {
          return { 
            ...s, 
            speed: parseFloat(newSpeed.toFixed(2)),
            status: 'edited'
          };
        }
        return s;
      });
      return { ...prevProj, segments: updated };
    });
  };

  const handleGlobalTtsMouseUp = () => {
    if (!dragInfoRef.current) return;
    handleSaveDraft();
    dragInfoRef.current = null;
    document.removeEventListener('mousemove', handleGlobalTtsMouseMove);
    document.removeEventListener('mouseup', handleGlobalTtsMouseUp);
  };

  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleGlobalMouseMove);
      document.removeEventListener('mouseup', handleGlobalMouseUp);
      document.removeEventListener('mousemove', handleGlobalTtsMouseMove);
      document.removeEventListener('mouseup', handleGlobalTtsMouseUp);
    };
  }, []);

  const handleStartScrubbing = (e) => {
    if (e.shiftKey) {
      handleStartDragScroll(e);
      return;
    }
    e.stopPropagation();
    e.preventDefault();
    if (!timelineRef.current || !videoRef.current) return;

    isScrubbingRef.current = true;
    let pendingTime = null;
    let rafId = null;

    const performSeek = () => {
      if (pendingTime === null) return;
      
      const targetTime = pendingTime;
      pendingTime = null;

      if (videoRef.current) {
        videoRef.current.currentTime = targetTime;
      }
      
      if (activeAudioSource === "dubbed") {
        if (dubbedAudioRef.current) dubbedAudioRef.current.currentTime = targetTime;
        if (bgAudioRef.current) bgAudioRef.current.currentTime = targetTime;
      }
      
      if (project.segments) {
        const matchingSeg = project.segments.find(s => targetTime >= s.start && targetTime <= s.end);
        if (matchingSeg && matchingSeg.id !== selectedSegmentIdRef.current) {
          setSelectedSegmentId(matchingSeg.id);
          setSelectedSegmentIds([matchingSeg.id]);
        }
      }
    };

    const scheduleSeek = (clientX) => {
      const rect = timelineRef.current.getBoundingClientRect();
      const clickX = clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, clickX / rect.width));
      const targetTime = percentage * getVideoDuration();

      pendingTime = targetTime;
      setLocalCurrentTime(targetTime); // Instantni vizuelni update (60fps kursor i talas)

      if (!rafId) {
        rafId = requestAnimationFrame(() => {
          rafId = null;
          performSeek();
        });
      }
    };

    scheduleSeek(e.clientX);

    const handleMouseMove = (moveEvent) => {
      scheduleSeek(moveEvent.clientX);
    };

    const handleMouseUp = () => {
      isScrubbingRef.current = false;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
      performSeek();
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  if (!project) return null;

  return (
    <div 
      ref={containerRef}
      className="timeline-card" 
      style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '12px 16px', overflowX: 'auto', overflowY: 'hidden', flexShrink: 0 }}
    >
      <div className="timeline-header-row">
        <h4 style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px', margin: 0 }}>
          <Film size={14} /> Vremenski Editor (Timeline)
        </h4>
        
        {/* Izbor aktivnog audio izvora (Original vs Dub) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '500' }}>Aktivni zvuk:</span>
          
          <button 
            onClick={(e) => { e.stopPropagation(); setActiveAudioSource("original"); }}
            style={{ 
              background: activeAudioSource === "original" ? 'rgba(139, 92, 246, 0.8)' : 'rgba(255,255,255,0.05)', 
              border: activeAudioSource === "original" ? '1px solid #8b5cf6' : '1px solid rgba(255,255,255,0.1)', 
              borderRadius: '6px', 
              color: '#fff', 
              fontSize: '0.7rem', 
              padding: '4px 10px', 
              cursor: 'pointer',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              outline: 'none',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: activeAudioSource === "original" ? '#a78bfa' : 'transparent', border: '1px solid rgba(255,255,255,0.4)' }} />
            <Mic size={12} /> Originalni ENG Vokal
          </button>

          <button 
            onClick={(e) => { e.stopPropagation(); setActiveAudioSource("dubbed"); }}
            style={{ 
              background: activeAudioSource === "dubbed" ? 'rgba(34, 197, 94, 0.8)' : 'rgba(255,255,255,0.05)', 
              border: activeAudioSource === "dubbed" ? '1px solid #22c55e' : '1px solid rgba(255,255,255,0.1)', 
              borderRadius: '6px', 
              color: '#fff', 
              fontSize: '0.7rem', 
              padding: '4px 10px', 
              cursor: 'pointer',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              outline: 'none',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: activeAudioSource === "dubbed" ? '#4ade80' : 'transparent', border: '1px solid rgba(255,255,255,0.4)' }} />
            <Volume2 size={12} /> Srpski glas (TTS)
          </button>
        </div>
      </div>

      {/* Vremenska skala i kontejner traka */}
      <div 
        ref={timelineRef}
        onMouseDown={handleStartScrubbing}
        style={{ minWidth: `${zoomWidth}px`, position: 'relative', cursor: 'ew-resize', display: 'flex', flexDirection: 'column', gap: '4px', userSelect: 'none' }}
      >
        {/* 1. Skala sekundi */}
        <div style={{ height: '24px', position: 'relative', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#475569', fontSize: '0.75rem' }}>
          {(() => {
            const dur = getVideoDuration();
            const ticks = [];
            const step = dur > 60 ? 10 : 5; 
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

        {/* 2. TRAKA: VIDEO SLIČICE (Keyframes) */}
        <div style={{ height: '36px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.03)', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center' }}>
          <div style={{ position: 'absolute', left: '10px', fontSize: '0.7rem', color: '#475569', zIndex: 5, pointerEvents: 'none', textTransform: 'uppercase', fontWeight: 'bold' }}>
            <Video size={10} style={{ display: 'inline', marginRight: '4px' }} /> Video Sličice
          </div>
          {project.visual_context_url && !visualContextError && (
            <img 
              src={project.visual_context_url} 
              onError={() => setVisualContextError(true)}
              style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.25, pointerEvents: 'none' }} 
              alt="Visual keyframes timeline"
            />
          )}
        </div>

        {/* 3. TRAKA: ORIGINALNI GOVOR (Engleski) */}
        <div style={{ height: '54px', background: 'rgba(139, 92, 246, 0.03)', borderRadius: '6px', border: '1px solid rgba(139, 92, 246, 0.08)', position: 'relative' }}>
          <div style={{ position: 'absolute', left: '10px', top: '5px', zIndex: 5, fontSize: '0.65rem', color: activeAudioSource === "original" ? '#c084fc' : '#475569', fontWeight: 'bold', textTransform: 'uppercase', pointerEvents: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Mic size={10} /> Originalni ENG Vokal
          </div>
          
          {/* Renderujemo regione segmenata */}
          {project.segments && project.segments.map(seg => {
            const dur = getVideoDuration();
            const left = (seg.start / dur) * 100;
            const width = ((seg.end - seg.start) / dur) * 100;
            const isTrackActive = activeAudioSource === "original";
            const isActive = isTrackActive && selectedSegmentIds.includes(seg.id);
            
            return (
              <div 
                key={seg.id}
                onClick={(e) => {
                  e.stopPropagation();
                  if (e.ctrlKey || e.metaKey) {
                    setSelectedSegmentIds(prev => {
                      if (prev.includes(seg.id)) {
                        const next = prev.filter(id => id !== seg.id);
                        if (next.length === 0) return [seg.id];
                        return next;
                      } else {
                        return [...prev, seg.id];
                      }
                    });
                    setSelectedSegmentId(seg.id, true);
                  } else {
                    setSelectedSegmentId(seg.id);
                    setSelectedSegmentIds([seg.id]);
                  }
                  
                  if (videoRef.current) {
                    videoRef.current.currentTime = seg.start;
                    if (activeAudioSource === "dubbed") {
                      if (dubbedAudioRef.current) dubbedAudioRef.current.currentTime = seg.start;
                      if (bgAudioRef.current) bgAudioRef.current.currentTime = seg.start;
                    }
                  }
                }}
                style={{
                  position: 'absolute',
                  left: `${left}%`,
                  width: `${width}%`,
                  height: '36px',
                  bottom: '4px',
                  background: isActive 
                    ? 'rgba(139, 92, 246, 0.25)' 
                    : (isTrackActive ? 'rgba(139, 92, 246, 0.04)' : 'rgba(255, 255, 255, 0.02)'),
                  border: isActive 
                    ? '2px solid #8b5cf6' 
                    : (isTrackActive ? '1px solid rgba(139, 92, 246, 0.12)' : '1px solid rgba(255, 255, 255, 0.05)'),
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                  transition: 'background-color 0.15s, border-color 0.15s'
                }}
              >
                {/* Drag-and-drop i resize kontrole za ivice */}
                <div 
                  onMouseDown={(e) => handleStartResizeLeft(e, seg)}
                  data-testid={`resize-left-${seg.id}`}
                  style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '6px', cursor: 'ew-resize', zIndex: 30 }}
                />
                <div 
                  onMouseDown={(e) => handleStartDragMove(e, seg)}
                  data-testid={`drag-move-${seg.id}`}
                  style={{ position: 'absolute', left: '6px', right: '6px', top: 0, bottom: 0, cursor: 'move', zIndex: 10 }}
                />
                <div 
                  onMouseDown={(e) => handleStartResizeRight(e, seg)}
                  data-testid={`resize-right-${seg.id}`}
                  style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: '6px', cursor: 'ew-resize', zIndex: 30 }}
                />

                {/* Custom Waveform u pozadini */}
                <div style={{ position: 'absolute', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 4px', opacity: isActive ? 0.45 : (isTrackActive ? 0.15 : 0.08), pointerEvents: 'none' }}>
                  {generateWaveformBars(seg.end - seg.start, seg.id).map((h, i) => (
                    <div key={i} style={{ width: '2px', height: `${h}%`, background: isTrackActive ? '#8b5cf6' : '#64748b', borderRadius: '1px' }} />
                  ))}
                </div>
                <span style={{ fontSize: '0.65rem', color: isTrackActive ? '#c084fc' : '#64748b', fontWeight: 'bold', zIndex: 20, pointerEvents: 'none' }}>
                  #{seg.id}
                </span>
              </div>
            );
          })}
        </div>

        {/* 4. TRAKA: SRPSKI SINHRONIZOVANI GLAS */}
        <div style={{ height: '54px', background: 'rgba(34, 197, 94, 0.02)', borderRadius: '6px', border: '1px solid rgba(34, 197, 94, 0.08)', position: 'relative' }}>
          {/* Wavesurfer stvarni talasni oblik u pozadini cele trake */}
          {dubbedAudioUrl && (
            <div 
              ref={dubbedWaveformRef} 
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1 }} 
            />
          )}

          <div style={{ position: 'absolute', left: '10px', top: '5px', zIndex: 5, fontSize: '0.65rem', color: activeAudioSource === "dubbed" ? '#86efac' : '#475569', fontWeight: 'bold', textTransform: 'uppercase', pointerEvents: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Volume2 size={10} /> Srpski glas (TTS)
          </div>
          
          {project.segments && project.segments.map(seg => {
            const isTtsGenerated = (seg.tts_path || probniAudios[seg.id]) && seg.status !== "edited" && seg.status !== "draft";
            if (!isTtsGenerated) return null;

            const dur = getVideoDuration();
            const left = (seg.start / dur) * 100;
            const origWidth = ((seg.end - seg.start) / dur) * 100;
            
            // Dinamičko pozicioniranje da se spreči odsecanje na ivicama ekrana
            let tooltipStyle = {
              left: '50%',
              right: 'auto',
              transform: 'translateX(-50%) translateY(-10px)'
            };
            let arrowStyle = {
              left: '50%',
              right: 'auto',
              transform: 'translateX(-50%)'
            };

            if (left < 15) {
              // Blizu leve ivice - poravnaj sa levom ivicom segmenta
              tooltipStyle = {
                left: '0px',
                right: 'auto',
                transform: 'translateY(-10px)'
              };
              arrowStyle = {
                left: '15px',
                right: 'auto',
                transform: 'none'
              };
            } else if (left > 85) {
              // Blizu desne ivice - poravnaj sa desnom ivicom segmenta
              tooltipStyle = {
                left: 'auto',
                right: '0px',
                transform: 'translateY(-10px)'
              };
              arrowStyle = {
                left: 'auto',
                right: '15px',
                transform: 'none'
              };
            }
            
            // Dinamički proračun procenjene dužine na osnovu brzine (tempa)
            const baseTtsDuration = seg.tts_duration || (seg.end - seg.start);
            const speedRatio = seg.last_generated_speed ? (seg.last_generated_speed / seg.speed) : (1.0 / seg.speed);
            const estimatedTtsDuration = baseTtsDuration * speedRatio;
            
            const ttsWidth = (estimatedTtsDuration / dur) * 100;
            const isLonger = estimatedTtsDuration > (seg.end - seg.start);
            
            // Detekcija kolizije samo sa sledećim vidljivim segmentom koji ima generisan glas
            const nextSeg = project.segments
              .filter(s => s.start >= seg.end && (s.tts_path || probniAudios[s.id]) && s.status !== "edited" && s.status !== "draft")
              .sort((a, b) => a.start - b.start)[0];
            const hasCollision = nextSeg && (seg.start + estimatedTtsDuration > nextSeg.start);
            const isTrackActive = activeAudioSource === "dubbed";
            const isActive = isTrackActive && selectedSegmentIds.includes(seg.id);
            const isHovered = hoveredSegmentId === seg.id;

            return (
              <div 
                key={seg.id}
                data-testid={`dubbed-segment-${seg.id}`}
                onMouseEnter={() => setHoveredSegmentId(seg.id)}
                onMouseLeave={() => setHoveredSegmentId(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  if (e.ctrlKey || e.metaKey) {
                    setSelectedSegmentIds(prev => {
                      if (prev.includes(seg.id)) {
                        const next = prev.filter(id => id !== seg.id);
                        if (next.length === 0) return [seg.id];
                        return next;
                      } else {
                        return [...prev, seg.id];
                      }
                    });
                    setSelectedSegmentId(seg.id, true);
                  } else {
                    setSelectedSegmentId(seg.id);
                    setSelectedSegmentIds([seg.id]);
                  }
                  if (videoRef.current) videoRef.current.currentTime = seg.start;
                }}
                style={{
                  position: 'absolute',
                  left: `${left}%`,
                  width: `${ttsWidth}%`,
                  height: '36px',
                  bottom: '4px',
                  background: isActive ? 'rgba(34, 197, 94, 0.25)' : (isTrackActive ? 'rgba(34, 197, 94, 0.08)' : 'rgba(255, 255, 255, 0.02)'),
                  border: isActive ? '2px solid #22c55e' : (isTrackActive ? '1px solid rgba(34, 197, 94, 0.2)' : '1px solid rgba(255, 255, 255, 0.05)'),
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  paddingLeft: '6px',
                  zIndex: isHovered ? 50 : 2,
                  transition: 'background-color 0.15s, border-color 0.15s',
                  overflow: 'hidden'
                }}
              >
                <div onMouseDown={(e) => handleStartTtsResizeLeft(e, seg)} data-testid={`tts-resize-left-${seg.id}`} style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '6px', cursor: 'ew-resize', zIndex: 30, background: isHovered ? 'rgba(34, 197, 94, 0.3)' : 'transparent', borderRadius: '4px 0 0 4px', transition: 'background-color 0.15s' }} />
                <div onMouseDown={(e) => handleStartTtsResizeRight(e, seg)} data-testid={`tts-resize-right-${seg.id}`} style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: '6px', cursor: 'ew-resize', zIndex: 30, background: isHovered ? 'rgba(34, 197, 94, 0.3)' : 'transparent', borderRadius: '0 4px 4px 0', transition: 'background-color 0.15s' }} />
                <div style={{ position: 'absolute', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 8px', opacity: isActive ? 0.45 : (isTrackActive ? 0.15 : 0.08), pointerEvents: 'none' }}>
                  {generateWaveformBars(estimatedTtsDuration, seg.id).map((h, i) => (
                    <div key={i} style={{ width: '2px', height: `${h}%`, background: isTrackActive ? '#22c55e' : '#64748b', borderRadius: '1px' }} />
                  ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', padding: '0 8px', zIndex: 20, pointerEvents: 'none', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.65rem', color: isTrackActive ? '#86efac' : '#64748b', fontWeight: 'bold' }}>#{seg.id}</span>
                  {seg.speed && seg.speed !== 1.0 && (
                    <span style={{ fontSize: '0.65rem', background: 'rgba(15, 23, 42, 0.75)', padding: '1px 4px', borderRadius: '3px', color: seg.speed > 1.0 ? '#86efac' : '#f87171', fontWeight: 'bold', border: '1px solid rgba(255, 255, 255, 0.1)' }}>{seg.speed.toFixed(2)}x</span>
                  )}
                </div>
                {(isHovered || isActive) && (isLonger || hasCollision) && (
                  <div style={{ position: 'absolute', ...tooltipStyle, background: 'rgba(15, 23, 42, 0.95)', padding: '8px 12px', borderRadius: '6px', border: '1px solid #475569', zIndex: 100, width: '280px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.5)' }}>
                    <div style={{ position: 'absolute', top: '100%', ...arrowStyle, width: '0', height: '0', borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderTop: '6px solid rgba(15, 23, 42, 0.95)' }} />
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <span style={{ fontSize: '1.1rem', marginTop: '-2px' }}>⚠️</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', textAlign: 'left', whiteSpace: 'normal' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#f87171' }}>{hasCollision ? "Kolizija tajminga!" : "Predugačak srpski izgovor!"}</span>
                        <span style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>{hasCollision ? "Audio segment se preklapa sa sledećim. Skratite audio ili promenite tajming." : "Trajanje izgovora je duže od trajanje originalnog video segmenta."}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 5. TRAKA: MUZIKA I EFEKTI */}
        <div style={{ height: '40px', background: 'rgba(241, 245, 249, 0.03)', borderRadius: '6px', border: '1px solid rgba(241, 245, 249, 0.08)', position: 'relative' }}>
          {noVocalsAudioUrl && (
            <div 
              ref={musicWaveformRef} 
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1 }} 
            />
          )}

          <div style={{ position: 'absolute', left: '10px', top: '4px', fontSize: '0.7rem', color: '#475569', zIndex: 5, pointerEvents: 'none', textTransform: 'uppercase', fontWeight: 'bold' }}>
            <Music size={10} style={{ display: 'inline', marginRight: '4px' }} /> Pozadinski zvuk (Muzika / Efekti)
          </div>
          
          {/* Fallback sinusoidni waveform ako nemamo wavesurfer */}
          {!noVocalsAudioUrl && (
            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 10px', opacity: 0.1, pointerEvents: 'none' }}>
              {Array.from({ length: 80 }).map((_, i) => (
                <div key={i} style={{ width: '2px', height: `${20 + Math.sin(i * 0.3) * 15}%`, background: '#cbd5e1', borderRadius: '1px' }} />
              ))}
            </div>
          )}
        </div>

         {/* KURSOR (PLAYHEAD) KOJI KLIZI */}
        {(() => {
          const dur = getVideoDuration();
          const leftPercent = (localCurrentTime / dur) * 100;
          return (
            <div 
              onMouseDown={handleStartScrubbing}
              style={{
                position: 'absolute',
                left: `${leftPercent}%`,
                top: '24px',
                bottom: 0,
                width: '2px',
                background: '#ef4444',
                boxShadow: '0 0 10px #ef4444',
                zIndex: 100,
                cursor: 'ew-resize',
                pointerEvents: 'auto'
              }}
            >
              <div style={{ position: 'absolute', top: '-6px', left: '-5px', width: '12px', height: '12px', borderRadius: '50%', background: '#ef4444', border: '2px solid #fff' }} />
            </div>
          );
        })()}

      </div>
    </div>
  );
}

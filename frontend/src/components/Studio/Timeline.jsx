import { Film, Video, Mic, Volume2, Music } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export default function Timeline() {
  const {
    project,
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
    videoRef,
    dubbedAudioRef,
    bgAudioRef,
    hoveredSegmentId,
    setHoveredSegmentId,
    dubbedBuster
  } = useStudio();

  // Izvedena vrednost za putanju dubbed zvuka
  const dubbedFilename = project?.dubbed_audio_path ? project.dubbed_audio_path.split('/').pop() : null;
  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";
  const dubbedAudioUrl = dubbedFilename ? `${API_BASE_URL}/videos/${dubbedFilename}?cb=${dubbedBuster}` : null;

  // Pomoćna funkcija za iscrtavanje waveform barova u SVG-u
  const generateWaveformBars = (duration, id) => {
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

  if (!project) return null;

  return (
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
          {project.segments && project.segments.map(seg => {
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
          
          {project.segments && project.segments.map(seg => {
            const dur = getVideoDuration();
            const left = (seg.start / dur) * 100;
            const origWidth = ((seg.end - seg.start) / dur) * 100;
            
            // Ako imamo generisan tts_duration, koristimo njega da vidimo da li je duži
            const ttsDur = seg.tts_duration || (seg.end - seg.start);
            const ttsWidth = (ttsDur / dur) * 100;
            const isLonger = seg.tts_duration && (seg.tts_duration > (seg.end - seg.start));
            const isActive = selectedSegmentId === seg.id;
            const isHovered = hoveredSegmentId === seg.id;
            
            return (
              <div 
                key={seg.id}
                onMouseEnter={() => setHoveredSegmentId(seg.id)}
                onMouseLeave={() => setHoveredSegmentId(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSegmentId(seg.id);
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
                  width: `${Math.max(origWidth, ttsWidth)}%`,
                  height: '36px',
                  bottom: '4px',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  overflow: 'visible',
                  border: isActive ? '2px solid #22c55e' : '1px solid rgba(34, 197, 94, 0.15)',
                  background: isActive ? 'rgba(34, 197, 94, 0.2)' : 'rgba(34, 197, 94, 0.05)',
                  transition: 'all 0.15s ease'
                }}
              >
                {/* Premium Tooltip prozorčić na hover ako segment ima upozorenje */}
                {isLonger && isHovered && (
                  <div style={{
                    position: 'absolute',
                    bottom: '100%',
                    left: '50%',
                    transform: 'translateX(-50%) translateY(-10px)',
                    background: 'rgba(15, 23, 42, 0.95)',
                    backdropFilter: 'blur(12px)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 0 10px rgba(239, 68, 68, 0.2)',
                    borderRadius: '10px',
                    padding: '10px 14px',
                    zIndex: 9999,
                    width: '240px',
                    color: '#fff',
                    pointerEvents: 'none',
                    transition: 'all 0.2s ease',
                    display: 'block'
                  }}>
                    {/* Strelica nadole */}
                    <div style={{
                      position: 'absolute',
                      top: '100%',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: '0',
                      height: '0',
                      borderLeft: '6px solid transparent',
                      borderRight: '6px solid transparent',
                      borderTop: '6px solid rgba(15, 23, 42, 0.95)'
                    }} />
                    
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <span style={{ fontSize: '1.1rem', marginTop: '-2px' }}>⚠️</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', textAlign: 'left', whiteSpace: 'normal' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#f87171' }}>Predugačak srpski izgovor!</span>
                        <span style={{ fontSize: '0.7rem', color: '#cbd5e1', lineHeight: '1.3' }}>
                          Srpski glas traje <strong>{seg.tts_duration.toFixed(2)}s</strong> što je za <strong>{(seg.tts_duration - (seg.end - seg.start)).toFixed(2)}s</strong> duže od originalnog prozora ({((seg.end - seg.start)).toFixed(2)}s).
                        </span>
                        <span style={{ fontSize: '0.65rem', color: '#94a3b8', fontStyle: 'italic', marginTop: '4px' }}>
                          💡 Skratite prevod ili ubrzajte segment u Podešavanjima Zvuka.
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Ako je duži, obeležavamo crvenom pozadinom višak trajanja */}
                {isLonger && (
                  <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${((seg.tts_duration - (seg.end - seg.start)) / seg.tts_duration) * 100}%`, background: 'rgba(239, 68, 68, 0.35)', borderLeft: '1px dashed #ef4444', borderRadius: '0 4px 4px 0' }} />
                )}
         
                {/* Waveform */}
                <div style={{ position: 'absolute', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 4px', opacity: isActive ? 0.5 : 0.25, overflow: 'hidden' }}>
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
  );
}

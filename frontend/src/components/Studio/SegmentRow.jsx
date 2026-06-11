import { useEffect, useRef, useState } from 'react';
import { Mic, Loader2, Wand2 } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';
import Knob from '../Common/Knob';

export default function SegmentRow() {
  const {
    project,
    selectedSegmentId,
    setSelectedSegmentId,
    selectedSegmentIds,
    setSelectedSegmentIds,
    segmentEditorTab,
    setSegmentEditorTab,
    applyAudioToAll,
    setApplyAudioToAll,
    shorteningActive,
    loadingSegmentTTS,
    probniAudios,
    isPlaying,
    setProject,
    handleMagicShorten,
    handleTestSegmentTTS,
    saveToHistory,
    shouldFocusTextarea,
    setShouldFocusTextarea,
    handleSaveDraft,
    selectedVoice,
    setSelectedVoice,
    generatingAllTTS,
    savingProject,
    handleGenerateAllTTS
  } = useStudio();

  const textareaRef = useRef(null);
  const [originalTextOnFocus, setOriginalTextOnFocus] = useState('');

  // Sinhronizacija fokusa iz prečica
  useEffect(() => {
    if (shouldFocusTextarea && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.select();
      setShouldFocusTextarea(false);
    }
  }, [selectedSegmentId, shouldFocusTextarea, setShouldFocusTextarea]);

  if (!project || !project.segments || !project.segments.length) return null;

  // AKO JE SELEKTOVANO VIŠE SEGMENTA -> RENDERUJ BULK OPERATIONS PANEL
  if (selectedSegmentIds && selectedSegmentIds.length > 1) {
    const activeSeg = project.segments.find(s => s.id === selectedSegmentId) || project.segments[0] || {};
    
    return (
      <div 
        className="segment-editor-card" 
        style={{ 
          background: 'rgba(139, 92, 246, 0.03)', 
          border: '1px solid rgba(139, 92, 246, 0.15)', 
          borderRadius: '20px', 
          padding: '16px', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '12px',
          height: '100%',
          overflow: 'hidden',
          minWidth: 0
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: '700', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            🎛️ Grupne Akcije ({selectedSegmentIds.length} selektovano)
          </h3>
          <button
            onClick={() => setSelectedSegmentIds([selectedSegmentId])}
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              color: '#fff',
              fontSize: '0.75rem',
              padding: '4px 10px',
              cursor: 'pointer',
              fontWeight: '600',
              outline: 'none',
              transition: 'background 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
          >
            Poništi grupu
          </button>
        </div>

        {/* Skrolabilni kontejner za kontrole */}
        <div style={{ flex: '1 1 0%', overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: '12px', paddingRight: '4px' }}>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: '1.4' }}>
            Izmene na kružnim kontrolama i odabiru glasa biće primenjene na sve selektovane segmente (ID: {selectedSegmentIds.join(', ')}).
          </p>

          {/* Grupni izbor glasa */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Glas za selektovane:</span>
            <select
              value={activeSeg.voice_type || "clone"}
              onChange={(e) => {
                saveToHistory(project.segments);
                const val = e.target.value;
                const updated = project.segments.map(s => {
                  if (selectedSegmentIds.includes(s.id)) {
                    return { ...s, voice_type: val, status: "edited" };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
                setTimeout(() => handleSaveDraft(), 50);
              }}
              style={{ 
                background: 'rgba(0,0,0,0.2)', 
                border: '1px solid rgba(255,255,255,0.08)', 
                color: '#fff', 
                padding: '8px 12px', 
                borderRadius: '8px', 
                outline: 'none', 
                fontSize: '0.85rem', 
                cursor: 'pointer' 
              }}
            >
              <option value="clone">Kloniraj originalni glas (OpenVoice V2)</option>
              <option value="male">Muški glas (Piper - sr_Marko)</option>
            </select>
          </div>

          {/* Grupni DAW kontrolni panel */}
          <div className="daw-controls-grid">
            <Knob
              label="Volume"
              min={-20}
              max={10}
              step={1}
              value={activeSeg.volume !== undefined ? activeSeg.volume : 0}
              defaultValue={0}
              unit="dB"
              onStartChange={() => saveToHistory(project.segments)}
              onChange={(val) => {
                const updated = project.segments.map(s => {
                  if (selectedSegmentIds.includes(s.id)) {
                    return { ...s, volume: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onRelease={handleSaveDraft}
            />

            <Knob
              label="Tempo"
              min={0.5}
              max={2.0}
              step={0.1}
              value={activeSeg.speed !== undefined ? activeSeg.speed : 1.0}
              defaultValue={1.0}
              unit="x"
              onStartChange={() => saveToHistory(project.segments)}
              onChange={(val) => {
                const updated = project.segments.map(s => {
                  if (selectedSegmentIds.includes(s.id)) {
                    return { ...s, speed: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onRelease={handleSaveDraft}
            />

            <Knob
              label="Pitch"
              min={-6}
              max={6}
              step={1}
              value={activeSeg.pitch !== undefined ? activeSeg.pitch : 0}
              defaultValue={0}
              unit="st"
              onStartChange={() => saveToHistory(project.segments)}
              onChange={(val) => {
                const updated = project.segments.map(s => {
                  if (selectedSegmentIds.includes(s.id)) {
                    return { ...s, pitch: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onRelease={handleSaveDraft}
            />

            <Knob
              label="Ducking"
              min={-20}
              max={10}
              step={1}
              value={activeSeg.bg_volume !== undefined ? activeSeg.bg_volume : 0}
              defaultValue={0}
              unit="dB"
              onStartChange={() => saveToHistory(project.segments)}
              onChange={(val) => {
                const updated = project.segments.map(s => {
                  if (selectedSegmentIds.includes(s.id)) {
                    return { ...s, bg_volume: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onRelease={handleSaveDraft}
            />
          </div>
        </div>

        {/* Akcije za grupnu selekciju */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: 'auto', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '12px' }}>
          <button
            onClick={() => {
              saveToHistory(project.segments);
              const updated = project.segments.map(s => {
                if (selectedSegmentIds.includes(s.id)) {
                  return { ...s, volume: 0, speed: 1.0, pitch: 0, bg_volume: 0, status: "edited" };
                }
                return s;
              });
              setProject({ ...project, segments: updated });
              setTimeout(() => handleSaveDraft(), 50);
            }}
            className="new-task-btn"
            style={{ flex: 1, fontSize: '0.85rem' }}
          >
            Resetuj
          </button>
          
          <button
            onClick={async () => {
              // Pokrećemo sekvencijalnu regeneraciju za sve selektovane segmente
              for (const id of selectedSegmentIds) {
                const seg = project.segments.find(s => s.id === id);
                if (seg) {
                  await handleTestSegmentTTS(
                    id,
                    seg.translated || "",
                    seg.voice_type,
                    seg.volume,
                    seg.speed,
                    seg.pitch,
                    seg.bg_volume,
                    false // autoplay = false
                  );
                }
              }
            }}
            className="glow-button"
            style={{ flex: 2, background: '#8b5cf6', justifyContent: 'center', fontSize: '0.85rem' }}
          >
            🎙️ Generiši glas za selektovane
          </button>
        </div>
      </div>
    );
  }

  // STANDARDNI EDIT PANEL ZA POJEDINAČNI SEGMENT
  const activeSegment = project.segments.find(s => s.id === selectedSegmentId) || project.segments[0] || {};
  
  // Automatsko pokretanje regeneracije/podešavanja tona nakon što korisnik pusti slajder
  const handleAutoAdjust = () => {
    handleTestSegmentTTS(
      selectedSegmentId,
      activeSegment.translated || "",
      activeSegment.voice_type,
      activeSegment.volume,
      activeSegment.speed,
      activeSegment.pitch,
      activeSegment.bg_volume,
      false // AUTOPLAY = FALSE za automatsko podešavanje!
    );
  };

  return (
    <div className="segment-editor-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', height: '100%', overflow: 'hidden', minWidth: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: '700', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Mic size={18} className="text-violet-400" /> Uređivanje Segmenta [{selectedSegmentId}]
        </h3>
        <span style={{ fontSize: '0.8rem', color: '#64748b', background: 'rgba(0,0,0,0.2)', padding: '3px 8px', borderRadius: '6px' }}>
          Trajanje: {((activeSegment.end || 0) - (activeSegment.start || 0)).toFixed(2)}s
        </span>
      </div>

      {/* Navigacija tabova */}
      <div className="segment-tabs-container">
        <button
          onClick={() => setSegmentEditorTab("text")}
          style={{
            background: 'none',
            border: 'none',
            borderBottom: segmentEditorTab === "text" ? '2px solid #8b5cf6' : '2px solid transparent',
            color: segmentEditorTab === "text" ? '#fff' : '#64748b',
            padding: '6px 12px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '0.85rem',
            transition: 'all 0.15s'
          }}
        >
          📝 Tekst & Prevod
        </button>
        <button
          onClick={() => setSegmentEditorTab("voice")}
          style={{
            background: 'none',
            border: 'none',
            borderBottom: segmentEditorTab === "voice" ? '2px solid #8b5cf6' : '2px solid transparent',
            color: segmentEditorTab === "voice" ? '#fff' : '#64748b',
            padding: '6px 12px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '0.85rem',
            transition: 'all 0.15s'
          }}
        >
          🎙️ Glas & TTS
        </button>
        <button
          onClick={() => setSegmentEditorTab("audio")}
          style={{
            background: 'none',
            border: 'none',
            borderBottom: segmentEditorTab === "audio" ? '2px solid #8b5cf6' : '2px solid transparent',
            color: segmentEditorTab === "audio" ? '#fff' : '#64748b',
            padding: '6px 12px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '0.85rem',
            transition: 'all 0.15s'
          }}
        >
          🔊 Podešavanja Zvuka
        </button>
      </div>

      {/* Skrolabilni kontejner za sadržaj tabova */}
      <div style={{ flex: '1 1 0%', overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: '12px', paddingRight: '4px' }}>
        {segmentEditorTab === "text" && (
          <>
            {/* Originalni tekst */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Original (Engleski):</span>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px 12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)', fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                "{activeSegment.original}"
              </div>
            </div>

            {/* Prevod tekst (Editabilno) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Prevod na Srpski:</span>
              <textarea
                ref={textareaRef}
                className="edit-segment-textarea"
                style={{ height: '70px', minHeight: '60px' }}
                value={activeSegment.translated || ""}
                onFocus={() => {
                  setOriginalTextOnFocus(activeSegment.translated || "");
                }}
                onBlur={() => {
                  if ((activeSegment.translated || "") !== originalTextOnFocus) {
                    // Snimamo pređašnje stanje
                    const oldSegments = project.segments.map(s => {
                      if (s.id === selectedSegmentId) {
                        return { ...s, translated: originalTextOnFocus };
                      }
                      return s;
                    });
                    saveToHistory(oldSegments);
                    handleSaveDraft();
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    e.currentTarget.blur();
                    handleTestSegmentTTS(
                      selectedSegmentId,
                      activeSegment.translated || "",
                      activeSegment.voice_type,
                      activeSegment.volume,
                      activeSegment.speed,
                      activeSegment.pitch,
                      activeSegment.bg_volume,
                      true
                    );
                  }
                }}
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', marginTop: '2px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ color: isOver ? '#ef4444' : '#64748b' }}>
                        {isOver ? `⚠️ Prekoračen limit za ${currentLen - limit} karaktera!` : `Preporučeno do ${limit} karaktera.`}
                      </span>
                      <button
                        onClick={() => handleMagicShorten(activeSegment.id)}
                        disabled={shorteningActive[activeSegment.id]}
                        title="Automatski skrati i prilagodi dužinu prevoda pomoću AI Lektora"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: '#a78bfa',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '2px',
                          transition: 'all 0.2s ease',
                          outline: 'none',
                          opacity: shorteningActive[activeSegment.id] ? 0.5 : 1
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.2)'}
                        onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
                      >
                        {shorteningActive[activeSegment.id] ? (
                          <Loader2 size={13} className="spinner-icon pulse-icon" style={{ color: '#a78bfa' }} />
                        ) : (
                          <Wand2 size={13} style={{ filter: 'drop-shadow(0 0 4px rgba(167, 139, 250, 0.4))' }} />
                        )}
                      </button>
                    </div>
                    <span style={{ color: isOver ? '#ef4444' : '#cbd5e1', fontWeight: '600' }}>
                      {currentLen} / {limit}
                    </span>
                  </div>
                );
              })()}
            </div>
          </>
        )}

        {segmentEditorTab === "voice" && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* GLOBALNE OPCIJE PROJEKTA */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.15)', borderRadius: '12px', padding: '12px' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#a78bfa', fontWeight: '700' }}>🌍 Globalne opcije projekta:</span>
              
              {/* Odabir TTS glasa projekta */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Podrazumevani glas projekta:</span>
                <select 
                  value={selectedVoice} 
                  onChange={(e) => setSelectedVoice(e.target.value)}
                  style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.15)', color: '#fff', padding: '8px 12px', borderRadius: '8px', outline: 'none', fontSize: '0.8rem', cursor: 'pointer' }}
                >
                  <option value="clone">Kloniraj glas (OpenVoice V2)</option>
                  <option value="male">Muški glas (Marko)</option>
                </select>
              </div>

              {/* Dugmići za Sačuvanje i Generisanje celog glasa */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                <button 
                  onClick={handleSaveDraft}
                  disabled={savingProject}
                  className="new-task-btn"
                  style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', fontSize: '0.8rem', padding: '8px 12px', borderRadius: '8px' }}
                >
                  {savingProject ? <Loader2 size={12} className="spinner-icon pulse-icon" /> : null} Sačuvaj
                </button>

                <button 
                  onClick={handleGenerateAllTTS}
                  disabled={generatingAllTTS}
                  className="glow-button"
                  style={{ flex: 1.5, background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', fontSize: '0.8rem', padding: '8px 12px', borderRadius: '8px', boxShadow: 'none' }}
                >
                  {generatingAllTTS ? <Loader2 size={12} className="spinner-icon pulse-icon" /> : null} Generiši Ceo Glas
                </button>
              </div>
            </div>

            {/* Horizontalni separator */}
            <div style={{ height: '1px', background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />

            {/* Odabir glasa za ovaj segment */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Glas za ovaj segment:</span>
              <select
                value={activeSegment.voice_type || "clone"}
                onChange={(e) => {
                  saveToHistory(project.segments);
                  const updated = project.segments.map(s => {
                    if (s.id === selectedSegmentId) {
                      return { ...s, voice_type: e.target.value, status: "edited" };
                    }
                    return s;
                  });
                  setProject({ ...project, segments: updated });
                  setTimeout(() => handleSaveDraft(), 50);
                }}
                style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', padding: '8px 12px', borderRadius: '8px', outline: 'none', fontSize: '0.85rem', cursor: 'pointer' }}
              >
                <option value="clone">Kloniraj originalni glas (OpenVoice V2)</option>
                <option value="male">Muški glas (Piper - sr_Marko)</option>
              </select>
            </div>

            {/* Preslušavanje i generisanje probnog TTS-a */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', background: 'rgba(0,0,0,0.15)', padding: '12px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.03)', marginTop: '8px' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#64748b', fontWeight: '700' }}>Probni TTS Zapis:</span>
              
              {probniAudios[selectedSegmentId] ? (
                <div style={{ width: '100%' }}>
                  <audio src={probniAudios[selectedSegmentId]} controls style={{ width: '100%', height: '36px', marginBottom: '8px' }} />
                </div>
              ) : (
                <span style={{ fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic', marginBottom: '8px' }}>
                  Glas nije generisan za ovaj segment. Klikni na dugme ispod da generišeš probni TTS.
                </span>
              )}

              <button 
                onClick={() => handleTestSegmentTTS(
                  selectedSegmentId, 
                  activeSegment.translated || "", 
                  activeSegment.voice_type,
                  activeSegment.volume,
                  activeSegment.speed,
                  activeSegment.pitch,
                  activeSegment.bg_volume,
                  true // Autoplay = true
                )}
                disabled={loadingSegmentTTS[selectedSegmentId]}
                className="glow-button"
                style={{
                  background: '#8b5cf6',
                  boxShadow: 'none',
                  padding: '10px 16px',
                  fontSize: '0.85rem',
                  width: '100%',
                  justifyContent: 'center'
                }}
              >
                {loadingSegmentTTS[selectedSegmentId] ? (
                  <Loader2 size={16} className="spinner-icon pulse-icon" />
                ) : (
                  "🎙️ Generiši / Regeneriši Probni Glas"
                )}
              </button>
            </div>
          </div>
        )}

        {segmentEditorTab === "audio" && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Primeni na sve segmente toggle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.15)', borderRadius: '10px', marginBottom: '2px' }}>
              <input
                type="checkbox"
                id="apply-audio-to-all"
                checked={applyAudioToAll}
                onChange={(e) => {
                  const checked = e.target.checked;
                  setApplyAudioToAll(checked);
                  if (checked && activeSegment) {
                    saveToHistory(project.segments);
                    const updated = project.segments.map(s => ({
                      ...s,
                      volume: activeSegment.volume !== undefined ? activeSegment.volume : 0.0,
                      speed: activeSegment.speed !== undefined ? activeSegment.speed : 1.0,
                      pitch: activeSegment.pitch !== undefined ? activeSegment.pitch : 0.0,
                      bg_volume: activeSegment.bg_volume !== undefined ? activeSegment.bg_volume : 0.0
                    }));
                    setProject({ ...project, segments: updated });
                    setTimeout(() => {
                      handleAutoAdjust();
                    }, 50);
                  }
                }}
                style={{ cursor: 'pointer', width: '16px', height: '16px', accentColor: '#8b5cf6' }}
              />
              <label htmlFor="apply-audio-to-all" style={{ fontSize: '0.8rem', color: '#cbd5e1', cursor: 'pointer', userSelect: 'none', fontWeight: '500' }}>
                🔗 Primeni audio podešavanja na sve segmente
              </label>
            </div>

            {/* Kružni DAW kontrolni panel */}
            <div className="daw-controls-grid">
              <Knob
                label="Volume"
                min={-20}
                max={10}
                step={1}
                value={activeSegment.volume !== undefined ? activeSegment.volume : 0}
                defaultValue={0}
                unit="dB"
                onStartChange={() => saveToHistory(project.segments)}
                onChange={(val) => {
                  const updated = project.segments.map(s => {
                    if (applyAudioToAll || s.id === selectedSegmentId) {
                      return { ...s, volume: val };
                    }
                    return s;
                  });
                  setProject({ ...project, segments: updated });
                }}
                onRelease={handleAutoAdjust}
              />

              <Knob
                label="Tempo"
                min={0.5}
                max={2.0}
                step={0.1}
                value={activeSegment.speed !== undefined ? activeSegment.speed : 1.0}
                defaultValue={1.0}
                unit="x"
                onStartChange={() => saveToHistory(project.segments)}
                onChange={(val) => {
                  const updated = project.segments.map(s => {
                    if (applyAudioToAll || s.id === selectedSegmentId) {
                      return { ...s, speed: val };
                    }
                    return s;
                  });
                  setProject({ ...project, segments: updated });
                }}
                onRelease={handleAutoAdjust}
              />

              <Knob
                label="Pitch"
                min={-6}
                max={6}
                step={1}
                value={activeSegment.pitch !== undefined ? activeSegment.pitch : 0}
                defaultValue={0}
                unit="st"
                onStartChange={() => saveToHistory(project.segments)}
                onChange={(val) => {
                  const updated = project.segments.map(s => {
                    if (applyAudioToAll || s.id === selectedSegmentId) {
                      return { ...s, pitch: val };
                    }
                    return s;
                  });
                  setProject({ ...project, segments: updated });
                }}
                onRelease={handleAutoAdjust}
              />

              <Knob
                label="Ducking"
                min={-20}
                max={10}
                step={1}
                value={activeSegment.bg_volume !== undefined ? activeSegment.bg_volume : 0}
                defaultValue={0}
                unit="dB"
                onStartChange={() => saveToHistory(project.segments)}
                onChange={(val) => {
                  const updated = project.segments.map(s => {
                    if (applyAudioToAll || s.id === selectedSegmentId) {
                      return { ...s, bg_volume: val };
                    }
                    return s;
                  });
                  setProject({ ...project, segments: updated });
                }}
                onRelease={handleAutoAdjust}
              />
            </div>
          </div>
        )}

        {/* Upozorenje ako je prevod ili glas modifikovan a nije regenerisan */}
        {activeSegment.status === "edited" && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.2)', borderRadius: '8px', color: '#facc15', fontSize: '0.8rem', marginTop: '4px' }}>
            <span>⚠️ Izmenjeno, regenerišite glas!</span>
          </div>
        )}
      </div>
    </div>
  );
}

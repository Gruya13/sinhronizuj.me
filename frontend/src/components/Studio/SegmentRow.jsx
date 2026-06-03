import { Mic, Loader2, Wand2 } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export default function SegmentRow() {
  const {
    project,
    selectedSegmentId,
    setSelectedSegmentId,
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
    handleTestSegmentTTS
  } = useStudio();

  if (!project || !project.segments || !project.segments.length) return null;

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
    <div className="segment-editor-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Mic size={18} className="text-violet-400" /> Uređivanje Segmenta [{selectedSegmentId}]
        </h3>
        <span style={{ fontSize: '0.8rem', color: '#64748b', background: 'rgba(0,0,0,0.2)', padding: '3px 8px', borderRadius: '6px' }}>
          Trajanje: {((activeSegment.end || 0) - (activeSegment.start || 0)).toFixed(2)}s
        </span>
      </div>

      {/* Navigacija tabova */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '4px', gap: '15px', marginBottom: '10px' }}>
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

      {segmentEditorTab === "text" ? (
        <>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', marginTop: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ color: isOver ? '#ef4444' : '#64748b' }}>
                      {isOver ? `⚠️ Prekoračen preporučeni limit za ${currentLen - limit} karaktera!` : `Preporučeno do ${limit} karaktera.`}
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
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* Primeni na sve segmente toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.15)', borderRadius: '10px', marginBottom: '4px' }}>
            <input
              type="checkbox"
              id="apply-audio-to-all"
              checked={applyAudioToAll}
              onChange={(e) => {
                const checked = e.target.checked;
                setApplyAudioToAll(checked);
                if (checked && activeSegment) {
                  // Odmah iskopiraj trenutna podešavanja na sve segmente
                  const updated = project.segments.map(s => ({
                    ...s,
                    volume: activeSegment.volume !== undefined ? activeSegment.volume : 0.0,
                    speed: activeSegment.speed !== undefined ? activeSegment.speed : 1.0,
                    pitch: activeSegment.pitch !== undefined ? activeSegment.pitch : 0.0,
                    bg_volume: activeSegment.bg_volume !== undefined ? activeSegment.bg_volume : 0.0
                  }));
                  setProject({ ...project, segments: updated });
                  // Pokreni auto adjust nakon kratkog timeout-a
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

          {/* Jačina zvuka (Volume) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#cbd5e1' }}>
              <span>Jačina zvuka (Volume):</span>
              <span style={{ fontWeight: 'bold', color: '#a78bfa' }}>{activeSegment.volume > 0 ? `+${activeSegment.volume}` : activeSegment.volume || 0} dB</span>
            </div>
            <input
              type="range"
              min="-20"
              max="10"
              step="1"
              value={activeSegment.volume !== undefined ? activeSegment.volume : 0}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                const updated = project.segments.map(s => {
                  if (applyAudioToAll || s.id === selectedSegmentId) {
                    return { ...s, volume: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onMouseUp={handleAutoAdjust}
              onTouchEnd={handleAutoAdjust}
              style={{ width: '100%', accentColor: '#8b5cf6', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#64748b' }}>
              <span>-20 dB (Tiho)</span>
              <span>0 dB (Default)</span>
              <span>+10 dB (Glasno)</span>
            </div>
          </div>

          {/* Brzina / Tempo (x) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#cbd5e1' }}>
              <span>Brzina govora (Tempo):</span>
              <span style={{ fontWeight: 'bold', color: '#a78bfa' }}>{activeSegment.speed !== undefined ? activeSegment.speed.toFixed(1) : "1.0"}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={activeSegment.speed !== undefined ? activeSegment.speed : 1.0}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                const updated = project.segments.map(s => {
                  if (applyAudioToAll || s.id === selectedSegmentId) {
                    return { ...s, speed: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onMouseUp={handleAutoAdjust}
              onTouchEnd={handleAutoAdjust}
              style={{ width: '100%', accentColor: '#8b5cf6', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#64748b' }}>
              <span>0.5x (Sporo)</span>
              <span>1.0x (Normalno)</span>
              <span>2.0x (Brzo)</span>
            </div>
          </div>

          {/* Visina glasa (Pitch semitoni) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#cbd5e1' }}>
              <span>Visina tona (Pitch):</span>
              <span style={{ fontWeight: 'bold', color: '#a78bfa' }}>{activeSegment.pitch > 0 ? `+${activeSegment.pitch}` : activeSegment.pitch || 0} st</span>
            </div>
            <input
              type="range"
              min="-6"
              max="6"
              step="1"
              value={activeSegment.pitch !== undefined ? activeSegment.pitch : 0}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                const updated = project.segments.map(s => {
                  if (applyAudioToAll || s.id === selectedSegmentId) {
                    return { ...s, pitch: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onMouseUp={handleAutoAdjust}
              onTouchEnd={handleAutoAdjust}
              style={{ width: '100%', accentColor: '#8b5cf6', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#64748b' }}>
              <span>Dubok muški</span>
              <span>0 (Original)</span>
              <span>Visok piskav</span>
            </div>
          </div>

          {/* Jačina pozadinske muzike (Ducking) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#cbd5e1' }}>
              <span>Jačina pozadinske muzike (Ducking):</span>
              <span style={{ fontWeight: 'bold', color: '#a78bfa' }}>{activeSegment.bg_volume > 0 ? `+${activeSegment.bg_volume}` : activeSegment.bg_volume || 0} dB</span>
            </div>
            <input
              type="range"
              min="-20"
              max="10"
              step="1"
              value={activeSegment.bg_volume !== undefined ? activeSegment.bg_volume : 0}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                const updated = project.segments.map(s => {
                  if (applyAudioToAll || s.id === selectedSegmentId) {
                    return { ...s, bg_volume: val };
                  }
                  return s;
                });
                setProject({ ...project, segments: updated });
              }}
              onMouseUp={handleAutoAdjust}
              onTouchEnd={handleAutoAdjust}
              style={{ width: '100%', accentColor: '#8b5cf6', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#64748b' }}>
              <span>-20 dB (Prigušeno)</span>
              <span>0 dB (Default)</span>
              <span>+10 dB (Glasno)</span>
            </div>
          </div>
        </div>
      ) }

      {/* Upozorenje ako je prevod ili glas modifikovan a nije regenerisan */}
      {activeSegment.status === "edited" && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.2)', borderRadius: '8px', color: '#facc15', fontSize: '0.8rem', marginTop: '10px', marginBottom: '10px' }}>
          <span>⚠️ Prevod ili glas su izmenjeni, generišite glas ponovo!</span>
        </div>
      )}

      {/* Akcije za segment */}
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: 'auto', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '15px' }}>
        {/* Preslušavanje probnog TTS-a */}
        {probniAudios[selectedSegmentId] ? (
          <div style={{ flex: 1 }}>
            <audio src={probniAudios[selectedSegmentId]} controls style={{ width: '100%', height: '36px' }} />
          </div>
        ) : (
          <span style={{ flex: 1, fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic' }}>
            Glas nije generisan za ovaj segment. Klikni "Regeneriši Probni Glas".
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
            fontSize: '0.85rem'
          }}
        >
          {loadingSegmentTTS[selectedSegmentId] ? (
            <Loader2 size={16} className="spinner-icon pulse-icon" />
          ) : (
            "🎙️ Regeneriši Probni Glas"
          )}
        </button>
      </div>
    </div>
  );
}

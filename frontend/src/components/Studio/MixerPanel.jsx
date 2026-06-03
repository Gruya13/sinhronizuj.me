import { Loader2, Mic, Save, Zap } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';
import Knob from '../Common/Knob';

export default function MixerPanel() {
  const {
    project,
    bgVolume,
    setBgVolume,
    dubVolume,
    setDubVolume,
    selectedVoice,
    setSelectedVoice,
    generatingAllTTS,
    savingProject,
    handleGenerateAllTTS,
    handleSaveDraft,
    handleRenderProject
  } = useStudio();

  if (!project) return null;

  return (
    <div 
      className="studio-controls-row" 
      style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '20px', padding: '24px' }}
    >
      {/* Leva strana: Mixer i odabir glasa */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <h4 style={{ fontSize: '0.9rem', fontWeight: '700', textTransform: 'uppercase', color: '#94a3b8' }}>🎛️ Audio Mikser & Podešavanje glasa</h4>
        
        <div style={{ display: 'flex', gap: '30px', justifyContent: 'flex-start', background: 'rgba(0,0,0,0.15)', padding: '16px 20px', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.03)', width: 'fit-content' }}>
          <Knob
            label="Muzika & Efekti"
            min={-30}
            max={10}
            step={1}
            value={bgVolume}
            defaultValue={-5}
            unit="dB"
            onChange={setBgVolume}
          />
          <Knob
            label="Srpski AI Glas"
            min={-15}
            max={15}
            step={1}
            value={dubVolume}
            defaultValue={0}
            unit="dB"
            onChange={setDubVolume}
          />
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
  );
}

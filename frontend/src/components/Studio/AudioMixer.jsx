import { useStudio } from '../../context/StudioContext';

export default function AudioMixer() {
  const {
    bgVolume,
    setBgVolume,
    dubVolume,
    setDubVolume
  } = useStudio();

  return (
    <div className="player-mixer-controls">
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Muzika:</span>
        <input 
          type="range" 
          min="-30" 
          max="10" 
          step="1"
          value={bgVolume} 
          onChange={(e) => setBgVolume(parseInt(e.target.value))}
          style={{ width: '80px', accentColor: '#8b5cf6', height: '4px', cursor: 'pointer' }}
        />
        <span style={{ fontSize: '0.7rem', color: '#cbd5e1', width: '30px', fontFamily: 'monospace', textAlign: 'right' }}>{bgVolume}dB</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>AI Glas:</span>
        <input 
          type="range" 
          min="-15" 
          max="15" 
          step="1"
          value={dubVolume} 
          onChange={(e) => setDubVolume(parseInt(e.target.value))}
          style={{ width: '80px', accentColor: '#22c55e', height: '4px', cursor: 'pointer' }}
        />
        <span style={{ fontSize: '0.7rem', color: '#cbd5e1', width: '30px', fontFamily: 'monospace', textAlign: 'right' }}>{dubVolume}dB</span>
      </div>
    </div>
  );
}

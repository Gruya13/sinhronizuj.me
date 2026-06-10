import { ShieldCheck, Zap, Trash2 } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export default function HardwareMonitor() {
  const { hwStats, modalStatus, status, handleFlushRedis } = useStudio();

  return (
    <div className="hardware-monitor-container">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' }}>
        <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '1px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 'bold' }}>
          <ShieldCheck size={12} style={{ color: '#10b981' }} /> <span className="hide-mobile">Hetzner VPS</span>
        </div>
        <div style={{ fontSize: '0.8rem', fontWeight: '600', display: 'flex', gap: '10px', color: '#f8fafc' }}>
          <span><span className="hide-mobile">CPU: </span>{hwStats?.cpu_usage || 0}%</span>
          <span><span className="hide-mobile">RAM: </span>{hwStats?.memory?.percent || 0}%</span>
        </div>
      </div>
      
      <div style={{ width: '1px', height: '24px', background: 'rgba(255, 255, 255, 0.1)' }} />
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' }}>
        <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '1px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 'bold' }}>
          <Zap size={12} className={modalStatus?.status === "Spreman" ? "pulse-icon" : ""} style={{ color: modalStatus?.status === "Spreman" ? '#eab308' : '#64748b' }} /> 
          <span className="hide-mobile">Modal GPU</span>
          <span 
            style={{ 
              fontSize: '8px', 
              fontWeight: '800', 
              background: modalStatus?.status === "Spreman" ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.15)', 
              color: modalStatus?.status === "Spreman" ? '#34d399' : '#94a3b8', 
              padding: '1px 5px', 
              borderRadius: '4px',
              border: modalStatus?.status === "Spreman" ? '1px solid rgba(16, 185, 129, 0.2)' : '1px solid rgba(100, 116, 139, 0.2)',
              marginLeft: '4px',
              letterSpacing: '0.2px'
            }}
          >
            {modalStatus?.status === "Spreman" ? `SPREMAN` : "SPAVA"}
          </span>
        </div>
        <div className="hide-mobile" style={{ fontSize: '0.8rem', fontWeight: '600', display: 'flex', gap: '10px', color: '#64748b' }}>
          <span style={{ color: status?.includes("Whisper") ? "#38bdf8" : '#475569', textShadow: status?.includes("Whisper") ? '0 0 10px rgba(56, 189, 248, 0.5)' : 'none', transition: 'all 0.3s' }}>Whisper</span>
          <span style={{ color: status?.includes("Prevođenje") || status?.includes("Lektura") ? "#38bdf8" : '#475569', textShadow: status?.includes("Prevođenje") || status?.includes("Lektura") ? '0 0 10px rgba(56, 189, 248, 0.5)' : 'none', transition: 'all 0.3s' }}>Qwen</span>
          <span style={{ color: status?.includes("Sinteza") || status?.includes("TTS") ? "#38bdf8" : '#475569', textShadow: status?.includes("Sinteza") || status?.includes("TTS") ? '0 0 10px rgba(56, 189, 248, 0.5)' : 'none', transition: 'all 0.3s' }}>OpenVoice</span>
        </div>
      </div>
      
      <div style={{ width: '1px', height: '24px', background: 'rgba(255, 255, 255, 0.1)' }} />
      
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <button 
          onClick={handleFlushRedis} 
          style={{ 
            background: 'rgba(239, 68, 68, 0.15)', 
            border: '1px solid rgba(239, 68, 68, 0.3)', 
            color: '#f87171', 
            padding: '6px 10px', 
            borderRadius: '6px', 
            fontSize: '11px', 
            fontWeight: '600', 
            cursor: 'pointer', 
            display: 'flex', 
            alignItems: 'center', 
            gap: '5px', 
            transition: 'all 0.2s', 
            fontFamily: 'inherit' 
          }}
          title="Očisti Redis Keš"
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)';
            e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)';
            e.currentTarget.style.color = '#fff';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)';
            e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.3)';
            e.currentTarget.style.color = '#f87171';
          }}
        >
          <Trash2 size={12} /> <span className="hide-mobile">Očisti Redis</span>
        </button>
      </div>
    </div>
  );
}

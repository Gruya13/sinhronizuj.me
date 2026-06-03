import { ShieldCheck, Zap, Trash2 } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export default function HardwareMonitor() {
  const { hwStats, modalStatus, status, handleFlushRedis } = useStudio();

  return (
    <div className="hybrid-monitor">
      <div className="monitor-section">
        <div className="monitor-label">
          <ShieldCheck size={14} /> Hetzner VPS
        </div>
        <div className="monitor-stats">
          <span>CPU: {hwStats?.cpu_usage || 0}%</span>
          <span>RAM: {hwStats?.memory?.percent || 0}%</span>
        </div>
      </div>
      
      <div className="monitor-divider" />
      
      <div className="monitor-section">
        <div className="monitor-label">
          <Zap size={14} className={modalStatus?.status === "Spreman" ? "pulse-icon" : ""} /> 
          Modal GPU
          <span className={`status-badge ${modalStatus?.status === "Spreman" ? 'active' : 'asleep'}`}>
            {modalStatus?.status === "Spreman" ? `SPREMAN (Auto-scale)` : "SPAVA"}
          </span>
        </div>
        <div className="monitor-status">
          <span className={status?.includes("Whisper") ? "active-worker" : ""}>Whisper</span>
          <span className={status?.includes("Prevođenje") || status?.includes("Lektura") ? "active-worker" : ""}>Qwen</span>
          <span className={status?.includes("Sinteza") || status?.includes("TTS") ? "active-worker" : ""}>OpenVoice</span>
        </div>
      </div>
      
      <div className="monitor-divider" />
      
      <div className="monitor-section" style={{ justifyContent: 'center' }}>
        <button 
          onClick={handleFlushRedis} 
          className="flush-redis-btn" 
          style={{ 
            background: 'rgba(239, 68, 68, 0.15)', 
            border: '1px solid rgba(239, 68, 68, 0.3)', 
            color: '#f87171', 
            padding: '4px 10px', 
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
        >
          <Trash2 size={12} /> Očisti Redis
        </button>
      </div>
    </div>
  );
}

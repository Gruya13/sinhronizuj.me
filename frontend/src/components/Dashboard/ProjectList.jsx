import { Video, Trash2 } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';

export default function ProjectList() {
  const { 
    projects, 
    handleSelectProject, 
    handleDeleteProject, 
    setIsCreateModalOpen 
  } = useStudio();

  return (
    <div className="projects-dashboard" style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: '700', color: '#f1f5f9' }}>Moji Projekti</h2>
        <button 
          onClick={() => setIsCreateModalOpen(true)} 
          className="glow-button"
          style={{ padding: '10px 20px', borderRadius: '12px' }}
        >
          + Novi Projekat
        </button>
      </div>

      {projects.length === 0 ? (
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '16px', padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
          <Video size={48} style={{ margin: '0 auto 15px', color: '#64748b', opacity: 0.5 }} />
          <p style={{ fontSize: '1rem', fontWeight: '600' }}>Nemate kreiranih projekata</p>
          <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '5px' }}>Kliknite na dugme iznad da započnete novi projekat sinhronizacije.</p>
        </div>
      ) : (
        <div className="projects-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px' }}>
          {projects.map((proj) => {
            let statusText = "Prazan";
            let statusClass = "asleep";
            if (proj.status === "analyzing") { statusText = "Analiza..."; statusClass = "analyzing"; }
            else if (proj.status === "ready") { statusText = "Spreman za rad"; statusClass = "active"; }
            else if (proj.status === "completed") { statusText = "Završen"; statusClass = "completed"; }
            
            return (
              <div 
                key={proj.id}
                onClick={() => handleSelectProject(proj)}
                style={{ 
                  background: 'rgba(255,255,255,0.03)', 
                  border: '1px solid rgba(255,255,255,0.05)', 
                  borderRadius: '16px', 
                  padding: '20px', 
                  cursor: 'pointer', 
                  transition: 'all 0.2s',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '15px',
                  position: 'relative'
                }}
                className="project-card"
              >
                <button 
                  onClick={(e) => handleDeleteProject(e, proj.id)}
                  style={{ 
                    position: 'absolute', 
                    top: '15px', 
                    right: '15px', 
                    background: 'transparent', 
                    border: 'none', 
                    color: '#64748b', 
                    cursor: 'pointer',
                    padding: '5px',
                    borderRadius: '6px',
                    transition: 'all 0.2s'
                  }}
                  className="delete-project-btn"
                  title="Obriši projekat"
                >
                  <Trash2 size={16} />
                </button>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', width: '85%' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{proj.name}</h3>
                  <p style={{ fontSize: '0.8rem', color: '#94a3b8', height: '20px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {proj.video_title || "Nema učitanog videa"}
                  </p>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '10px', fontSize: '0.8rem' }}>
                  <span style={{ color: '#64748b' }}>{new Date(proj.created_at).toLocaleDateString()}</span>
                  <span className={`status-badge ${statusClass}`} style={{ fontSize: '10px' }}>{statusText}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

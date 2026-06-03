import { Video, Trash2, Clock, CheckCircle2, FolderOpen, Plus, BarChart3 } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';
import { motion } from 'framer-motion';

export default function ProjectList() {
  const { 
    projects, 
    handleSelectProject, 
    handleDeleteProject, 
    setIsCreateModalOpen 
  } = useStudio();

  // Izračunavanje statistika
  const totalProjects = projects.length;
  const analyzingProjects = projects.filter(p => p.status === 'analyzing').length;
  const readyProjects = projects.filter(p => p.status === 'ready').length;
  const completedProjects = projects.filter(p => p.status === 'completed').length;

  // Kontejner animacije za stagger efekat
  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.08
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 15 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 120, damping: 14 } }
  };

  return (
    <div className="projects-dashboard" style={{ display: 'flex', flexDirection: 'column', gap: '30px', marginTop: '10px' }}>
      
      {/* STATISTIKA PANEL */}
      <motion.div 
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px',
          background: 'rgba(255,255,255,0.01)',
          border: '1px solid rgba(255,255,255,0.04)',
          borderRadius: '20px',
          padding: '20px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '10px' }}>
          <div style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#c084fc', padding: '12px', borderRadius: '14px' }}>
            <FolderOpen size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 'bold' }}>Ukupno Projekata</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', fontFamily: 'Outfit' }}>{totalProjects}</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '10px' }}>
          <div style={{ background: 'rgba(6, 182, 212, 0.15)', color: '#22d3ee', padding: '12px', borderRadius: '14px' }}>
            <Clock size={20} className={analyzingProjects > 0 ? "pulse-icon" : ""} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 'bold' }}>U Obradi (Analiza)</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', fontFamily: 'Outfit' }}>{analyzingProjects}</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '10px' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', padding: '12px', borderRadius: '14px' }}>
            <CheckCircle2 size={20} />
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 'bold' }}>Završeno / Spreman</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', fontFamily: 'Outfit' }}>{readyProjects + completedProjects}</div>
          </div>
        </div>
      </motion.div>

      {/* HEADER SA DUGMETOM */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: '800', fontFamily: 'Outfit', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BarChart3 size={22} className="text-violet-400" /> Moji Projekti
        </h2>
        <button 
          onClick={() => setIsCreateModalOpen(true)} 
          className="glow-button"
          style={{ 
            padding: '10px 20px', 
            borderRadius: '12px',
            fontFamily: 'Outfit',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Plus size={18} /> Novi Projekat
        </button>
      </div>

      {projects.length === 0 ? (
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{ 
            background: 'rgba(255,255,255,0.01)', 
            border: '1px solid rgba(255,255,255,0.03)', 
            borderRadius: '24px', 
            padding: '60px 40px', 
            textAlign: 'center', 
            color: '#64748b' 
          }}
        >
          <Video size={54} style={{ margin: '0 auto 20px', color: '#475569', opacity: 0.4 }} />
          <p style={{ fontSize: '1.1rem', fontWeight: '700', color: '#94a3b8', fontFamily: 'Outfit' }}>Nemate kreiranih projekata</p>
          <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '8px', maxWidth: '380px', margin: '8px auto 0' }}>
            Kliknite na dugme <strong>Novi Projekat</strong> iznad da započnete magičnu sinhronizaciju videa na srpski jezik.
          </p>
        </motion.div>
      ) : (
        <div 
          className="projects-grid" 
          style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', 
            gap: '20px' 
          }}
        >
          {projects.map((proj, index) => {
            let statusText = "Prazan";
            let statusClass = "asleep";
            let StatusIcon = Video;
            let iconColor = "#94a3b8";

            if (proj.status === "analyzing") { 
              statusText = "Analiza..."; 
              statusClass = "analyzing"; 
              StatusIcon = Clock;
              iconColor = "#06b6d4";
            }
            else if (proj.status === "ready") { 
              statusText = "Spreman za rad"; 
              statusClass = "active"; 
              StatusIcon = FolderOpen;
              iconColor = "#8b5cf6";
            }
            else if (proj.status === "completed") { 
              statusText = "Završen"; 
              statusClass = "completed"; 
              StatusIcon = CheckCircle2;
              iconColor = "#10b981";
            }
            
            return (
              <motion.div 
                key={proj.id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 120, damping: 14, delay: index * 0.05 }}
                whileHover={{ 
                  y: -6, 
                  borderColor: 'rgba(139, 92, 246, 0.25)',
                  boxShadow: '0 12px 30px -10px rgba(0, 0, 0, 0.6), 0 0 20px rgba(139, 92, 246, 0.05)'
                }}
                onClick={() => handleSelectProject(proj)}
                style={{ 
                  background: 'linear-gradient(135deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0.01) 100%)', 
                  border: '1px solid rgba(255,255,255,0.04)', 
                  borderRadius: '20px', 
                  padding: '22px', 
                  cursor: 'pointer', 
                  transition: 'border-color 0.25s, box-shadow 0.25s',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '20px',
                  position: 'relative',
                  overflow: 'hidden'
                }}
                className="project-card"
              >
                {/* Status Indicator na samom vrhu kartice */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ 
                    background: `rgba(${statusClass === 'active' ? '139, 92, 246' : statusClass === 'completed' ? '16, 185, 129' : '6, 182, 212'}, 0.1)`, 
                    color: iconColor, 
                    padding: '8px', 
                    borderRadius: '10px' 
                  }}>
                    <StatusIcon size={18} />
                  </div>
                  
                  <button 
                    onClick={(e) => handleDeleteProject(e, proj.id)}
                    style={{ 
                      background: 'transparent', 
                      border: 'none', 
                      color: 'var(--text-dim)', 
                      cursor: 'pointer',
                      padding: '6px',
                      borderRadius: '8px',
                      transition: 'all 0.2s',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    className="delete-project-btn-hover"
                    title="Obriši projekat"
                    onMouseEnter={(e) => e.currentTarget.style.color = '#f43f5e'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-dim)'}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>

                {/* Središnji deo - Detalji */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <h3 style={{ 
                    fontSize: '1.2rem', 
                    fontWeight: '700', 
                    fontFamily: 'Outfit',
                    color: '#f1f5f9', 
                    whiteSpace: 'nowrap', 
                    overflow: 'hidden', 
                    textOverflow: 'ellipsis' 
                  }}>
                    {proj.name}
                  </h3>
                  <p style={{ 
                    fontSize: '0.8rem', 
                    color: 'var(--text-secondary)', 
                    height: '20px', 
                    whiteSpace: 'nowrap', 
                    overflow: 'hidden', 
                    textOverflow: 'ellipsis',
                    fontWeight: '500'
                  }}>
                    {proj.video_title || "Nema učitanog videa"}
                  </p>
                </div>

                {/* Donji deo - Datum i status */}
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center', 
                  borderTop: '1px solid rgba(255,255,255,0.04)', 
                  paddingTop: '12px', 
                  fontSize: '0.75rem',
                  color: 'var(--text-dim)'
                }}>
                  <span>{new Date(proj.created_at).toLocaleDateString('sr-RS')}</span>
                  <span className={`status-badge ${statusClass}`} style={{ fontSize: '9px', padding: '3px 8px', borderRadius: '6px' }}>
                    {statusText}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}

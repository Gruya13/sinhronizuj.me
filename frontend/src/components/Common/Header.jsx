import { useState, useRef, useEffect } from 'react';
import { FolderOpen, Plus, ChevronDown, Check, LayoutDashboard, Settings } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';
import { motion, AnimatePresence } from 'framer-motion';
import HardwareMonitor from './HardwareMonitor';

export default function Header() {
  const {
    user,
    handleLogout,
    projects,
    project,
    handleSelectProject,
    resetStudio,
    setIsCreateModalOpen
  } = useStudio();

  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Zatvaranje dropdown-a klikom van njega
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isOpen]);

  const activeProjectName = project ? project.name : null;

  return (
    <header 
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 24px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        background: 'rgba(15, 23, 42, 0.2)',
        backdropFilter: 'blur(20px)',
        borderRadius: '24px 24px 0 0',
        position: 'relative',
        zIndex: 999,
        gap: '20px',
        flexWrap: 'wrap'
      }}
    >
      {/* BRANDING / LOGO */}
      <div 
        onClick={resetStudio}
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px', 
          cursor: 'pointer',
          userSelect: 'none',
          flexShrink: 0
        }}
      >
        <span 
          style={{ 
            fontFamily: 'Outfit', 
            fontSize: '1.4rem', 
            fontWeight: '900', 
            background: 'linear-gradient(135deg, #a78bfa 0%, #06b6d4 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            letterSpacing: '-0.5px'
          }}
        >
          sinhronizuj.me
        </span>
        <span 
          style={{ 
            fontSize: '9px', 
            fontWeight: 'bold', 
            background: 'rgba(139, 92, 246, 0.15)', 
            color: '#c084fc', 
            padding: '2px 6px', 
            borderRadius: '6px',
            border: '1px solid rgba(139, 92, 246, 0.2)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}
        >
          Studio V2
        </span>
      </div>

      {/* MONITOR STATUSA U SREDINI */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', minWidth: '280px' }}>
        <HardwareMonitor />
      </div>

      {/* DESNI DEO: DROPDOWN I PROFIL */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
        <div ref={dropdownRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setIsOpen(!isOpen)}
            style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '8px 16px',
              color: '#fff',
              fontFamily: 'Outfit',
              fontWeight: '600',
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 0.2s',
              outline: 'none',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
              e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.3)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)';
            }}
          >
            <FolderOpen size={15} className="text-violet-400" />
            <span style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {activeProjectName ? `Projekat: ${activeProjectName}` : 'Moji Projekti'}
            </span>
            <ChevronDown size={14} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
          </button>

          <AnimatePresence>
            {isOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.96 }}
                transition={{ duration: 0.15 }}
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 8px)',
                  right: 0,
                  width: '260px',
                  background: 'rgba(15, 23, 42, 0.95)',
                  backdropFilter: 'blur(16px)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '16px',
                  padding: '8px',
                  boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.7), 0 0 20px rgba(139, 92, 246, 0.03)',
                  zIndex: 1000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '2px'
                }}
              >
                {/* STAVKA: DASHBOARD */}
                <button
                  onClick={() => {
                    resetStudio();
                    setIsOpen(false);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    width: '100%',
                    background: !project ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
                    border: 'none',
                    color: !project ? '#c084fc' : '#94a3b8',
                    padding: '8px 12px',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    fontWeight: '600',
                    textAlign: 'left',
                    transition: 'all 0.15s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                    e.currentTarget.style.color = '#fff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = !project ? 'rgba(139, 92, 246, 0.1)' : 'transparent';
                    e.currentTarget.style.color = !project ? '#c084fc' : '#94a3b8';
                  }}
                >
                  <LayoutDashboard size={14} />
                  <span>Svi Projekti (Dashboard)</span>
                  {!project && <Check size={12} style={{ marginLeft: 'auto' }} />}
                </button>

                <div style={{ height: '1px', background: 'rgba(255, 255, 255, 0.05)', margin: '6px 4px' }} />

                {/* LISTA PROJEKATA */}
                <div 
                  style={{ 
                    maxHeight: '200px', 
                    overflowY: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                    paddingRight: '2px'
                  }}
                >
                  {projects.length === 0 ? (
                    <div style={{ padding: '12px', textAlign: 'center', fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic' }}>
                      Nema kreiranih projekata
                    </div>
                  ) : (
                    projects.map((proj) => {
                      const isActive = project && project.project_id === proj.id;
                      let statusColor = '#94a3b8';
                      if (proj.status === 'analyzing') statusColor = '#06b6d4';
                      else if (proj.status === 'ready') statusColor = '#8b5cf6';
                      else if (proj.status === 'completed') statusColor = '#10b981';

                      return (
                        <button
                          key={proj.id}
                          onClick={() => {
                            handleSelectProject(proj);
                            setIsOpen(false);
                          }}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            width: '100%',
                            background: isActive ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
                            border: 'none',
                            color: isActive ? '#c084fc' : '#cbd5e1',
                            padding: '8px 12px',
                            borderRadius: '10px',
                            cursor: 'pointer',
                            fontSize: '0.8rem',
                            fontWeight: isActive ? '700' : '500',
                            textAlign: 'left',
                            transition: 'all 0.15s',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                            e.currentTarget.style.color = '#fff';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = isActive ? 'rgba(139, 92, 246, 0.1)' : 'transparent';
                            e.currentTarget.style.color = isActive ? '#c084fc' : '#cbd5e1';
                          }}
                        >
                          {/* Status kružić */}
                          <div 
                            style={{ 
                              width: '6px', 
                              height: '6px', 
                              borderRadius: '50%', 
                              background: statusColor,
                              flexShrink: 0
                            }} 
                          />
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                            {proj.name}
                          </span>
                          {isActive && <Check size={12} style={{ flexShrink: 0 }} />}
                        </button>
                      );
                    })
                  )}
                </div>

                <div style={{ height: '1px', background: 'rgba(255, 255, 255, 0.05)', margin: '6px 4px' }} />

                {/* KREIRAJ NOVI */}
                <button
                  onClick={() => {
                    setIsCreateModalOpen(true);
                    setIsOpen(false);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    width: '100%',
                    background: 'rgba(139, 92, 246, 0.1)',
                    border: '1px dashed rgba(139, 92, 246, 0.3)',
                    color: '#a78bfa',
                    padding: '8px 12px',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    fontWeight: '600',
                    textAlign: 'left',
                    transition: 'all 0.15s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(139, 92, 246, 0.2)';
                    e.currentTarget.style.color = '#fff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(139, 92, 246, 0.1)';
                    e.currentTarget.style.color = '#a78bfa';
                  }}
                >
                  <Plus size={14} />
                  <span>Novi Projekat...</span>
                </button>

              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {user && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', borderLeft: '1px solid rgba(255, 255, 255, 0.08)', paddingLeft: '16px' }}>
            <div 
              style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'flex-end',
                fontSize: '0.75rem',
                color: '#94a3b8'
              }}
            >
              <span style={{ fontWeight: '700', color: '#f1f5f9' }}>{user.email}</span>
              <span>Korisnik</span>
            </div>
            <button
              onClick={handleLogout}
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                borderRadius: '10px',
                padding: '6px 12px',
                color: '#f87171',
                fontFamily: 'Outfit, sans-serif',
                fontWeight: '600',
                fontSize: '0.8rem',
                cursor: 'pointer',
                transition: 'all 0.2s',
                outline: 'none'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                e.currentTarget.style.color = '#fff';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                e.currentTarget.style.color = '#f87171';
              }}
            >
              Odjavi se
            </button>
          </div>
        )}
      </div>

    </header>
  );
}

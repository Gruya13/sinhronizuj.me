import { useState, useRef, useEffect } from 'react';
import { useStudio } from '../../context/StudioContext';
import { motion, AnimatePresence } from 'framer-motion';
import HardwareMonitor from './HardwareMonitor';

export default function Header() {
  const {
    user,
    handleLogout,
    resetStudio,
    isAdminMode,
    setIsAdminMode,
    adminStats
  } = useStudio();

  return (
    <header className="main-header">
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
      <div style={{ display: 'flex', justifyContent: 'center', flexShrink: 1 }}>
        <HardwareMonitor />
      </div>

      {/* DESNI DEO: KORISNIČKI PROFIL */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
        {user && (
          <div className="header-user-section" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            
            {/* DUGME ZA ADMIN PANEL */}
            {user.is_admin && (
              <button
                onClick={() => {
                  if (isAdminMode) {
                    resetStudio();
                  } else {
                    resetStudio();
                    setIsAdminMode(true);
                  }
                }}
                style={{
                  background: isAdminMode ? 'linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)' : 'rgba(255, 255, 255, 0.05)',
                  border: isAdminMode ? 'none' : '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '10px',
                  padding: '6px 12px',
                  color: '#fff',
                  fontFamily: 'Outfit, sans-serif',
                  fontWeight: '600',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  outline: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                🛡️ Admin
                {adminStats?.users?.waitlist_pending > 0 && (
                  <span style={{
                    background: '#ef4444',
                    color: '#fff',
                    borderRadius: '50%',
                    padding: '1px 6px',
                    fontSize: '0.7rem',
                    fontWeight: 'bold',
                    marginLeft: '2px'
                  }}>
                    {adminStats.users.waitlist_pending}
                  </span>
                )}
              </button>
            )}

            <div 
              className="hide-mobile"
              style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'flex-end',
                fontSize: '0.75rem',
                color: '#94a3b8'
              }}
            >
              <span style={{ fontWeight: '700', color: '#f1f5f9' }}>{user.email}</span>
              <span style={{ fontSize: '0.65rem', color: user.is_admin ? '#c084fc' : '#94a3b8' }}>
                {user.is_admin ? "Administrator" : "Korisnik"}
              </span>
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

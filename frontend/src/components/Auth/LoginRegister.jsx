import { useState } from 'react';
import { useStudio } from '../../context/StudioContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, EyeOff, Loader2, KeyRound, Mail, AlertCircle, Sparkles } from 'lucide-react';

export default function LoginRegister({ onBack }) {
  const { handleLogin, handleRegister, error, setError } = useStudio();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) return;

    setLoading(true);
    setError(null);

    try {
      if (isLogin) {
        await handleLogin(email, password);
      } else {
        await handleRegister(email, password);
        // Nakon registracije, automatski ga logujemo ili obaveštavamo
        setIsLogin(true);
        setPassword('');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    if (isLogin) {
      if (onBack) {
        onBack();
      }
    } else {
      setIsLogin(true);
      setError(null);
      setPassword('');
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        width: '100%',
        background: 'radial-gradient(circle at top left, rgba(139, 92, 246, 0.15) 0%, transparent 40%), radial-gradient(circle at bottom right, rgba(6, 182, 212, 0.1) 0%, transparent 40%), #0b0f19',
        padding: '24px',
        boxSizing: 'border-box',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* Dekorativni pozadinski elementi */}
      <div
        style={{
          position: 'absolute',
          top: '15%',
          left: '10%',
          width: '300px',
          height: '300px',
          background: 'rgba(139, 92, 246, 0.12)',
          borderRadius: '50%',
          filter: 'blur(80px)',
          zIndex: 1,
          pointerEvents: 'none'
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '15%',
          right: '10%',
          width: '350px',
          height: '350px',
          background: 'rgba(6, 182, 212, 0.08)',
          borderRadius: '50%',
          filter: 'blur(100px)',
          zIndex: 1,
          pointerEvents: 'none'
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        style={{
          width: '100%',
          maxWidth: '440px',
          background: 'rgba(17, 24, 39, 0.45)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.07)',
          borderRadius: '24px',
          padding: '40px 32px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px rgba(139, 92, 246, 0.04)',
          zIndex: 2,
          position: 'relative',
          boxSizing: 'border-box'
        }}
      >
        {/* DUGME NAZAD NA LANDING */}
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            style={{
              position: 'absolute',
              top: '20px',
              left: '24px',
              background: 'none',
              border: 'none',
              color: '#9ca3af',
              fontSize: '0.85rem',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'color 0.2s',
              padding: 0,
              fontFamily: 'inherit',
              zIndex: 10
            }}
            onMouseEnter={(e) => e.currentTarget.style.color = '#fff'}
            onMouseLeave={(e) => e.currentTarget.style.color = '#9ca3af'}
          >
            ← Nazad
          </button>
        )}

        {/* LOGO */}
        <div style={{ textAlign: 'center', marginBottom: '32px', marginTop: onBack ? '12px' : '0px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '48px',
              height: '48px',
              background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(6, 182, 212, 0.2) 100%)',
              border: '1px solid rgba(139, 92, 246, 0.3)',
              borderRadius: '16px',
              marginBottom: '16px',
              boxShadow: '0 8px 16px rgba(139, 92, 246, 0.15)'
            }}
          >
            <Sparkles size={24} style={{ color: '#a78bfa' }} />
          </div>
          <h1
            style={{
              fontFamily: 'Outfit, sans-serif',
              fontSize: '2rem',
              fontWeight: '900',
              background: 'linear-gradient(135deg, #c084fc 0%, #22d3ee 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              margin: '0 0 8px 0',
              letterSpacing: '-0.5px'
            }}
          >
            sinhronizuj.me
          </h1>
          <p style={{ color: '#9ca3af', fontSize: '0.9rem', margin: 0, fontWeight: 500 }}>
            {isLogin ? 'Dobrodošli nazad! Prijavite se na svoj nalog.' : 'Započnite odmah! Kreirajte novi nalog.'}
          </p>
        </div>

        {/* GREŠKE */}
        <AnimatePresence mode="wait">
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0, y: -10 }}
              animate={{ opacity: 1, height: 'auto', y: 0 }}
              exit={{ opacity: 0, height: 0, y: -10 }}
              style={{
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.18)',
                borderRadius: '12px',
                padding: '12px 16px',
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: '#f87171',
                fontSize: '0.85rem',
                fontWeight: 500,
                overflow: 'hidden'
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* FORMA */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* EMAIL POLJE */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label
              htmlFor="email"
              style={{ color: '#d1d5db', fontSize: '0.85rem', fontWeight: 600, paddingLeft: '4px' }}
            >
              E-mail Adresa
            </label>
            <div style={{ position: 'relative' }}>
              <div
                style={{
                  position: 'absolute',
                  left: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#6b7280',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <Mail size={16} />
              </div>
              <input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ime@primer.com"
                style={{
                  width: '100%',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '12px',
                  padding: '12px 14px 12px 42px',
                  color: '#fff',
                  fontSize: '0.9rem',
                  outline: 'none',
                  transition: 'all 0.2s',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = 'rgba(139, 92, 246, 0.4)';
                  e.target.style.background = 'rgba(255, 255, 255, 0.05)';
                  e.target.style.boxShadow = '0 0 0 3px rgba(139, 92, 246, 0.15)';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                  e.target.style.background = 'rgba(255, 255, 255, 0.03)';
                  e.target.style.boxShadow = 'none';
                }}
              />
            </div>
          </div>

          {/* PASSWORD POLJE */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingLeft: '4px' }}>
              <label
                htmlFor="password"
                style={{ color: '#d1d5db', fontSize: '0.85rem', fontWeight: 600 }}
              >
                Lozinka
              </label>
            </div>
            <div style={{ position: 'relative' }}>
              <div
                style={{
                  position: 'absolute',
                  left: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#6b7280',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <KeyRound size={16} />
              </div>
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{
                  width: '100%',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '12px',
                  padding: '12px 42px 12px 42px',
                  color: '#fff',
                  fontSize: '0.9rem',
                  outline: 'none',
                  transition: 'all 0.2s',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = 'rgba(139, 92, 246, 0.4)';
                  e.target.style.background = 'rgba(255, 255, 255, 0.05)';
                  e.target.style.boxShadow = '0 0 0 3px rgba(139, 92, 246, 0.15)';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                  e.target.style.background = 'rgba(255, 255, 255, 0.03)';
                  e.target.style.boxShadow = 'none';
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '14px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#6b7280',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  padding: 0
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* DUGME ZA PODNOŠENJE */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              background: 'linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)',
              color: '#fff',
              border: 'none',
              borderRadius: '12px',
              padding: '14px',
              fontSize: '0.95rem',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'all 0.2s',
              boxShadow: '0 4px 15px rgba(139, 92, 246, 0.2)',
              marginTop: '10px',
              fontFamily: 'inherit'
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = '0 6px 20px rgba(139, 92, 246, 0.3)';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'none';
              e.currentTarget.style.boxShadow = '0 4px 15px rgba(139, 92, 246, 0.2)';
            }}
          >
            {loading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <span>Molimo sačekajte...</span>
              </>
            ) : (
              <span>{isLogin ? 'Prijavi se' : 'Registruj se'}</span>
            )}
          </button>
        </form>

        {/* PODNOŽJE (PREBACIVANJE REŽIMA) */}
        <div
          style={{
            textAlign: 'center',
            marginTop: '28px',
            fontSize: '0.85rem',
            color: '#9ca3af',
            fontWeight: 500
          }}
        >
          {isLogin ? 'Nemate nalog?' : 'Već imate nalog?'}
          <button
            onClick={toggleMode}
            style={{
              background: 'none',
              border: 'none',
              color: '#a78bfa',
              fontWeight: '700',
              cursor: 'pointer',
              marginLeft: '6px',
              padding: 0,
              fontFamily: 'inherit'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#c084fc';
              e.currentTarget.style.textDecoration = 'underline';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#a78bfa';
              e.currentTarget.style.textDecoration = 'none';
            }}
          >
            {isLogin ? 'Kreirajte nalog' : 'Prijavite se ovde'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

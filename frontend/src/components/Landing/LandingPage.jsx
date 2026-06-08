import { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, Mail, Loader2, CheckCircle2, Volume2, 
  Play, Pause, ArrowRight, Mic, Settings, Cpu, 
  Check, Lock, ShieldCheck, HelpCircle, AudioLines
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";

export default function LandingPage({ onEnterLogin }) {
  // Stanja za listu čekanja
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  // Stanja za audio demo mikser
  const [isPlaying, setIsPlaying] = useState(false);
  const [originalVolume, setOriginalVolume] = useState(70);
  const [dubbedVolume, setDubbedVolume] = useState(30);
  
  const audioEnRef = useRef(null);
  const audioSrRef = useRef(null);
  const syncIntervalRef = useRef(null);

  // Inicijalizacija audio objekata na klijentu
  useEffect(() => {
    audioEnRef.current = new Audio('/demo/demo_en.mp3');
    audioSrRef.current = new Audio('/demo/demo_sr.mp3');
    audioEnRef.current.loop = true;
    audioSrRef.current.loop = true;

    // Postavljanje početnog volumena
    audioEnRef.current.volume = originalVolume / 100;
    audioSrRef.current.volume = dubbedVolume / 100;

    return () => {
      if (audioEnRef.current) audioEnRef.current.pause();
      if (audioSrRef.current) audioSrRef.current.pause();
      if (syncIntervalRef.current) clearInterval(syncIntervalRef.current);
    };
  }, []);

  // Sinhronizacija jačine zvuka sa stanjem
  useEffect(() => {
    if (audioEnRef.current) {
      audioEnRef.current.volume = originalVolume / 100;
    }
  }, [originalVolume]);

  useEffect(() => {
    if (audioSrRef.current) {
      audioSrRef.current.volume = dubbedVolume / 100;
    }
  }, [dubbedVolume]);

  // Reprodukcija / pauza
  const handleTogglePlay = () => {
    if (!audioEnRef.current || !audioSrRef.current) return;

    if (isPlaying) {
      audioEnRef.current.pause();
      audioSrRef.current.pause();
      if (syncIntervalRef.current) {
        clearInterval(syncIntervalRef.current);
      }
    } else {
      // Kada krećemo ispočetka, resetujemo poziciju
      audioEnRef.current.currentTime = 0;
      audioSrRef.current.currentTime = 0;

      audioEnRef.current.play().catch(err => console.error("Greška pri puštanju EN audia:", err));
      audioSrRef.current.play().catch(err => console.error("Greška pri puštanju SR audia:", err));

      // Periodična resinhronizacija ako audio fajlovi pobegnu za više od 120ms
      syncIntervalRef.current = setInterval(() => {
        if (audioEnRef.current && audioSrRef.current) {
          const diff = Math.abs(audioEnRef.current.currentTime - audioSrRef.current.currentTime);
          if (diff > 0.12) {
            audioSrRef.current.currentTime = audioEnRef.current.currentTime;
          }
        }
      }, 400);
    }
    setIsPlaying(!isPlaying);
  };

  // Slanje forme za listu čekanja
  const handleWaitlistSubmit = async (e) => {
    e.preventDefault();
    if (!email) return;

    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/waitlist`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Došlo je do greške pri prijavi.');
      }

      setSuccess(true);
      setEmail('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Generiše talasiće za demo vizuelni mikser
  const renderWaveformBars = () => {
    const bars = [];
    for (let i = 0; i < 24; i++) {
      const height = isPlaying ? Math.floor(Math.random() * 35) + 5 : 4;
      bars.push(
        <div 
          key={i} 
          style={{
            width: '3px',
            height: `${height}px`,
            background: isPlaying ? 'linear-gradient(to top, #8b5cf6, #06b6d4)' : 'rgba(255,255,255,0.15)',
            borderRadius: '2px',
            transition: 'height 0.15s ease'
          }}
        />
      );
    }
    return bars;
  };

  return (
    <div style={{ color: '#fff', fontFamily: 'Outfit, Inter, sans-serif', overflowX: 'hidden' }}>
      
      {/* 1. ZAGLAVLJE (HEADER) */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '24px 5%',
        background: 'rgba(10, 15, 29, 0.4)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        position: 'sticky',
        top: 0,
        zIndex: 100
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '36px',
            height: '36px',
            background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(6, 182, 212, 0.2) 100%)',
            border: '1px solid rgba(139, 92, 246, 0.3)',
            borderRadius: '10px'
          }}>
            <Sparkles size={18} style={{ color: '#a78bfa' }} />
          </div>
          <span style={{ fontSize: '1.4rem', fontWeight: 900, background: 'linear-gradient(135deg, #c084fc 0%, #22d3ee 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', letterSpacing: '-0.5px' }}>
            sinhronizuj.me
          </span>
        </div>

        <button 
          onClick={onEnterLogin}
          style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: '8px 18px',
            borderRadius: '10px',
            color: '#cbd5e1',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s',
            fontFamily: 'inherit'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
            e.currentTarget.style.color = '#fff';
            e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.3)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
            e.currentTarget.style.color = '#cbd5e1';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)';
          }}
        >
          Prijava za članove
        </button>
      </header>

      {/* Pozadinske bleštve (Aurora) */}
      <div style={{ position: 'relative', width: '100%' }}>
        <div style={{
          position: 'absolute',
          top: '-150px',
          left: '15%',
          width: '500px',
          height: '500px',
          background: 'rgba(139, 92, 246, 0.15)',
          borderRadius: '50%',
          filter: 'blur(130px)',
          pointerEvents: 'none',
          zIndex: 1
        }} />
        <div style={{
          position: 'absolute',
          top: '150px',
          right: '10%',
          width: '400px',
          height: '400px',
          background: 'rgba(6, 182, 212, 0.1)',
          borderRadius: '50%',
          filter: 'blur(120px)',
          pointerEvents: 'none',
          zIndex: 1
        }} />

        {/* 2. HERO SEKCIJA */}
        <section style={{
          padding: '120px 5% 80px 5%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          position: 'relative',
          zIndex: 2,
          maxWidth: '900px',
          margin: '0 auto'
        }}>
          
          {/* Oznaka Zatvorena Beta */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(139, 92, 246, 0.1)',
            border: '1px solid rgba(139, 92, 246, 0.2)',
            padding: '6px 14px',
            borderRadius: '30px',
            color: '#c084fc',
            fontSize: '0.8rem',
            fontWeight: 700,
            marginBottom: '28px',
            textTransform: 'uppercase',
            letterSpacing: '1px'
          }}>
            <Lock size={12} />
            <span>Zatvoreno Beta Testiranje</span>
          </div>

          <h1 style={{
            fontSize: '3.6rem',
            fontWeight: 900,
            lineHeight: 1.1,
            letterSpacing: '-1.5px',
            margin: '0 0 24px 0',
            background: 'linear-gradient(to right, #ffffff, #e2e8f0, #94a3b8)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            Neka vaši video snimci progovore srpski — <span style={{ background: 'linear-gradient(135deg, #a78bfa 0%, #22d3ee 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>vašim glasom</span>
          </h1>

          <p style={{
            fontSize: '1.2rem',
            color: '#94a3b8',
            lineHeight: 1.6,
            maxWidth: '680px',
            margin: '0 0 40px 0',
            fontWeight: 500
          }}>
            Lokalizujte video sadržaje uz AI kloniranje glasa, automatsku lekturu i napredni DAW Studio editor direktno u pretraživaču. Prirodno, tačno i sinhronizovano na 44.1kHz.
          </p>

          {/* WAITLIST FORMA (HERO) */}
          <div style={{ width: '100%', maxWidth: '520px', margin: '0 auto 24px auto' }}>
            <AnimatePresence mode="wait">
              {success ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  style={{
                    background: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.2)',
                    borderRadius: '16px',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <CheckCircle2 size={32} className="text-emerald-400" />
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#34d399', margin: 0 }}>Uspešno ste se prijavili!</h3>
                  <p style={{ fontSize: '0.85rem', color: '#a7f3d0', margin: 0, textAlign: 'center' }}>
                    Nalazite se na listi čekanja za zatvorenu betu. Obavestićemo vas čim vam odobrimo pristup.
                  </p>
                </motion.div>
              ) : (
                <motion.form 
                  onSubmit={handleWaitlistSubmit}
                  style={{
                    display: 'flex',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.07)',
                    borderRadius: '16px',
                    padding: '6px',
                    gap: '8px',
                    boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
                    boxSizing: 'border-box'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', flex: 1, position: 'relative', paddingLeft: '14px' }}>
                    <Mail size={18} style={{ color: '#64748b', position: 'absolute', left: '14px' }} />
                    <input 
                      type="email" 
                      required
                      placeholder="Unesite vašu e-mail adresu..."
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={loading}
                      style={{
                        width: '100%',
                        background: 'transparent',
                        border: 'none',
                        outline: 'none',
                        color: '#fff',
                        fontSize: '0.95rem',
                        padding: '10px 10px 10px 32px',
                        fontFamily: 'inherit'
                      }}
                    />
                  </div>
                  <button 
                    type="submit" 
                    disabled={loading || !email}
                    className="glow-button"
                    style={{
                      background: 'linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '12px',
                      padding: '12px 24px',
                      fontSize: '0.9rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      transition: 'all 0.2s',
                      fontFamily: 'inherit',
                      boxShadow: '0 4px 15px rgba(139, 92, 246, 0.2)'
                    }}
                  >
                    {loading ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <>
                        Pridruži se beti <ArrowRight size={16} />
                      </>
                    )}
                  </button>
                </motion.form>
              )}
            </AnimatePresence>
            
            {error && (
              <div style={{
                color: '#f87171',
                fontSize: '0.85rem',
                marginTop: '12px',
                textAlign: 'left',
                paddingLeft: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <span>⚠️ {error}</span>
              </div>
            )}
          </div>

          <span style={{ fontSize: '0.8rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldCheck size={14} className="text-violet-500" /> Bez spama. Vaša e-mail adresa se čuva isključivo za pozivnice.
          </span>
        </section>

        {/* 3. INTERAKTIVNI LIVE DEMO (AUDIO MIKSER) */}
        <section style={{
          padding: '20px 5% 100px 5%',
          maxWidth: '1200px',
          margin: '0 auto',
          position: 'relative',
          zIndex: 2
        }}>
          <h2 style={{
            fontSize: '2rem',
            fontWeight: 800,
            textAlign: 'center',
            marginBottom: '48px',
            background: 'linear-gradient(to right, #fff, #94a3b8)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px'
          }}>
            <AudioLines className="text-cyan-400" /> Doživite AI Sinhronizaciju Uživo
          </h2>

          <div style={{
            background: 'rgba(15, 23, 42, 0.4)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            borderRadius: '24px',
            padding: '40px',
            boxShadow: '0 30px 60px -15px rgba(0, 0, 0, 0.6), 0 0 40px rgba(139, 92, 246, 0.02)',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '40px',
            alignItems: 'center'
          }} className="demo-grid">
            
            {/* Leva strana - Objašnjenje i plejer kontrola */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{
                background: 'rgba(6, 182, 212, 0.1)',
                border: '1px solid rgba(6, 182, 212, 0.2)',
                borderRadius: '8px',
                padding: '4px 10px',
                alignSelf: 'flex-start',
                fontSize: '0.75rem',
                color: '#22d3ee',
                fontWeight: 700,
                textTransform: 'uppercase'
              }}>
                Demonstracija u realnom vremenu
              </div>
              <h3 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0 }}>Kako zvuči klonirani glas?</h3>
              <p style={{ color: '#94a3b8', lineHeight: 1.6, fontSize: '0.95rem', margin: 0 }}>
                Kliknite na dugme za reprodukciju i pomerajte slajdere na desnoj strani. Možete potpuno utišati engleski original, pojačati srpski dubbing ili miksovati oba kanala kako biste se uverili u prirodnost glasa i studijski kvalitet obrade.
              </p>

              {/* Veliko dugme Play/Pause sa animiranim waveformom */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={handleTogglePlay}
                  style={{
                    width: '64px',
                    height: '64px',
                    borderRadius: '50%',
                    background: isPlaying ? 'linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%)' : 'linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)',
                    border: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    color: '#fff',
                    boxShadow: isPlaying ? '0 0 20px rgba(236, 72, 153, 0.4)' : '0 10px 20px rgba(139, 92, 246, 0.3)',
                    transition: 'all 0.25s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'scale(1.05)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'none';
                  }}
                >
                  {isPlaying ? <Pause size={28} fill="#fff" /> : <Play size={28} fill="#fff" style={{ marginLeft: '4px' }} />}
                </button>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 700 }}>
                    {isPlaying ? 'Zvuk je pokrenut' : 'Klikni za preslušavanje'}
                  </span>
                  <div style={{ display: 'flex', gap: '3px', alignItems: 'center', height: '40px' }}>
                    {renderWaveformBars()}
                  </div>
                </div>
              </div>
            </div>

            {/* Desna strana - Slajderi za miksovanje */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '20px',
              padding: '30px',
              display: 'flex',
              flexDirection: 'column',
              gap: '28px'
            }}>
              
              {/* Slajder 1: Originalna traka (Engleski) */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Volume2 size={16} className="text-slate-400" /> ORIGINALNI ENGLESKI VOKAL
                  </span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#cbd5e1' }}>{originalVolume}%</span>
                </div>
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={originalVolume}
                  onChange={(e) => setOriginalVolume(Number(e.target.value))}
                  style={{
                    width: '100%',
                    accentColor: '#64748b',
                    cursor: 'pointer',
                    height: '6px',
                    borderRadius: '3px'
                  }}
                />
              </div>

              {/* Slajder 2: Srpski AI Dubbing */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem', color: '#c084fc', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Mic size={16} style={{ color: '#a78bfa' }} /> KLONIRANI SRPSKI GLAS (AI DUB)
                  </span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#c084fc' }}>{dubbedVolume}%</span>
                </div>
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={dubbedVolume}
                  onChange={(e) => setDubbedVolume(Number(e.target.value))}
                  style={{
                    width: '100%',
                    accentColor: '#8b5cf6',
                    cursor: 'pointer',
                    height: '6px',
                    borderRadius: '3px'
                  }}
                />
              </div>

              {/* Objašnjenje harmonizacije i Resemble Enhance */}
              <div style={{ 
                marginTop: '10px',
                paddingTop: '20px', 
                borderTop: '1px solid rgba(255,255,255,0.05)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: isPlaying ? '#34d399' : '#64748b',
                  boxShadow: isPlaying ? '0 0 10px #34d399' : 'none'
                }} />
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  Audio se procesira lokalno u vašem pretraživaču. Bez kašnjenja.
                </span>
              </div>

            </div>

          </div>
        </section>

        {/* 4. KAKO RADI SEKCIJA */}
        <section style={{
          padding: '80px 5% 100px 5%',
          maxWidth: '1200px',
          margin: '0 auto',
          position: 'relative',
          zIndex: 2
        }}>
          <h2 style={{
            fontSize: '2.2rem',
            fontWeight: 900,
            textAlign: 'center',
            marginBottom: '60px',
            background: 'linear-gradient(to right, #ffffff, #cbd5e1)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            Sinhronizacija u 3 Jednostavna Koraka
          </h2>

          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '30px'
          }} className="steps-grid">
            
            {/* Korak 1 */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.01)',
              border: '1px solid rgba(255, 255, 255, 0.04)',
              borderRadius: '20px',
              padding: '35px 30px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}>
              <div style={{
                fontSize: '2.5rem',
                fontWeight: 900,
                color: 'rgba(139, 92, 246, 0.25)',
                position: 'absolute',
                top: '20px',
                right: '25px',
                lineHeight: 1
              }}>01</div>
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: 'rgba(139, 92, 246, 0.1)',
                border: '1px solid rgba(139, 92, 246, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#a78bfa'
              }}>
                <Cpu size={22} />
              </div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Analiza i Separacija</h3>
              <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: 1.6, margin: 0 }}>
                Naš AI sistem izdvaja vokale od pozadinske muzike (Demucs), vrši transkripciju reči (Whisper/SenseVoice) i generiše prevod uz vizuelni kontekst videa (Qwen2-VL).
              </p>
            </div>

            {/* Korak 2 */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.01)',
              border: '1px solid rgba(255, 255, 255, 0.04)',
              borderRadius: '20px',
              padding: '35px 30px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}>
              <div style={{
                fontSize: '2.5rem',
                fontWeight: 900,
                color: 'rgba(6, 182, 212, 0.25)',
                position: 'absolute',
                top: '20px',
                right: '25px',
                lineHeight: 1
              }}>02</div>
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: 'rgba(6, 182, 212, 0.1)',
                border: '1px solid rgba(6, 182, 212, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#22d3ee'
              }}>
                <Settings size={22} />
              </div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Lektura i DAW Editor</h3>
              <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: 1.6, margin: 0 }}>
                Korigujte prevod u realtime DAW editoru. Koristite "Čarobni štapić" AI Lektora da inteligentno skrati tekst kako bi stao u originalno trajanje govornog segmenta.
              </p>
            </div>

            {/* Korak 3 */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.01)',
              border: '1px solid rgba(255, 255, 255, 0.04)',
              borderRadius: '20px',
              padding: '35px 30px',
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}>
              <div style={{
                fontSize: '2.5rem',
                fontWeight: 900,
                color: 'rgba(236, 72, 153, 0.25)',
                position: 'absolute',
                top: '20px',
                right: '25px',
                lineHeight: 1
              }}>03</div>
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: 'rgba(236, 72, 153, 0.1)',
                border: '1px solid rgba(236, 72, 153, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ec4899'
              }}>
                <Volume2 size={22} />
              </div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Sinteza i Renderovanje</h3>
              <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: 1.6, margin: 0 }}>
                Sistem vrši prenos glasa iz originalnog audio snimka (OpenVoice V2) i spaja ga u finalni miks sa pozadinskom muzikom. Opcioni Wav2Lip sinhronizuje usne sa novim tonom.
              </p>
            </div>

          </div>
        </section>

        {/* 5. KARAKTERISTIKE SEKCIJA */}
        <section style={{
          padding: '80px 5% 100px 5%',
          maxWidth: '1200px',
          margin: '0 auto',
          position: 'relative',
          zIndex: 2
        }}>
          <h2 style={{
            fontSize: '2.2rem',
            fontWeight: 900,
            textAlign: 'center',
            marginBottom: '60px',
            background: 'linear-gradient(to right, #ffffff, #cbd5e1)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            Vrhunska Tehnologija za Studijski Kvalitet
          </h2>

          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '30px'
          }} className="features-grid">
            
            {/* Feature 1 */}
            <div className="glass-card" style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '20px',
              padding: '30px',
              display: 'flex',
              gap: '20px'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '14px',
                background: 'rgba(139, 92, 246, 0.1)',
                border: '1px solid rgba(139, 92, 246, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#a78bfa',
                flexShrink: 0
              }}>
                <Mic size={22} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Napredno Kloniranje Glasa</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: 1.6, margin: 0 }}>
                  Piper i OpenVoice V2 skeniraju boju i frekvenciju originalnog govornika i preslikavaju je na srpski jezik, zadržavajući jedinstveni identitet svakog glasa.
                </p>
              </div>
            </div>

            {/* Feature 2 */}
            <div className="glass-card" style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '20px',
              padding: '30px',
              display: 'flex',
              gap: '20px'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '14px',
                background: 'rgba(6, 182, 212, 0.1)',
                border: '1px solid rgba(6, 182, 212, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#22d3ee',
                flexShrink: 0
              }}>
                <Sparkles size={22} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Resemble Enhance (Denoise)</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: 1.6, margin: 0 }}>
                  Zaboravite na metalne i robotske glasove. CFM modeli podižu frekvenciju generisanog govora na 44.1kHz, uklanjajući šumove i dajući čist studijski zvuk.
                </p>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="glass-card" style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '20px',
              padding: '30px',
              display: 'flex',
              gap: '20px'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '14px',
                background: 'rgba(236, 72, 153, 0.1)',
                border: '1px solid rgba(236, 72, 153, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ec4899',
                flexShrink: 0
              }}>
                <Settings size={22} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Kompletan DAW Studio u letu</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: 1.6, margin: 0 }}>
                  Finopodesite tempo, volume i pitch po segmentu. Sa tehnologijom hot-patching splicinga preslušajte promene istog trenutka bez čekanja na renderovanje.
                </p>
              </div>
            </div>

            {/* Feature 4 */}
            <div className="glass-card" style={{
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '20px',
              padding: '30px',
              display: 'flex',
              gap: '20px'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '14px',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#10b981',
                flexShrink: 0
              }}>
                <Cpu size={22} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>Hibridna Snaga Cloud Serverless-a</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.88rem', lineHeight: 1.6, margin: 0 }}>
                  Stabilnost Hetzner VPS control plane-a kombinovana je sa serverless snagom GPU klastera na Modal.com (T4, L4, A10G) za instant AI proračune.
                </p>
              </div>
            </div>

          </div>
        </section>

        {/* 6. ZAVRŠNA SEKCIJA SA WAITLIST FORMOM I FOOTER */}
        <section style={{
          padding: '80px 5% 120px 5%',
          position: 'relative',
          zIndex: 2,
          maxWidth: '800px',
          margin: '0 auto',
          textAlign: 'center'
        }}>
          <div style={{
            background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(6, 182, 212, 0.05) 100%)',
            border: '1px solid rgba(139, 92, 246, 0.15)',
            borderRadius: '24px',
            padding: '60px 40px',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
          }}>
            <h2 style={{
              fontSize: '2.2rem',
              fontWeight: 900,
              margin: '0 0 16px 0',
              lineHeight: 1.2
            }}>
              Rezervišite Svoje Mesto u Ranoj Beti
            </h2>
            <p style={{
              color: '#94a3b8',
              fontSize: '1.05rem',
              lineHeight: 1.6,
              maxWidth: '580px',
              margin: '0 auto 40px auto'
            }}>
              Zatvorena beta ima ograničen broj mesta radi održavanja visokih performansi serverless GPU modela. Prijavite se odmah na listu čekanja.
            </p>

            {/* WAITLIST FORMA (DONJA) */}
            <div style={{ width: '100%', maxWidth: '480px', margin: '0 auto' }}>
              <AnimatePresence mode="wait">
                {success ? (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    style={{
                      background: 'rgba(16, 185, 129, 0.08)',
                      border: '1px solid rgba(16, 185, 129, 0.2)',
                      borderRadius: '16px',
                      padding: '20px',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <CheckCircle2 size={32} className="text-emerald-400" />
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#34d399', margin: 0 }}>Hvala vam na prijavi!</h3>
                    <p style={{ fontSize: '0.85rem', color: '#a7f3d0', margin: 0 }}>
                      Vaša e-mail adresa je uspešno sačuvana. Kontaktiraćemo vas uskoro.
                    </p>
                  </motion.div>
                ) : (
                  <motion.form 
                    onSubmit={handleWaitlistSubmit}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '16px'
                    }}
                  >
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      borderRadius: '14px',
                      padding: '12px 16px',
                      position: 'relative',
                      boxSizing: 'border-box'
                    }}>
                      <Mail size={18} style={{ color: '#64748b', position: 'absolute', left: '16px' }} />
                      <input 
                        type="email" 
                        required
                        placeholder="Unesite vašu e-mail adresu..."
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        disabled={loading}
                        style={{
                          width: '100%',
                          background: 'transparent',
                          border: 'none',
                          outline: 'none',
                          color: '#fff',
                          fontSize: '0.95rem',
                          paddingLeft: '32px',
                          fontFamily: 'inherit'
                        }}
                      />
                    </div>
                    
                    <button 
                      type="submit" 
                      disabled={loading || !email}
                      style={{
                        background: 'linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '14px',
                        padding: '14px 28px',
                        fontSize: '0.95rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        transition: 'all 0.2s',
                        fontFamily: 'inherit',
                        boxShadow: '0 4px 15px rgba(139, 92, 246, 0.2)'
                      }}
                    >
                      {loading ? (
                        <Loader2 size={18} className="animate-spin" />
                      ) : (
                        <>
                          Zatraži pristup beti <ArrowRight size={18} />
                        </>
                      )}
                    </button>
                  </motion.form>
                )}
              </AnimatePresence>

              {error && (
                <div style={{
                  color: '#f87171',
                  fontSize: '0.85rem',
                  marginTop: '12px',
                  textAlign: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}>
                  <span>⚠️ {error}</span>
                </div>
              )}
            </div>
          </div>

          {/* Footer informacije */}
          <footer style={{
            marginTop: '80px',
            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            paddingTop: '30px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.85rem',
            color: '#64748b'
          }}>
            <span>© 2026 sinhronizuj.me. Sva prava zadržana.</span>
            <div style={{ display: 'flex', gap: '20px' }}>
              <a href="https://github.com/Gruya13/daca_dub" target="_blank" rel="noreferrer" style={{ color: '#64748b', textDecoration: 'none', transition: 'color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.color = '#fff'} onMouseLeave={(e) => e.currentTarget.style.color = '#64748b'}>GitHub</a>
              <span style={{ cursor: 'pointer', transition: 'color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.color = '#fff'} onMouseLeave={(e) => e.currentTarget.style.color = '#64748b'} onClick={() => alert("Projekat je u fazi zatvorenog beta testiranja. Pristup imaju samo odobreni članovi.")}>Pravila korišćenja</span>
            </div>
          </footer>
        </section>

      </div>
    </div>
  );
}

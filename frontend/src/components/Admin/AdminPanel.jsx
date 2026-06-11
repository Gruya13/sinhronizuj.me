import { useState, useEffect } from 'react';
import { useStudio } from '../../context/StudioContext';
import { api } from '../../services/api';
import { 
  Users, Hourglass, DollarSign, Activity, FileVideo, 
  Settings, ShieldAlert, Trash2, Search, ArrowLeft, 
  ExternalLink, Loader2, Check, X, Shield, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function AdminPanel() {
  const { resetStudio, adminStats, fetchAdminStats } = useStudio();
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // Lokalna stanja za admin podatke
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [waitlist, setWaitlist] = useState([]);
  const [usersList, setUsersList] = useState([]);
  const [projectsList, setProjectsList] = useState([]);
  
  // Stanja za pretragu i filtere
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  
  // Detaljan pregled projekta (Modal)
  const [selectedProject, setSelectedProject] = useState(null);
  const [loadingProjectDetail, setLoadingProjectDetail] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      await fetchAdminStats(); // Osveži globalne metrike
      
      if (activeTab === 'waitlist') {
        const data = await api.getAdminWaitlist();
        setWaitlist(data);
      } else if (activeTab === 'users') {
        const data = await api.getAdminUsers();
        setUsersList(data);
      } else if (activeTab === 'projects') {
        const data = await api.getAdminProjects();
        setProjectsList(data);
      }
    } catch (err) {
      setError(err.message || 'Greška pri učitavanju podataka.');
    } finally {
      setLoading(false);
    }
  };

  // Učitavanje podataka u zavisnosti od aktivnog tab-a
  useEffect(() => {
    fetchData();
  }, [activeTab]);

  // Upravljanje Waitlistom
  const handleApproveWaitlist = async (id) => {
    try {
      await api.approveWaitlist(id);
      setWaitlist(prev => prev.map(item => item.id === id ? { ...item, status: 'approved' } : item));
      fetchAdminStats();
    } catch (err) {
      alert('Greška pri odobravanju: ' + err.message);
    }
  };

  const handleRejectWaitlist = async (id) => {
    try {
      await api.rejectWaitlist(id);
      setWaitlist(prev => prev.map(item => item.id === id ? { ...item, status: 'rejected' } : item));
      fetchAdminStats();
    } catch (err) {
      alert('Greška pri odbijanju: ' + err.message);
    }
  };

  // Upravljanje Korisnicima
  const handleToggleAdmin = async (userId, userEmail) => {
    if (!window.confirm(`Da li ste sigurni da želite da promenite administratorska prava za korisnika ${userEmail}?`)) {
      return;
    }
    try {
      const res = await api.toggleUserAdmin(userId);
      alert(res.message);
      setUsersList(prev => prev.map(u => u.id === userId ? { ...u, is_admin: !u.is_admin } : u));
    } catch (err) {
      alert('Greška: ' + err.message);
    }
  };

  // Pregled pojedinačnog projekta
  const handleViewProjectDetail = async (projectId) => {
    setLoadingProjectDetail(true);
    try {
      const data = await api.getAdminProjectDetail(projectId);
      setSelectedProject(data);
    } catch (err) {
      alert('Greška pri učitavanju detalja projekta: ' + err.message);
    } finally {
      setLoadingProjectDetail(false);
    }
  };

  // Filterisanje waitlist liste
  const filteredWaitlist = waitlist.filter(item => {
    const matchesSearch = item.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Filterisanje korisnika
  const filteredUsers = usersList.filter(u => 
    u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Filterisanje projekata
  const filteredProjects = projectsList.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          p.owner_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          p.video_title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="admin-panel-container" style={{ color: '#f8fafc', padding: '10px 0', display: 'flex', flexDirection: 'column', gap: '20px', height: '100%', overflow: 'hidden' }}>
      
      {/* ZAGLAVLJE SA DUGMETOM NAZAD */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button 
            onClick={resetStudio} 
            className="back-btn" 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              background: 'rgba(255,255,255,0.05)', 
              border: '1px solid rgba(255,255,255,0.1)', 
              borderRadius: '8px', 
              padding: '6px 12px', 
              color: '#fff', 
              cursor: 'pointer',
              fontSize: '0.85rem'
            }}
          >
            <ArrowLeft size={14} /> Nazad na Dashboard
          </button>
          <h2 style={{ fontSize: '1.4rem', fontWeight: '800', fontFamily: 'Outfit', margin: 0, background: 'linear-gradient(135deg, #c084fc 0%, #38bdf8 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Administracija Sistema
          </h2>
        </div>
        <button 
          onClick={fetchData} 
          disabled={loading} 
          style={{ 
            background: 'rgba(255,255,255,0.03)', 
            border: '1px solid rgba(255,255,255,0.08)', 
            borderRadius: '8px', 
            padding: '6px', 
            color: '#fff', 
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center'
          }}
          title="Osveži podatke"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* NAVIGACIJA TABOVA */}
      <div className="admin-tabs" style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
        {[
          { id: 'dashboard', label: 'Dashboard', icon: Activity },
          { id: 'waitlist', label: 'Waitlist', icon: Hourglass },
          { id: 'users', label: 'Korisnici', icon: Users },
          { id: 'projects', label: 'Projekti', icon: FileVideo }
        ].map(tab => {
          const IconComp = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: isActive ? 'rgba(139, 92, 246, 0.12)' : 'transparent',
                border: 'none',
                borderBottom: isActive ? '2px solid #a78bfa' : '2px solid transparent',
                padding: '8px 16px',
                color: isActive ? '#c084fc' : '#94a3b8',
                fontWeight: '600',
                fontSize: '0.85rem',
                fontFamily: 'Outfit',
                cursor: 'pointer',
                transition: 'all 0.15s',
                outline: 'none'
              }}
            >
              <IconComp size={14} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* SADRŽAJ AKTIVNOG TABA */}
      <div style={{ flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '12px', padding: '12px', color: '#f87171', fontSize: '0.85rem', marginBottom: '15px' }}>
            ⚠️ {error}
          </div>
        )}

        {/* TAB 1: DASHBOARD */}
        {activeTab === 'dashboard' && adminStats && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* KPI KARTICE */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
              
              <div className="glass-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '14px', padding: '16px', display: 'flex', alignItems: 'center', gap: '15px' }}>
                <div style={{ background: 'rgba(139, 92, 246, 0.15)', color: '#c084fc', borderRadius: '10px', padding: '10px' }}>
                  <Users size={20} />
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>Ukupno Korisnika</span>
                  <span style={{ fontSize: '1.4rem', fontWeight: '800', fontFamily: 'Outfit' }}>{adminStats.users.total}</span>
                </div>
              </div>

              <div className="glass-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '14px', padding: '16px', display: 'flex', alignItems: 'center', gap: '15px' }}>
                <div style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', borderRadius: '10px', padding: '10px' }}>
                  <Hourglass size={20} />
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>Na Waitlist-i (Pending)</span>
                  <span style={{ fontSize: '1.4rem', fontWeight: '800', fontFamily: 'Outfit' }}>
                    {adminStats.users.waitlist_pending} <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 'normal' }}>/ {adminStats.users.waitlist_total}</span>
                  </span>
                </div>
              </div>

              <div className="glass-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '14px', padding: '16px', display: 'flex', alignItems: 'center', gap: '15px' }}>
                <div style={{ background: 'rgba(6, 182, 212, 0.15)', color: '#06b6d4', borderRadius: '10px', padding: '10px' }}>
                  <FileVideo size={20} />
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>Ukupno Projekata</span>
                  <span style={{ fontSize: '1.4rem', fontWeight: '800', fontFamily: 'Outfit' }}>{adminStats.projects.total}</span>
                </div>
              </div>

              <div className="glass-card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '14px', padding: '16px', display: 'flex', alignItems: 'center', gap: '15px' }}>
                <div style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderRadius: '10px', padding: '10px' }}>
                  <DollarSign size={20} />
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'block' }}>Ukupni Troškovi</span>
                  <span style={{ fontSize: '1.4rem', fontWeight: '800', fontFamily: 'Outfit', color: '#34d399' }}>${adminStats.costs.total_usd.toFixed(2)}</span>
                </div>
              </div>

            </div>

            {/* STATUSI PROJEKATA I FINANSIJE */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
              
              {/* STATUSI PROJEKATA */}
              <div className="glass-card" style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '16px', padding: '20px' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '700', fontFamily: 'Outfit', marginBottom: '15px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '8px' }}>
                  Statusi Projekata u Bazi
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {[
                    { key: 'completed', label: 'Završeni', color: '#10b981' },
                    { key: 'ready', label: 'Studio (Spremni)', color: '#8b5cf6' },
                    { key: 'analyzing', label: 'Analiziraju se', color: '#06b6d4' },
                    { key: 'empty', label: 'Kreirani / Prazni', color: '#64748b' },
                    { key: 'failed', label: 'Neuspešni (Failed)', color: '#ef4444' }
                  ].map(item => {
                    const count = adminStats.projects.by_status[item.key] || 0;
                    const total = adminStats.projects.total || 1;
                    const percent = Math.round((count / total) * 100);
                    return (
                      <div key={item.key}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: item.color }} />
                            {item.label}
                          </span>
                          <span style={{ fontWeight: 'bold' }}>{count} ({percent}%)</span>
                        </div>
                        <div style={{ height: '6px', background: 'rgba(255,255,255,0.03)', borderRadius: '3px' }}>
                          <div style={{ height: '100%', background: item.color, borderRadius: '3px', width: `${percent}%` }}></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* DETALJNI TROŠKOVI PO AI FAZAMA */}
              <div className="glass-card" style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '16px', padding: '20px' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '700', fontFamily: 'Outfit', marginBottom: '15px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '8px' }}>
                  Podela Troškova po Fazama obrade
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {[
                    { key: 'separation', label: 'Izolacija vokala (Demucs T4)', color: '#a78bfa' },
                    { key: 'transcription', label: 'Transkripcija (Whisper T4)', color: '#38bdf8' },
                    { key: 'translation', label: 'Prevođenje (Qwen2-VL A10G)', color: '#06b6d4' },
                    { key: 'lektor', label: 'Lektura (Qwen-32B AWQ)', color: '#fb7185' },
                    { key: 'tts', label: 'Sinteza govora (OpenVoice L4)', color: '#f59e0b' },
                    { key: 'lipsync', label: 'LipSync (Wav2Lip)', color: '#10b981' }
                  ].map(item => {
                    const cost = adminStats.costs.by_phase[item.key] || 0.0;
                    const total = adminStats.costs.total_usd || 1.0;
                    const percent = Math.round((cost / total) * 100) || 0;
                    return (
                      <div key={item.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', padding: '6px 8px', background: 'rgba(255,255,255,0.01)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: item.color }} />
                          {item.label}
                        </span>
                        <span style={{ fontWeight: '700', color: '#cbd5e1' }}>
                          ${cost.toFixed(3)} <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 'normal' }}>({percent}%)</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>

          </div>
        )}

        {/* TAB 2: WAITLIST */}
        {activeTab === 'waitlist' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            
            {/* KONTROLE PRETRAGE */}
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <div style={{ position: 'relative', flex: 1, minWidth: '200px' }}>
                <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
                <input
                  type="text"
                  placeholder="Pretraži waitlist email..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '10px',
                    padding: '8px 12px 8px 36px',
                    color: '#fff',
                    outline: 'none',
                    fontSize: '0.85rem'
                  }}
                />
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '10px',
                  padding: '8px 16px',
                  color: '#fff',
                  outline: 'none',
                  fontSize: '0.85rem',
                  cursor: 'pointer'
                }}
              >
                <option value="all" style={{ background: '#0f172a' }}>Svi Statusi</option>
                <option value="pending" style={{ background: '#0f172a' }}>Na Čekanju (Pending)</option>
                <option value="approved" style={{ background: '#0f172a' }}>Odobreni</option>
                <option value="rejected" style={{ background: '#0f172a' }}>Odbijeni</option>
              </select>
            </div>

            {/* TABELA */}
            <div style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '14px', overflow: 'hidden' }}>
              {loading && waitlist.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center' }}><Loader2 className="animate-spin" style={{ margin: '0 auto' }} /></div>
              ) : filteredWaitlist.length === 0 ? (
                <div style={{ padding: '30px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>Nema pronađenih prijava.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Email adresa</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Datum prijave</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Status</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8', textAlign: 'right' }}>Akcije</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredWaitlist.map((item) => (
                      <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.2s' }} className="hover:bg-white/5">
                        <td style={{ padding: '12px 16px', fontWeight: '600' }}>{item.email}</td>
                        <td style={{ padding: '12px 16px', color: '#64748b' }}>{new Date(item.created_at).toLocaleDateString('sr-RS')}</td>
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '6px',
                            fontSize: '0.75rem',
                            fontWeight: 'bold',
                            background: item.status === 'approved' ? 'rgba(16, 185, 129, 0.15)' : item.status === 'rejected' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                            color: item.status === 'approved' ? '#34d399' : item.status === 'rejected' ? '#f87171' : '#fbbf24'
                          }}>
                            {item.status === 'approved' ? 'Odobren' : item.status === 'rejected' ? 'Odbijen' : 'Na čekanju'}
                          </span>
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                          {item.status === 'pending' && (
                            <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                              <button
                                onClick={() => handleApproveWaitlist(item.id)}
                                style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', color: '#34d399', borderRadius: '6px', padding: '4px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
                              >
                                <Check size={12} /> Odobri
                              </button>
                              <button
                                onClick={() => handleRejectWaitlist(item.id)}
                                style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#f87171', borderRadius: '6px', padding: '4px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
                              >
                                <X size={12} /> Odbij
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

          </div>
        )}

        {/* TAB 3: KORISNICI */}
        {activeTab === 'users' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            
            {/* PRETRAGA */}
            <div style={{ position: 'relative' }}>
              <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
              <input
                type="text"
                placeholder="Pretraži registrovane korisnike po email-u..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '10px',
                  padding: '8px 12px 8px 36px',
                  color: '#fff',
                  outline: 'none',
                  fontSize: '0.85rem'
                }}
              />
            </div>

            {/* TABELA */}
            <div style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '14px', overflow: 'hidden' }}>
              {loading && usersList.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center' }}><Loader2 className="animate-spin" style={{ margin: '0 auto' }} /></div>
              ) : filteredUsers.length === 0 ? (
                <div style={{ padding: '30px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>Nema registrovanih korisnika.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Email adresa</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Registrovan</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Uloga</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8', textAlign: 'center' }}>Projekti</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Ukupni troškovi</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8', textAlign: 'right' }}>Akcije</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((item) => (
                      <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '12px 16px', fontWeight: '600' }}>{item.email}</td>
                        <td style={{ padding: '12px 16px', color: '#64748b' }}>{new Date(item.created_at).toLocaleDateString('sr-RS')}</td>
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '6px',
                            fontSize: '0.75rem',
                            fontWeight: 'bold',
                            background: item.is_admin ? 'rgba(167, 139, 250, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                            color: item.is_admin ? '#c084fc' : '#94a3b8',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}>
                            {item.is_admin ? <Shield size={10} /> : null}
                            {item.is_admin ? 'Admin' : 'Korisnik'}
                          </span>
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 'bold' }}>{item.projects_count}</td>
                        <td style={{ padding: '12px 16px', fontWeight: '700', color: '#34d399' }}>${item.total_costs_usd.toFixed(3)}</td>
                        <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                          <button
                            onClick={() => handleToggleAdmin(item.id, item.email)}
                            style={{
                              background: 'transparent',
                              border: '1px solid rgba(255,255,255,0.1)',
                              color: '#cbd5e1',
                              borderRadius: '6px',
                              padding: '4px 8px',
                              cursor: 'pointer',
                              fontSize: '0.75rem',
                              transition: 'all 0.15s'
                            }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                          >
                            Promeni rolu
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

          </div>
        )}

        {/* TAB 4: PROJEKTI */}
        {activeTab === 'projects' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            
            {/* KONTROLE PRETRAGE */}
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <div style={{ position: 'relative', flex: 1, minWidth: '200px' }}>
                <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
                <input
                  type="text"
                  placeholder="Pretraži projekte (naziv, korisnik)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '10px',
                    padding: '8px 12px 8px 36px',
                    color: '#fff',
                    outline: 'none',
                    fontSize: '0.85rem'
                  }}
                />
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '10px',
                  padding: '8px 16px',
                  color: '#fff',
                  outline: 'none',
                  fontSize: '0.85rem',
                  cursor: 'pointer'
                }}
              >
                <option value="all" style={{ background: '#0f172a' }}>Svi Statusi</option>
                <option value="completed" style={{ background: '#0f172a' }}>Završeni</option>
                <option value="ready" style={{ background: '#0f172a' }}>Studio (Spremni)</option>
                <option value="analyzing" style={{ background: '#0f172a' }}>U obradi</option>
                <option value="empty" style={{ background: '#0f172a' }}>Prazni</option>
                <option value="failed" style={{ background: '#0f172a' }}>Neuspešni</option>
              </select>
            </div>

            {/* TABELA */}
            <div style={{ background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '14px', overflow: 'hidden' }}>
              {loading && projectsList.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center' }}><Loader2 className="animate-spin" style={{ margin: '0 auto' }} /></div>
              ) : filteredProjects.length === 0 ? (
                <div style={{ padding: '30px', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>Nema pronađenih projekata.</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Projekat</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Korisnik</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Status</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Kreiran</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8' }}>Cena obrade</th>
                      <th style={{ padding: '12px 16px', color: '#94a3b8', textAlign: 'right' }}>Detalji</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProjects.map((item) => {
                      let statusColor = '#94a3b8';
                      if (item.status === 'completed') statusColor = '#10b981';
                      else if (item.status === 'ready') statusColor = '#8b5cf6';
                      else if (item.status === 'analyzing') statusColor = '#06b6d4';
                      else if (item.status === 'failed') statusColor = '#ef4444';

                      return (
                        <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '12px 16px' }}>
                            <span style={{ fontWeight: '700', display: 'block' }}>{item.name}</span>
                            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{item.video_title || 'Video bez naslova'}</span>
                          </td>
                          <td style={{ padding: '12px 16px', color: '#cbd5e1' }}>{item.owner_email}</td>
                          <td style={{ padding: '12px 16px' }}>
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '5px',
                              fontSize: '0.75rem',
                              fontWeight: 'bold',
                              color: statusColor
                            }}>
                              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: statusColor }} />
                              {item.status.toUpperCase()}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', color: '#64748b' }}>{new Date(item.created_at).toLocaleDateString('sr-RS')}</td>
                          <td style={{ padding: '12px 16px', fontWeight: '700', color: '#34d399' }}>${item.total_cost_usd.toFixed(3)}</td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                            <button
                              onClick={() => handleViewProjectDetail(item.id)}
                              style={{
                                background: 'rgba(139, 92, 246, 0.1)',
                                border: '1px solid rgba(139, 92, 246, 0.2)',
                                color: '#c084fc',
                                borderRadius: '6px',
                                padding: '4px 8px',
                                cursor: 'pointer',
                                fontSize: '0.75rem'
                              }}
                            >
                              Pregledaj
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

          </div>
        )}
      </div>

      {/* MODAL ZA DETALJAN PREGLED PROJEKTA */}
      <AnimatePresence>
        {selectedProject && (
          <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10000, padding: '20px' }}>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              style={{
                background: '#0b0f19',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '16px',
                width: '100%',
                maxWidth: '900px',
                maxHeight: '90%',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxShadow: '0 20px 50px rgba(0,0,0,0.6)'
              }}
            >
              {/* ZAGLAVLJE MODALA */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: '800', fontFamily: 'Outfit', margin: 0 }}>
                    {selectedProject.name} <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 'normal' }}>({selectedProject.id.slice(0, 8)})</span>
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Vlasnik: {selectedProject.owner_email}</span>
                </div>
                <button 
                  onClick={() => setSelectedProject(null)}
                  style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
                >
                  <X size={18} />
                </button>
              </div>

              {/* SADRŽAJ MODALA */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                
                {/* STATUSI I FAZE */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
                  
                  {/* METAPODACI */}
                  <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '12px', fontSize: '0.8rem' }}>
                    <span style={{ color: '#64748b', display: 'block', marginBottom: '8px' }}>Detalji</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Status:</span>
                        <span style={{ fontWeight: 'bold' }}>{selectedProject.status.toUpperCase()}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Kreiran:</span>
                        <span>{new Date(selectedProject.created_at).toLocaleDateString('sr-RS')}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>Broj segmenata:</span>
                        <span>{selectedProject.segments?.length || 0}</span>
                      </div>
                    </div>
                  </div>

                  {/* S3 SKLADIŠTE RESURSI */}
                  <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '12px', fontSize: '0.8rem' }}>
                    <span style={{ color: '#64748b', display: 'block', marginBottom: '8px' }}>S3 Cloud Resursi</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {selectedProject.video_url && (
                        <a href={selectedProject.video_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          Originalni Video <ExternalLink size={10} />
                        </a>
                      )}
                      {selectedProject.vocals_url && (
                        <a href={selectedProject.vocals_url} target="_blank" rel="noreferrer" style={{ color: '#c084fc', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          Izolovani Vokal <ExternalLink size={10} />
                        </a>
                      )}
                      {selectedProject.final_video_url && (
                        <a href={selectedProject.final_video_url} target="_blank" rel="noreferrer" style={{ color: '#10b981', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 'bold' }}>
                          Finalni Sinhronizovani Video <ExternalLink size={10} />
                        </a>
                      )}
                    </div>
                  </div>

                </div>

                {/* DETALJNI LOGOVI GREŠAKA ILI PROCESA */}
                <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '15px' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: '700', margin: '0 0 10px 0', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Logovi i Praćenje Grešaka (worker.log)</span>
                    {selectedProject.status === 'failed' && <span style={{ color: '#ef4444', fontWeight: 'bold' }}>FAILED TASK</span>}
                  </h4>
                  <div style={{
                    maxHeight: '180px',
                    overflowY: 'auto',
                    background: '#05070c',
                    border: '1px solid rgba(255,255,255,0.04)',
                    borderRadius: '8px',
                    padding: '10px',
                    fontSize: '0.75rem',
                    fontFamily: 'monospace',
                    color: '#a3e635',
                    whiteSpace: 'pre-wrap',
                    textAlign: 'left'
                  }}>
                    {selectedProject.logs && selectedProject.logs.length > 0 ? (
                      selectedProject.logs.join('\n')
                    ) : (
                      <span style={{ color: '#64748b', fontStyle: 'italic' }}>Nema zabeleženih logova za ovaj projekat.</span>
                    )}
                  </div>
                </div>

                {/* SEGMENTI PREVODA */}
                <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '15px' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: '700', margin: '0 0 10px 0', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '4px' }}>
                    Segmenti i Prevodi ({selectedProject.segments?.length || 0})
                  </h4>
                  <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid rgba(255,255,255,0.04)', borderRadius: '8px' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', textAlign: 'left' }}>
                      <thead>
                        <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                          <th style={{ padding: '8px 12px', color: '#94a3b8' }}>Vreme</th>
                          <th style={{ padding: '8px 12px', color: '#94a3b8' }}>Original (Engleski)</th>
                          <th style={{ padding: '8px 12px', color: '#94a3b8' }}>Prevod (Srpski)</th>
                          <th style={{ padding: '8px 12px', color: '#94a3b8' }}>Glas</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedProject.segments?.map((seg) => (
                          <tr key={seg.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                            <td style={{ padding: '8px 12px', color: '#64748b' }}>{seg.start.toFixed(1)}s - {seg.end.toFixed(1)}s</td>
                            <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>{seg.original}</td>
                            <td style={{ padding: '8px 12px', color: '#fff', fontWeight: 'bold' }}>{seg.translated}</td>
                            <td style={{ padding: '8px 12px', color: '#c084fc' }}>{seg.voice_type}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

              </div>

              {/* PODNOŽJE MODALA */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 20px', borderTop: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.01)' }}>
                <button
                  onClick={() => setSelectedProject(null)}
                  style={{
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '8px',
                    padding: '6px 16px',
                    color: '#fff',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    fontFamily: 'Outfit'
                  }}
                >
                  Zatvori
                </button>
              </div>

            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}

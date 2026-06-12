import { motion, AnimatePresence } from 'framer-motion';
import { Paperclip, ArrowRight, Play } from 'lucide-react';
import { useStudio } from '../../context/StudioContext';
import ProjectList from './ProjectList';

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";

export default function DashboardView() {
  const {
    showProjectsList,
    newProjectName, setNewProjectName,
    isCreateModalOpen, setIsCreateModalOpen,
    creatingProject,
    loading,
    uploadProgress,
    uploadState,
    previewFile,
    resetStudio,
    handleCreateProject,
    handleLoadUrl,
    handleSubmit,
    handleFileUpload,
    fileInputRef,
    url, setUrl
  } = useStudio();

  return (
    <>
      <AnimatePresence mode="wait">
        {/* DASHBOARD: LISTA PROJEKATA */}
        {showProjectsList && !previewFile && (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
          >
            <ProjectList />
          </motion.div>
        )}

        {/* FAZA 0: UNOS VIDEA */}
        {!showProjectsList && !previewFile && (
          <motion.div
            key="input-area"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="input-area" 
            style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.95rem', color: '#94a3b8', fontWeight: '600' }}>Učitaj video za obradu</span>
              <button onClick={resetStudio} className="back-btn" style={{ padding: '5px 12px', borderRadius: '8px', fontSize: '0.8rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer' }}>
                Nazad na projekte
              </button>
            </div>
            <form onSubmit={handleLoadUrl} className="input-group main-input">
              <div className="input-wrapper">
                <input 
                  type="url" placeholder="Zalepite YouTube ili S3 link..." 
                  value={url} onChange={(e) => setUrl(e.target.value)}
                  disabled={loading} required
                />
                <button 
                  type="button" 
                  className="icon-btn" 
                  onClick={() => fileInputRef.current.click()}
                  title="Uploaduj lokalni video"
                >
                  <Paperclip size={20} />
                </button>
                <button type="submit" disabled={loading || !url} className="glow-button">
                  <ArrowRight size={20} /> Učitaj video
                </button>
              </div>
            </form>
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: 'none' }} 
              accept="video/*" 
              onChange={handleFileUpload}
            />
            <p className="upload-hint">Podržani formati: MP4, WebM, MKV. Maksimalno 500MB.</p>
          </motion.div>
        )}

        {/* PREVIEW NAKON UČITAVANJA PRE ANALIZE */}
        {previewFile && (
          <motion.div
            key="preview-pane"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.25 }}
            className="preview-pane-container"
          >
            <div className="preview-video-wrapper">
              {previewFile.type === "youtube" ? (
                <iframe src={previewFile.url} className="preview-media" allowFullScreen title="YouTube Preview"/>
              ) : (
                <video src={previewFile.url} controls className="preview-media" />
              )}
            </div>

            <div className="preview-details-panel">
              <div>
                <h3 className="preview-title" style={{ fontSize: '1.25rem', fontWeight: '700', marginBottom: '8px' }}>Priprema za Analizu (Faza 1)</h3>
                <p className="text-sm text-slate-400 mb-6" style={{ marginBottom: '24px', color: '#94a3b8', fontSize: '0.9rem' }}>
                  Video je uspešno učitan. Prvi korak će analizirati video, izdvojiti audio trake, transkribovati govor na engleskom i kreirati prvi prevod.
                </p>
                
                <div className="file-info-list" style={{ background: 'rgba(0,0,0,0.15)', borderRadius: '12px', padding: '15px', display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
                  <div className="file-info-item" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: '#64748b' }}>Naziv:</span>
                    <span style={{ fontWeight: '600' }}>{previewFile.name}</span>
                  </div>
                  <div className="file-info-item" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: '#64748b' }}>Izvor:</span>
                    <span style={{ fontWeight: '600' }}>{previewFile.type === "local" ? "Lokalni Upload" : "Mrežni URL"}</span>
                  </div>
                </div>
              </div>

              {previewFile.type === "local" && (
                <div className="upload-status-box" style={{ background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '20px' }}>
                  <div className="status-text-row" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span>S3 Transfer:</span>
                    <span style={{ color: uploadState === 'completed' ? '#4ade80' : '#38bdf8', fontWeight: 'bold' }}>
                      {uploadState === 'uploading' ? `Slanje (${uploadProgress}%)` : 'Završeno'}
                    </span>
                  </div>
                </div>
              )}

              <div className="preview-actions-row" style={{ display: 'flex', gap: '12px', marginTop: 'auto' }}>
                <button onClick={resetStudio} className="back-btn" style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '12px', borderRadius: '12px', cursor: 'pointer' }}>
                  Nazad
                </button>
                <button 
                  onClick={handleSubmit} 
                  disabled={previewFile.type === "local" && uploadState !== "completed"} 
                  className="glow-button"
                  style={{ flex: 2, justifyContent: 'center' }}
                >
                  <Play size={18} /> Započni Analizu
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* MODAL ZA KREIRANJE PROJEKTA */}
      <AnimatePresence>
        {isCreateModalOpen && (
          <div 
            style={{ 
              position: 'fixed', 
              top: 0, 
              left: 0, 
              width: '100vw', 
              height: '100vh', 
              background: 'rgba(0,0,0,0.6)', 
              backdropFilter: 'blur(8px)', 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center', 
              zIndex: 9999 
            }}
            onClick={() => setIsCreateModalOpen(false)}
          >
            <div 
              style={{ 
                background: 'rgba(25, 28, 41, 0.95)', 
                border: '1px solid rgba(255,255,255,0.1)', 
                borderRadius: '24px', 
                padding: '30px', 
                width: '90%', 
                maxWidth: '400px',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
                boxShadow: '0 20px 40px rgba(0,0,0,0.5)'
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <h3 style={{ fontSize: '1.25rem', fontWeight: '700', color: '#f1f5f9' }}>Novi Projekat</h3>
              <form onSubmit={handleCreateProject} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Naziv projekta</label>
                  <input 
                    type="text" 
                    placeholder="npr. Sinhronizacija AI Agent"
                    value={newProjectName} 
                    onChange={(e) => setNewProjectName(e.target.value)}
                    style={{ 
                      width: '100%', 
                      background: 'rgba(255,255,255,0.05)', 
                      border: '1px solid rgba(255,255,255,0.1)', 
                      borderRadius: '12px', 
                      padding: '12px', 
                      color: '#fff', 
                      fontSize: '0.95rem',
                      outline: 'none'
                    }}
                    autoFocus
                    required
                    disabled={creatingProject}
                  />
                </div>

                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '10px' }}>
                  <button 
                    type="button" 
                    onClick={() => setIsCreateModalOpen(false)}
                    style={{ 
                      background: 'rgba(255,255,255,0.05)', 
                      border: '1px solid rgba(255,255,255,0.1)', 
                      color: '#fff', 
                      padding: '10px 18px', 
                      borderRadius: '12px',
                      cursor: 'pointer',
                      fontSize: '0.9rem'
                    }}
                    disabled={creatingProject}
                  >
                    Otkaži
                  </button>
                  <button 
                    type="submit" 
                    className="glow-button"
                    style={{ padding: '10px 18px', borderRadius: '12px', fontSize: '0.9rem' }}
                    disabled={creatingProject}
                  >
                    {creatingProject ? "Kreiranje..." : "Kreiraj projekat"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}

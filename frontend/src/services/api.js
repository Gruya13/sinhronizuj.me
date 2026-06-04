const API_BASE_URL = import.meta.env.VITE_API_URL || "http://178.104.214.78:8000";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Pomoćna funkcija za obradu HTTP odgovora.
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = "Greška na serveru";
    try {
      const data = await response.json();
      if (data && data.detail) {
        errorDetail = data.detail;
      } else if (data && data.message) {
        errorDetail = data.message;
      }
    } catch (_) {
      // ignorisi gresku parsiranja JSON-a
    }
    throw new ApiError(errorDetail, response.status);
  }
  return response.json();
}

/**
 * Pomoćni omotač za fetch koji automatski dodaje JWT token u zaglavlje.
 */
async function authFetch(url, options = {}) {
  const token = localStorage.getItem('sinhronizuj_me_token');
  options.headers = options.headers || {};
  
  if (token) {
    options.headers['Authorization'] = `Bearer ${token}`;
  }
  
  const res = await fetch(url, options);
  
  if (res.status === 401) {
    localStorage.removeItem('sinhronizuj_me_token');
    // Bacamo izuzetak koji će biti uhvaćen na frontendu
    throw new ApiError("Sesija je istekla. Molimo prijavite se ponovo.", 401);
  }
  
  return handleResponse(res);
}

export const api = {
  /**
   * Prijava korisnika.
   */
  async login(email, password) {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await handleResponse(res);
    if (data.access_token) {
      localStorage.setItem('sinhronizuj_me_token', data.access_token);
    }
    return data;
  },

  /**
   * Registracija korisnika.
   */
  async register(email, password) {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    return handleResponse(res);
  },

  /**
   * Dobavljanje trenutno prijavljenog korisnika.
   */
  async getMe() {
    return authFetch(`${API_BASE_URL}/api/v1/auth/me`);
  },

  /**
   * Izlistava sve projekte koji pripadaju korisniku.
   */
  async getProjects() {
    return authFetch(`${API_BASE_URL}/api/v1/projects`);
  },

  /**
   * Dobavlja statistiku hardvera VPS-a.
   */
  async getHwStats() {
    return authFetch(`${API_BASE_URL}/api/v1/hw-stats`);
  },

  /**
   * Dobavlja status Modal.com radnika.
   */
  async getModalStatus() {
    return authFetch(`${API_BASE_URL}/api/v1/modal-status`);
  },

  /**
   * Dobavlja status određenog Celery zadatka (task-a).
   */
  async getTaskStatus(taskId) {
    return authFetch(`${API_BASE_URL}/api/v1/status/${taskId}`);
  },

  /**
   * Učitava podatke o specifičnom projektu iz baze.
   */
  async getProject(projectId) {
    return authFetch(`${API_BASE_URL}/api/v1/project/${projectId}`);
  },

  /**
   * Briše kompletnu Redis bazu (čišćenje).
   */
  async flushRedis() {
    return authFetch(`${API_BASE_URL}/api/v1/redis/flush`, { method: 'POST' });
  },

  /**
   * Kreira novi prazan projekat.
   */
  async createProject(name) {
    return authFetch(`${API_BASE_URL}/api/v1/project`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
  },

  /**
   * Briše projekat i sve njegove povezane fajlove.
   */
  async deleteProject(projectId) {
    return authFetch(`${API_BASE_URL}/api/v1/project/${projectId}`, {
      method: 'DELETE'
    });
  },

  /**
   * Pokreće Fazu 1 (Analiza videa).
   */
  async processVideo(url, projectId) {
    return authFetch(`${API_BASE_URL}/api/v1/process-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        url, 
        debug: false,
        project_id: projectId
      })
    });
  },

  /**
   * Dobavlja presigned URL za upload lokalnog fajla na MinIO.
   */
  async getUploadUrl(filename, contentType) {
    return authFetch(
      `${API_BASE_URL}/api/v1/storage/upload_url?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`
    );
  },

  /**
   * Poziva AI lektora da skrati tekst segmenta.
   */
  async shortenSegment(projectId, segmentId, text) {
    return authFetch(`${API_BASE_URL}/api/v1/project/${projectId}/segment/${segmentId}/shorten`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
  },

  /**
   * Čuva najnoviji nacrt (draft) segmenata na serveru.
   */
  async saveProjectDraft(projectId, segments) {
    return authFetch(`${API_BASE_URL}/api/v1/project/${projectId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segments })
    });
  },

  /**
   * Generiše TTS za pojedinačni segment sa zadatim audio modifikatorima.
   */
  async generateSegmentTTS(projectId, segmentId, text, voiceType, volume, speed, pitch, bgVolume) {
    return authFetch(`${API_BASE_URL}/api/v1/project/${projectId}/segment/${segmentId}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        voice_type: voiceType,
        volume,
        speed,
        pitch,
        bg_volume: bgVolume
      })
    });
  },

  /**
   * Generiše TTS glasove za sve segmente u projektu odjednom.
   */
  async generateAllTTS(projectId, voiceType) {
    return authFetch(`${API_BASE_URL}/api/v1/project/${projectId}/generate-all-tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice_type: voiceType })
    });
  },

  /**
   * Pokreće Fazu 2 (Renderovanje finalnog videa).
   */
  async renderProject(projectId, voiceType, backgroundVolume, dubbedVolume) {
    return authFetch(`${API_BASE_URL}/api/v1/project/${projectId}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        voice_type: voiceType,
        background_volume: backgroundVolume,
        dubbed_volume: dubbedVolume
      })
    });
  }
};

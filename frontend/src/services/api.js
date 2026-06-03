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
    } catch (_) {}
    throw new ApiError(errorDetail, response.status);
  }
  return response.json();
}

export const api = {
  /**
   * Izlistava sve projekte.
   */
  async getProjects() {
    const res = await fetch(`${API_BASE_URL}/api/v1/projects`);
    return handleResponse(res);
  },

  /**
   * Dobavlja statistiku hardvera VPS-a.
   */
  async getHwStats() {
    const res = await fetch(`${API_BASE_URL}/api/v1/hw-stats`);
    return handleResponse(res);
  },

  /**
   * Dobavlja status Modal.com radnika.
   */
  async getModalStatus() {
    const res = await fetch(`${API_BASE_URL}/api/v1/modal-status`);
    return handleResponse(res);
  },

  /**
   * Dobavlja status određenog Celery zadatka (task-a).
   */
  async getTaskStatus(taskId) {
    const res = await fetch(`${API_BASE_URL}/api/v1/status/${taskId}`);
    return handleResponse(res);
  },

  /**
   * Učitava podatke o specifičnom projektu iz baze.
   */
  async getProject(projectId) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project/${projectId}`);
    return handleResponse(res);
  },

  /**
   * Briše kompletnu Redis bazu (čišćenje).
   */
  async flushRedis() {
    const res = await fetch(`${API_BASE_URL}/api/v1/redis/flush`, { method: 'POST' });
    return handleResponse(res);
  },

  /**
   * Kreira novi prazan projekat.
   */
  async createProject(name) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    return handleResponse(res);
  },

  /**
   * Briše projekat i sve njegove povezane fajlove.
   */
  async deleteProject(projectId) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project/${projectId}`, {
      method: 'DELETE'
    });
    return handleResponse(res);
  },

  /**
   * Pokreće Fazu 1 (Analiza videa).
   */
  async processVideo(url, projectId) {
    const res = await fetch(`${API_BASE_URL}/api/v1/process-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        url, 
        debug: false,
        project_id: projectId
      })
    });
    return handleResponse(res);
  },

  /**
   * Dobavlja presigned URL za upload lokalnog fajla na MinIO.
   */
  async getUploadUrl(filename, contentType) {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/storage/upload_url?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`
    );
    return handleResponse(res);
  },

  /**
   * Poziva AI lektora da skrati tekst segmenta.
   */
  async shortenSegment(projectId, segmentId, text) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project/${projectId}/segment/${segmentId}/shorten`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    return handleResponse(res);
  },

  /**
   * Čuva najnoviji nacrt (draft) segmenata na serveru.
   */
  async saveProjectDraft(projectId, segments) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project/${projectId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segments })
    });
    return handleResponse(res);
  },

  /**
   * Generiše TTS za pojedinačni segment sa zadatim audio modifikatorima.
   */
  async generateSegmentTTS(projectId, segmentId, text, voiceType, volume, speed, pitch, bgVolume) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project/${projectId}/segment/${segmentId}/tts`, {
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
    return handleResponse(res);
  },

  /**
   * Generiše TTS glasove za sve segmente u projektu odjednom.
   */
  async generateAllTTS(projectId, voiceType) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project/${projectId}/generate-all-tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice_type: voiceType })
    });
    return handleResponse(res);
  },

  /**
   * Pokreće Fazu 2 (Renderovanje finalnog videa).
   */
  async renderProject(projectId, voiceType, backgroundVolume, dubbedVolume) {
    const res = await fetch(`${API_BASE_URL}/api/v1/project/${projectId}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        voice_type: voiceType,
        background_volume: backgroundVolume,
        dubbed_volume: dubbedVolume
      })
    });
    return handleResponse(res);
  }
};

import { SwingAnalyzer, normalizeSwingPayload } from './SwingAnalyzer';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const HEALTH_TIMEOUT_MS = 5000;
const UPLOAD_TIMEOUT_MS = 240000;

const resolveBackendUrl = () => {
  if (!BACKEND_URL) {
    throw new Error('Set EXPO_PUBLIC_BACKEND_URL in mobile/.env, then restart Expo.');
  }

  return BACKEND_URL.replace(/\/$/, '');
};

export const getConfiguredBackendUrl = () => (BACKEND_URL ? BACKEND_URL.replace(/\/$/, '') : null);

const fetchBackend = async (path, options = {}, timeoutMs = HEALTH_TIMEOUT_MS) => {
  const baseUrl = resolveBackendUrl();
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timeoutId = controller
    ? setTimeout(() => controller.abort(), timeoutMs)
    : null;

  try {
    return await fetch(`${baseUrl}${path}`, {
      ...options,
      ...(controller ? { signal: controller.signal } : {}),
    });
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error(`Timed out waiting for backend analysis at ${baseUrl}. The API may still be processing the video; check the backend terminal for the latest swing analysis stage timing.`);
    }

    throw new Error(`Could not reach backend at ${baseUrl}. Make sure uvicorn is running on 0.0.0.0:8000 and your firewall allows the connection.`);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
};

export class ServerSwingAnalyzer extends SwingAnalyzer {
  async isAvailable() {
    return Boolean(BACKEND_URL);
  }

  async checkHealth() {
    const response = await fetchBackend('/health', {}, HEALTH_TIMEOUT_MS);

    if (!response.ok) {
      throw new Error(`Backend health check failed with status ${response.status}.`);
    }

    return response.json();
  }

  async submitAnalysisPayload(payload) {
    const response = await fetchBackend('/swings/analysis', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }, UPLOAD_TIMEOUT_MS);

    return this.handleResponse(response);
  }

  async analyzeVideo({ uri, metadata = {}, userConsentedToUpload = false }) {
    if (!userConsentedToUpload) {
      throw new Error('Raw video upload requires explicit user consent.');
    }

    const formData = new FormData();
    formData.append('video', {
      uri,
      name: 'swing.mp4',
      type: 'video/mp4',
    });
    formData.append('user_consented_to_upload', userConsentedToUpload ? 'true' : 'false');

    const response = await fetchBackend('/swings/upload', {
      method: 'POST',
      body: formData,
    }, UPLOAD_TIMEOUT_MS);

    return this.handleResponse(response, {
      source: 'server',
      videoMetadata: metadata,
      privacy: {
        rawVideoUploaded: true,
        userConsentedToUpload,
      },
    });
  }

  async handleResponse(response, defaults = {}) {
    if (!response.ok) {
      let message = `Request failed with status ${response.status}`;
      try {
        const errorBody = await response.json();
        message = errorBody.detail || message;
      } catch {
        // Keep the status-based message if the server did not return JSON.
      }
      throw new Error(message);
    }

    const result = await response.json();
    return normalizeSwingPayload(result, defaults);
  }
}

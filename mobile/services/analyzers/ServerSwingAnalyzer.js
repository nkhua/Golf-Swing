import { SwingAnalyzer, normalizeSwingPayload } from './SwingAnalyzer';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const resolveBackendUrl = () => {
  if (!BACKEND_URL) {
    throw new Error('Set EXPO_PUBLIC_BACKEND_URL in mobile/.env, then restart Expo.');
  }

  return BACKEND_URL.replace(/\/$/, '');
};

export class ServerSwingAnalyzer extends SwingAnalyzer {
  async isAvailable() {
    return Boolean(BACKEND_URL);
  }

  async submitAnalysisPayload(payload) {
    const response = await fetch(`${resolveBackendUrl()}/swings/analysis`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

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

    const response = await fetch(`${resolveBackendUrl()}/swings/upload`, {
      method: 'POST',
      body: formData,
    });

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

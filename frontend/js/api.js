/**
 * API client with auth token management.
 */
const API = (() => {
    const BASE = '/api';

    function getToken() {
        return localStorage.getItem('auth_token');
    }

    function setToken(token) {
        localStorage.setItem('auth_token', token);
    }

    function clearToken() {
        localStorage.removeItem('auth_token');
    }

    function headers(extra = {}) {
        const h = { 'Content-Type': 'application/json', ...extra };
        const token = getToken();
        if (token) h['Authorization'] = `Bearer ${token}`;
        return h;
    }

    async function request(method, path, body = null) {
        const opts = { method, headers: headers() };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(`${BASE}${path}`, opts);
        if (res.status === 401) {
            clearToken();
            location.reload();
            throw new Error('Unauthorized');
        }
        if (res.status === 204) return null;
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Request failed');
        return data;
    }

    // Auth
    async function register(email, username, password) {
        const data = await request('POST', '/auth/register', { email, username, password });
        setToken(data.access_token);
        return data;
    }

    async function login(username, password) {
        const data = await request('POST', '/auth/login', { username, password });
        setToken(data.access_token);
        return data;
    }

    async function getMe() {
        return request('GET', '/auth/me');
    }

    function logout() {
        clearToken();
    }

    // Conversations
    async function getConversations(archived = false, search = '') {
        let path = `/conversations?archived=${archived}`;
        if (search) path += `&search=${encodeURIComponent(search)}`;
        return request('GET', path);
    }

    async function createConversation(data = {}) {
        return request('POST', '/conversations', data);
    }

    async function getConversation(id) {
        return request('GET', `/conversations/${id}`);
    }

    async function updateConversation(id, data) {
        return request('PATCH', `/conversations/${id}`, data);
    }

    async function deleteConversationApi(id) {
        return request('DELETE', `/conversations/${id}`);
    }

    async function getMessages(convId) {
        return request('GET', `/conversations/${convId}/messages`);
    }

    // Chat (streaming)
    function streamChat(body, onChunk, onDone, onError) {
        const controller = new AbortController();

        fetch(`${BASE}/chat/stream`, {
            method: 'POST',
            headers: headers(),
            body: JSON.stringify(body),
            signal: controller.signal,
        }).then(async (response) => {
            if (!response.ok) {
                const err = await response.json();
                onError(err.detail || 'Stream failed');
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === 'text') {
                            onChunk(data.content);
                        } else if (data.type === 'meta') {
                            onChunk(null, data); // Pass metadata
                        } else if (data.type === 'done') {
                            onDone();
                        } else if (data.type === 'error') {
                            onError(data.content);
                        }
                    } catch (e) {
                        // Skip parse errors
                    }
                }
            }
            onDone();
        }).catch((err) => {
            if (err.name !== 'AbortError') {
                onError(err.message);
            }
        });

        return controller;
    }

    // Providers
    async function getProviders() {
        return request('GET', '/chat/providers');
    }

    return {
        getToken, setToken, clearToken,
        register, login, getMe, logout,
        getConversations, createConversation, getConversation,
        updateConversation, deleteConversationApi, getMessages,
        streamChat, getProviders,
    };
})();

/**
 * Main application logic — state management, UI interactions, streaming.
 */

// --- State ---
let currentUser = null;
let currentConversationId = null;
let conversations = [];
let providers = [];
let streamController = null;
let isStreaming = false;
let contextMenuConvId = null;

// --- DOM Refs ---
const $ = id => document.getElementById(id);

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    await showApp();

    // Close context menu on click outside
    document.addEventListener('click', () => hideContextMenu());

    // Enable/disable send button based on input
    $('message-input').addEventListener('input', () => {
        $('send-btn').disabled = !$('message-input').value.trim();
    });
});

// --- App ---
async function showApp() {
    await loadProviders();
    await loadConversations();
    showWelcome();
}

async function loadProviders() {
    try {
        providers = await API.getProviders();
        const providerSelect = $('provider-select');
        providerSelect.innerHTML = '';
        providers.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            opt.disabled = !p.available;
            if (!p.available) opt.textContent += ' (no key)';
            providerSelect.appendChild(opt);
        });
        onProviderChange();
    } catch (err) {
        console.error('Failed to load providers:', err);
    }
}

function onProviderChange() {
    const providerId = $('provider-select').value;
    const provider = providers.find(p => p.id === providerId);
    const modelSelect = $('model-select');
    modelSelect.innerHTML = '';
    if (provider) {
        provider.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = m.name;
            modelSelect.appendChild(opt);
        });
    }
}

async function loadConversations(search = '') {
    try {
        conversations = await API.getConversations(false, search);
        renderConversationList();
    } catch (err) {
        console.error('Failed to load conversations:', err);
    }
}

function renderConversationList() {
    const list = $('conversation-list');
    if (conversations.length === 0) {
        list.innerHTML = '<p style="padding:1rem;color:var(--text-muted);font-size:0.8125rem;text-align:center">No conversations yet</p>';
        return;
    }

    list.innerHTML = conversations.map(c => `
        <div class="conv-item ${c.id === currentConversationId ? 'active' : ''}"
             onclick="openConversation('${c.id}')"
             oncontextmenu="showContextMenu(event, '${c.id}')">
            <span class="conv-title">${escapeHtml(c.title)}</span>
            <button class="btn-icon btn-small conv-menu" onclick="event.stopPropagation(); showContextMenu(event, '${c.id}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/>
                </svg>
            </button>
        </div>
    `).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function searchConversations(query) {
    loadConversations(query);
}

// --- Conversation Management ---
function showWelcome() {
    currentConversationId = null;
    $('welcome-screen').classList.remove('hidden');
    $('messages-container').classList.add('hidden');
    $('messages-container').innerHTML = '';
    renderConversationList();
}

async function openConversation(convId) {
    currentConversationId = convId;
    $('welcome-screen').classList.add('hidden');
    $('messages-container').classList.remove('hidden');
    $('messages-container').innerHTML = '';

    try {
        const messages = await API.getMessages(convId);
        messages.forEach(msg => appendMessage(msg.role, msg.content, false));

        // Update provider/model selectors
        const conv = conversations.find(c => c.id === convId);
        if (conv) {
            $('provider-select').value = conv.provider;
            onProviderChange();
            $('model-select').value = conv.model;
            $('system-prompt').value = conv.system_prompt || '';
        }

        renderConversationList();
        scrollToBottom();
    } catch (err) {
        console.error('Failed to open conversation:', err);
    }

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        $('sidebar').classList.add('collapsed');
    }
}

async function createNewChat() {
    showWelcome();
    $('system-prompt').value = '';
}

// --- Context Menu ---
function showContextMenu(e, convId) {
    e.preventDefault();
    e.stopPropagation();
    contextMenuConvId = convId;
    const menu = $('context-menu');
    menu.classList.remove('hidden');
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
}

function hideContextMenu() {
    $('context-menu').classList.add('hidden');
}

async function renameConversation() {
    hideContextMenu();
    const newTitle = prompt('Enter new title:');
    if (!newTitle || !contextMenuConvId) return;
    try {
        await API.updateConversation(contextMenuConvId, { title: newTitle });
        await loadConversations();
    } catch (err) {
        alert('Failed to rename: ' + err.message);
    }
}

async function archiveConversation() {
    hideContextMenu();
    if (!contextMenuConvId) return;
    try {
        await API.updateConversation(contextMenuConvId, { is_archived: true });
        if (currentConversationId === contextMenuConvId) showWelcome();
        await loadConversations();
    } catch (err) {
        alert('Failed to archive: ' + err.message);
    }
}

async function deleteConversation() {
    hideContextMenu();
    if (!contextMenuConvId || !confirm('Delete this conversation?')) return;
    try {
        await API.deleteConversationApi(contextMenuConvId);
        if (currentConversationId === contextMenuConvId) showWelcome();
        await loadConversations();
    } catch (err) {
        alert('Failed to delete: ' + err.message);
    }
}

// --- Messaging ---
function appendMessage(role, content, animate = true) {
    const container = $('messages-container');
    const div = document.createElement('div');
    div.className = `message ${animate ? '' : ''}`;

    const avatarClass = role === 'user' ? 'user' : 'assistant';
    const avatarText = role === 'user' ? 'U' : 'AI';
    const roleLabel = role === 'user' ? 'You' : 'Assistant';

    div.innerHTML = `
        <div class="message-avatar ${avatarClass}">${avatarText}</div>
        <div class="message-body">
            <div class="message-role">${roleLabel}</div>
            <div class="message-content">${role === 'user' ? escapeHtml(content) : MarkdownRenderer.render(content)}</div>
        </div>
    `;

    container.appendChild(div);
    return div;
}

function appendStreamingMessage() {
    const container = $('messages-container');
    const div = document.createElement('div');
    div.className = 'message';
    div.id = 'streaming-message';

    const avatarText = 'AI';
    div.innerHTML = `
        <div class="message-avatar assistant">${avatarText}</div>
        <div class="message-body">
            <div class="message-role">Assistant</div>
            <div class="message-content">
                <div class="typing-indicator"><span></span><span></span><span></span></div>
            </div>
        </div>
    `;

    container.appendChild(div);
    return div;
}

function updateStreamingMessage(text) {
    const msg = $('streaming-message');
    if (!msg) return;
    const contentEl = msg.querySelector('.message-content');
    contentEl.innerHTML = MarkdownRenderer.render(text);
    scrollToBottom();
}

function finalizeStreamingMessage() {
    const msg = $('streaming-message');
    if (msg) msg.id = '';
}

async function sendMessage() {
    const input = $('message-input');
    const text = input.value.trim();
    if (!text || isStreaming) return;

    // Show message
    $('welcome-screen').classList.add('hidden');
    $('messages-container').classList.remove('hidden');
    appendMessage('user', text);
    input.value = '';
    input.style.height = 'auto';
    $('send-btn').disabled = true;

    // Start streaming
    isStreaming = true;
    $('send-btn').classList.add('hidden');
    $('stop-btn').classList.remove('hidden');

    const streamMsg = appendStreamingMessage();
    scrollToBottom();

    let fullResponse = '';
    let convId = currentConversationId;

    const body = {
        message: text,
        conversation_id: convId || undefined,
        provider: $('provider-select').value,
        model: $('model-select').value,
        system_prompt: $('system-prompt').value || undefined,
        temperature: parseFloat($('temperature-slider').value),
        max_tokens: parseInt($('max-tokens-input').value),
    };

    streamController = API.streamChat(
        body,
        // onChunk
        (content, meta) => {
            if (meta && meta.conversation_id && !currentConversationId) {
                currentConversationId = meta.conversation_id;
                loadConversations(); // Refresh sidebar
            }
            if (content) {
                fullResponse += content;
                updateStreamingMessage(fullResponse);
            }
        },
        // onDone
        () => {
            finishStreaming();
        },
        // onError
        (error) => {
            if (fullResponse) {
                fullResponse += `\n\n*Error: ${error}*`;
                updateStreamingMessage(fullResponse);
            } else {
                updateStreamingMessage(`*Error: ${error}*`);
            }
            finishStreaming();
        }
    );
}

function finishStreaming() {
    isStreaming = false;
    streamController = null;
    finalizeStreamingMessage();
    $('send-btn').classList.remove('hidden');
    $('stop-btn').classList.add('hidden');
    $('send-btn').disabled = !$('message-input').value.trim();
}

function stopStreaming() {
    if (streamController) {
        streamController.abort();
        finishStreaming();
    }
}

function sendSuggestion(text) {
    $('message-input').value = text;
    $('send-btn').disabled = false;
    sendMessage();
}

// --- UI Helpers ---
function scrollToBottom() {
    const chatArea = $('chat-area');
    chatArea.scrollTop = chatArea.scrollHeight;
}

function toggleSidebar() {
    $('sidebar').classList.toggle('collapsed');
}

function toggleSettings() {
    $('settings-panel').classList.toggle('hidden');
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

function handleInputKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// Keyboard shortcut: Ctrl+N for new chat
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        createNewChat();
    }
});

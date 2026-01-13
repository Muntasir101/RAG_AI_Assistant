// Session management
let sessionId = null;

// DOM elements
const chatForm = document.getElementById('chatForm');
const questionInput = document.getElementById('questionInput');
const sendButton = document.getElementById('sendButton');
const chatMessages = document.getElementById('chatMessages');
const infoPanel = document.getElementById('infoPanel');
const confidenceBadge = document.getElementById('confidenceBadge');
const confidenceValue = document.getElementById('confidenceValue');
const sourcesList = document.getElementById('sourcesList');
const sourcesSection = document.getElementById('sourcesSection');

// API endpoint
const API_URL = '/ask';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    chatForm.addEventListener('submit', handleSubmit);
    questionInput.focus();
});

// Handle form submission
async function handleSubmit(e) {
    e.preventDefault();
    
    const question = questionInput.value.trim();
    if (!question) return;

    // Add user message to chat
    addMessage(question, 'user');
    
    // Clear input
    questionInput.value = '';
    questionInput.disabled = true;
    sendButton.disabled = true;

    // Show loading indicator
    const loadingId = addLoadingMessage();

    try {
        // Call API
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                session_id: sessionId
            })
        });

        const data = await response.json();

        // Remove loading indicator
        removeLoadingMessage(loadingId);

        if (response.ok) {
            // Update session ID
            sessionId = data.session_id;

            // Add bot response
            addMessage(data.answer, 'bot');

            // Update info panel
            updateInfoPanel(data);

            // Show info panel if there are sources
            if (data.sources && data.sources.length > 0) {
                infoPanel.style.display = 'block';
            }
        } else {
            // Show error
            addMessage(`Error: ${data.detail || 'Failed to get answer'}`, 'bot', true);
        }
    } catch (error) {
        removeLoadingMessage(loadingId);
        addMessage(`Error: ${error.message}. Please check if the server is running.`, 'bot', true);
        console.error('Error:', error);
    } finally {
        questionInput.disabled = false;
        sendButton.disabled = false;
        questionInput.focus();
    }
}

// Add message to chat
function addMessage(text, type, isError = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (isError) {
        contentDiv.classList.add('error-message');
    }
    
    // Format text with line breaks
    const paragraphs = text.split('\n').filter(p => p.trim());
    paragraphs.forEach(para => {
        const p = document.createElement('p');
        p.textContent = para;
        contentDiv.appendChild(p);
    });
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageDiv;
}

// Add loading message
function addLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    messageDiv.id = 'loading-message';
    
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message-loading';
    loadingDiv.innerHTML = '<span></span><span></span><span></span>';
    
    messageDiv.appendChild(loadingDiv);
    chatMessages.appendChild(messageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return 'loading-message';
}

// Remove loading message
function removeLoadingMessage(id) {
    const loadingMsg = document.getElementById(id);
    if (loadingMsg) {
        loadingMsg.remove();
    }
}

// Update info panel with answer details
function updateInfoPanel(data) {
    // Update confidence
    const confidence = Math.round((data.confidence || 0) * 100);
    confidenceValue.textContent = `${confidence}%`;
    
    // Update confidence badge color with professional styling
    if (confidence >= 80) {
        confidenceBadge.style.background = '#d1fae5';
        confidenceBadge.style.borderColor = '#10b981';
        confidenceValue.style.color = '#059669';
    } else if (confidence >= 50) {
        confidenceBadge.style.background = '#fef3c7';
        confidenceBadge.style.borderColor = '#f59e0b';
        confidenceValue.style.color = '#d97706';
    } else {
        confidenceBadge.style.background = '#fee2e2';
        confidenceBadge.style.borderColor = '#ef4444';
        confidenceValue.style.color = '#dc2626';
    }
    
    // Update sources
    sourcesList.innerHTML = '';
    if (data.sources && data.sources.length > 0) {
        data.sources.forEach((source, index) => {
            const sourceDiv = document.createElement('div');
            sourceDiv.className = 'source-item';
            sourceDiv.innerHTML = `
                <strong>Source ${index + 1}:</strong>
                <p>${source.content_preview || 'No preview available'}</p>
            `;
            sourcesList.appendChild(sourceDiv);
        });
        sourcesSection.style.display = 'block';
    } else {
        sourcesSection.style.display = 'none';
    }
}

// Toggle info panel
function toggleInfoPanel() {
    if (infoPanel.style.display === 'none') {
        infoPanel.style.display = 'block';
    } else {
        infoPanel.style.display = 'none';
    }
}

// Allow Enter key to submit (but Shift+Enter for new line)
questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

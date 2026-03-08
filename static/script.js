document.addEventListener('DOMContentLoaded', () => {
    const messagesContainer = document.getElementById('messages-container');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const welcomeMessage = document.querySelector('.welcome-message');

    function appendMessage(role, text) {
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role === 'user' ? 'user-message' : 'bot-message'}`;
        msgDiv.textContent = text;
        messagesContainer.appendChild(msgDiv);

        // Auto scroll to bottom
        const main = document.querySelector('main');
        main.scrollTop = main.scrollHeight;
    }

    async function sendMessage() {
        const query = userInput.value.trim();
        if (!query) return;

        appendMessage('user', query);
        userInput.value = '';

        // Show typing indicator logic (simplified)
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'message bot-message typing-indicator';
        typingIndicator.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
        typingIndicator.style.display = 'block';
        messagesContainer.appendChild(typingIndicator);

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query })
            });

            const data = await response.json();
            messagesContainer.removeChild(typingIndicator);

            if (data.answer) {
                appendMessage('bot', data.answer);
            } else {
                appendMessage('bot', 'Error: ' + (data.error || 'Unknown error occurred.'));
            }
        } catch (error) {
            messagesContainer.removeChild(typingIndicator);
            appendMessage('bot', 'Error connecting to the server.');
            console.error('Fetch error:', error);
        }
    }

    sendBtn.addEventListener('click', sendMessage);

    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Focus input on load
    userInput.focus();
});

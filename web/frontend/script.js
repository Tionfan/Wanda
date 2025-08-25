class ChatApp {
    constructor() {
        this.apiUrl = 'http://localhost:8080'; // 后端API地址
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.charCount = document.querySelector('.char-count');

        // 配置marked选项
        this.configureMarked();
        this.initEventListeners();
    }

    configureMarked() {
        // 配置marked选项
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                highlight: function (code, lang) {
                    if (typeof Prism !== 'undefined' && Prism.languages[lang]) {
                        return Prism.highlight(code, Prism.languages[lang], lang);
                    }
                    return code;
                },
                breaks: true, // 支持换行
                gfm: true, // 启用GitHub风格的Markdown
                sanitize: false, // 允许HTML（谨慎使用）
                smartLists: true,
                smartypants: true
            });
        }
    }

    // Markdown渲染方法
    renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        // 如果marked库没有加载，回退到简单的文本替换
        return this.simpleMarkdownRender(text);
    }

    // 简单的Markdown渲染（备用方案）
    simpleMarkdownRender(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // 粗体
            .replace(/\*(.*?)\*/g, '<em>$1</em>') // 斜体
            .replace(/`(.*?)`/g, '<code>$1</code>') // 行内代码
            .replace(/\n/g, '<br>') // 换行
            .replace(/^### (.*$)/gim, '<h3>$1</h3>') // h3标题
            .replace(/^## (.*$)/gim, '<h2>$1</h2>') // h2标题
            .replace(/^# (.*$)/gim, '<h1>$1</h1>'); // h1标题
    }

    initEventListeners() {
        // 发送按钮点击事件
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // 输入框回车事件
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 字符计数
        this.messageInput.addEventListener('input', () => {
            const length = this.messageInput.value.length;
            this.charCount.textContent = `${length}/1000`;

            if (length > 900) {
                this.charCount.style.color = '#e74c3c';
            } else if (length > 800) {
                this.charCount.style.color = '#f39c12';
            } else {
                this.charCount.style.color = '#999';
            }
        });

        // 模态框外部点击关闭
        document.getElementById('thinkingModal').addEventListener('click', (e) => {
            if (e.target.id === 'thinkingModal') {
                this.closeThinkingModal();
            }
        });
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // 禁用输入和发送按钮
        this.setInputState(false);

        // 添加用户消息到界面
        this.addMessage(message, 'user');

        // 清空输入框
        this.messageInput.value = '';
        this.charCount.textContent = '0/1000';
        this.charCount.style.color = '#999';

        try {
            // 创建助手消息容器
            const assistantMessageElement = this.addMessage('', 'assistant', true);
            const messageTextElement = assistantMessageElement.querySelector('.message-text');

            // 发送请求到后端
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let assistantResponse = '';
            let reasoningContent = '';
            let isReceivingReasoning = false;
            let isReceivingAnswer = false;
            let thinkingContainer = null;
            let thinkingTextElement = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // 保留不完整的行

                for (const line of lines) {
                    if (line.trim() === '') continue;

                    try {
                        const data = JSON.parse(line);

                        if (data.type === 'reasoning') {
                            if (!isReceivingReasoning) {
                                isReceivingReasoning = true;
                                // 创建思考过程容器
                                thinkingContainer = this.createThinkingContainer(assistantMessageElement);
                                thinkingTextElement = thinkingContainer.querySelector('.thinking-text');
                            }
                            reasoningContent += data.content;
                            // 流式更新思考内容
                            if (thinkingTextElement) {
                                thinkingTextElement.textContent = reasoningContent;
                                this.scrollToBottom();
                            }
                        } else if (data.type === 'answer') {
                            if (!isReceivingAnswer) {
                                isReceivingAnswer = true;
                                // 收起思考过程
                                if (thinkingContainer && reasoningContent) {
                                    this.collapseThinking(thinkingContainer, reasoningContent);
                                }
                            }
                            assistantResponse += data.content;
                            // 流式输出时先显示原文本，在完成后再渲染Markdown
                            messageTextElement.textContent = assistantResponse;
                            this.scrollToBottom();
                        } else if (data.type === 'error') {
                            throw new Error(data.content);
                        }
                    } catch (parseError) {
                        console.warn('Failed to parse line:', line, parseError);
                    }
                }
            }

            // 流式输出完成后，将最终的文本渲染为Markdown
            if (assistantResponse && messageTextElement) {
                messageTextElement.innerHTML = this.renderMarkdown(assistantResponse);
                // 触发代码高亮
                if (typeof Prism !== 'undefined') {
                    Prism.highlightAllUnder(assistantMessageElement);
                }
            }

            // 滚动到最新消息
            this.scrollToBottom();

        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('抱歉，发生了错误。请稍后重试。', 'assistant');
        } finally {
            // 重新启用输入
            this.setInputState(true);
        }
    }

    addMessage(content, sender, isStreaming = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';

        const messageText = document.createElement('div');
        messageText.className = 'message-text';

        // 根据发送者类型决定是否渲染Markdown
        if (sender === 'assistant') {
            // AI回复使用Markdown渲染
            messageText.innerHTML = this.renderMarkdown(content);
        } else {
            // 用户消息保持纯文本
            messageText.textContent = content;
        }

        messageContent.appendChild(messageText);
        messageDiv.appendChild(messageContent);

        // 移除欢迎消息（如果存在）
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage && sender === 'user') {
            welcomeMessage.remove();
        }

        this.chatMessages.appendChild(messageDiv);

        // 如果是AI消息且包含代码块，触发代码高亮
        if (sender === 'assistant' && typeof Prism !== 'undefined') {
            Prism.highlightAllUnder(messageDiv);
        }

        if (!isStreaming) {
            this.scrollToBottom();
        }

        return messageDiv;
    }

    addThinkingButton(messageElement, reasoningContent) {
        const messageContent = messageElement.querySelector('.message-content');

        const thinkingButton = document.createElement('button');
        thinkingButton.className = 'thinking-button';
        thinkingButton.textContent = '💭 查看AI思考过程';
        thinkingButton.onclick = () => this.showThinkingModal(reasoningContent);

        messageContent.appendChild(thinkingButton);
    }

    createThinkingContainer(messageElement) {
        const messageContent = messageElement.querySelector('.message-content');

        const thinkingContainer = document.createElement('div');
        thinkingContainer.className = 'thinking-container expanded';

        const thinkingHeader = document.createElement('div');
        thinkingHeader.className = 'thinking-header';
        thinkingHeader.innerHTML = '🤔 AI正在思考...';

        const thinkingContent = document.createElement('div');
        thinkingContent.className = 'thinking-content-inline';

        const thinkingText = document.createElement('div');
        thinkingText.className = 'thinking-text';

        thinkingContent.appendChild(thinkingText);
        thinkingContainer.appendChild(thinkingHeader);
        thinkingContainer.appendChild(thinkingContent);

        // 插入到消息文本之前
        const messageText = messageContent.querySelector('.message-text');
        messageContent.insertBefore(thinkingContainer, messageText);

        return thinkingContainer;
    }

    collapseThinking(thinkingContainer, reasoningContent) {
        if (!thinkingContainer) return;

        // 更新头部文本
        const thinkingHeader = thinkingContainer.querySelector('.thinking-header');
        thinkingHeader.innerHTML = `
            <span class="thinking-title">💭 AI思考过程</span>
            <span class="thinking-toggle">展开查看</span>
        `;

        // 移除expanded类，添加collapsed类
        thinkingContainer.classList.remove('expanded');
        thinkingContainer.classList.add('collapsed');

        // 添加点击事件
        thinkingHeader.style.cursor = 'pointer';
        thinkingHeader.onclick = () => this.toggleThinking(thinkingContainer, reasoningContent);
    }

    toggleThinking(thinkingContainer, reasoningContent) {
        const isCollapsed = thinkingContainer.classList.contains('collapsed');
        const thinkingContent = thinkingContainer.querySelector('.thinking-content-inline');
        const toggleSpan = thinkingContainer.querySelector('.thinking-toggle');

        if (isCollapsed) {
            // 展开
            thinkingContainer.classList.remove('collapsed');
            thinkingContainer.classList.add('expanded');
            toggleSpan.textContent = '收起';
            thinkingContent.style.maxHeight = thinkingContent.scrollHeight + 'px';
        } else {
            // 收起
            thinkingContainer.classList.remove('expanded');
            thinkingContainer.classList.add('collapsed');
            toggleSpan.textContent = '展开查看';
            thinkingContent.style.maxHeight = '0';
        }
    }

    showThinkingModal(content) {
        const modal = document.getElementById('thinkingModal');
        const thinkingContent = document.getElementById('thinkingContent');

        thinkingContent.textContent = content;
        modal.style.display = 'flex';

        // 防止body滚动
        document.body.style.overflow = 'hidden';
    }

    closeThinkingModal() {
        const modal = document.getElementById('thinkingModal');
        modal.style.display = 'none';

        // 恢复body滚动
        document.body.style.overflow = '';
    }

    setInputState(enabled) {
        this.messageInput.disabled = !enabled;
        this.sendButton.disabled = !enabled;

        if (enabled) {
            this.sendButton.querySelector('.send-text').style.display = 'inline';
            this.sendButton.querySelector('.loading-spinner').style.display = 'none';
            this.messageInput.focus();
        } else {
            this.sendButton.querySelector('.send-text').style.display = 'none';
            this.sendButton.querySelector('.loading-spinner').style.display = 'inline';
        }
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
}

// 全局函数供HTML调用
function closeThinkingModal() {
    window.chatApp.closeThinkingModal();
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});

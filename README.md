# Email AI Orchestrator

This project combines multiple local AI models to summarize emails, analyze sentiment, and generate reply suggestions inside a Chrome Extension.

## 🚀 Features
- 📬 Email summarization using BART
- 😀 Sentiment analysis using RoBERTa
- ✍️ Reply suggestion via Gemma 3B
- 🔌 Chrome Extension for UI

## 🛠️ Setup

```bash
git clone https://github.com/ht6891/email-ai-orchestrator.git
cd email-ai-orchestrator
pip install -r requirements.txt
python app.py
```

## 🧪 Demo

You can view the system demo here:
📽️ *[Insert demo video link once ready]*

## 📈 Models Used

- 🤖 **Summarization**: Facebook BART (`facebook/bart-large-cnn`)
- 😊 **Sentiment Analysis**: RoBERTa (`cardiffnlp/twitter-roberta-base-sentiment`)
- 💬 **Reply Suggestion**: Local LLM Gemma 3B via Ollama

## 📌 Future Improvements

- 📧 Gmail API integration to fetch emails securely
- 🔐 User-specific customization (e.g., tone, length preferences)
- 📊 Model comparison UI inside extension

## 📄 License

MIT License. See `LICENSE` file for more information.

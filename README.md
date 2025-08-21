# Email AI Assistant

## 1\. Project Overview

The **Email AI Assistant** is a desktop application designed to enhance email management efficiency by leveraging local AI models. This system integrates with Gmail to automatically fetch emails from your inbox, allowing you to utilize a suite of AI-powered features through a web-based interface.

  - **Quick & LLM-based Summaries**: Provides two levels of summarization to help you quickly grasp the main points of an email.
  - **Sentiment Analysis**: Analyzes the tone of an email (positive, negative, neutral) to help you prioritize responses to important messages.
  - **Draft Replies**: Automatically generates draft replies based on the email's content, saving you valuable time.
  - **Multilingual Translation**: Supports bidirectional translation between Korean and English, enabling seamless communication across language barriers.

## 2\. Key Technologies

  - **Backend**: `Flask`, `Transformers`, `PyTorch`
  - **Frontend**: `HTML`, `CSS`, `JavaScript`
  - **AI Models**:
      - `gemma3:4b` (run locally via Ollama)
      - `philschmid/bart-large-cnn-samsum` (English summarization)
      - `csebuetnlp/mT5_multilingual_XLSum` (Multilingual summarization)
      - `cardiffnlp/twitter-xlm-roberta-base-sentiment` (Sentiment analysis)
  - **API**: `Gmail API`

## 3\. System Architecture

## 4\. Installation and Setup

### 4.1. Prerequisites

1.  **Python 3.8 or higher** installed.
2.  **Ollama** installed and the `gemma3:4b` model downloaded.
    ```bash
    ollama pull gemma3:4b
    ```
3.  `credentials.json` file from **Google Cloud Platform**.
      - Create a new project in the [Google Cloud Console](https://console.cloud.google.com/).
      - Navigate to **APIs & Services \> Library**, search for the **Gmail API**, and enable it.
      - Go to **APIs & Services \> Credentials** and create an **OAuth client ID** (Application type: Desktop app).
      - Download the credentials as a JSON file and save it as `credentials.json` in the project's root directory.

### 4.2. Installation Steps

1.  **Clone the repository**

    ```bash
    git clone https://github.com/your-username/email-ai-assistant.git
    cd email-ai-assistant
    ```

2.  **Install the required libraries**

    ```bash
    pip install -r requirements.txt
    ```

### 4.3. How to Run

1.  **Start the Flask backend server**

      - Open a terminal and run the following command to start the Flask server.

    <!-- end list -->

    ```bash
    python app.py
    ```

2.  **Initial Gmail API Authentication**

      - When you run the server for the first time, you'll need to grant API access by logging into your Google account through a browser window.
      - Once authentication is complete, a `token.json` file will be created automatically, and you won't need to log in again.

3.  **Access the Web Application**

      - Open the `popup.html` file directly in your web browser to launch the application.

## 5\. File Descriptions

| Filename | Description |
|---|---|
| `app.py` | The **main Flask application** that defines API endpoints, loads AI models, and handles summarization, sentiment analysis, reply generation, and translation tasks. |
| `gmail_service.py` | The **Gmail API integration module**. It handles OAuth 2.0 authentication and fetches recent emails from the user's inbox. |
| `run_fetch.py` | An **executable script** that calls `gmail_service.py` to retrieve email data. |
| `process_emails.py` | A **standalone script** for processing fetched emails with AI functions and printing the results to the terminal, used for API testing. |
| `email_cleaner.py` | A preprocessing module that **improves the accuracy of the AI models** by removing unnecessary signatures, ads, and legal disclaimers from email bodies. |
| `evaluate.py` | An **evaluation script** that quantitatively measures the performance of the AI models (summarization, translation, etc.) and generates a CSV file and a Markdown report. |
| `popup.html` | The **web-based user interface** where users can interact with the AI features and view the results. |
| `popup.js` | Handles the dynamic functionality of `popup.html`, making asynchronous (AJAX) calls to the Flask server to request AI processing and render the results. |
| `credentials.json` | A file containing **user authentication information for the Gmail API**. (For security, this file should not be included in a public Git repository). |
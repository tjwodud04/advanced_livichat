# Live2D Interactive Avatar Project

An interactive Live2D avatar project that enables low-latency voice conversations. Using OpenAI's voice recognition and generation capabilities, users can engage in natural conversations with characters.

Brief Project Demo:

https://github.com/user-attachments/assets/1b67882f-7ca8-4871-97ab-11de4ba86212

## 🌟 Key Features

- **Multiple Character Support**: Interact with various characters like Kei and Haru
- **Low-Latency Voice Chat**: Live voice input through browser microphone
- **Natural Lip Sync**: Character mouth movements synchronized with voice
- **Emotion Expression**: Character expressions change based on conversation context
- **Responsive UI**: Support for various devices including mobile

## 🔧 Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/Vercel_CharacterChat.git
cd Vercel_CharacterChat
```

2. Create and activate Python virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install required packages
```bash
pip install -r requirements.txt
```

## ⚙️ Configuration

### OpenAI API Key Setup
1. Get your API key from [OpenAI website](https://platform.openai.com)
2. Click "Set OpenAI API Key" button in the web interface
3. Enter your API key

### Running Local Development Server
```bash
python realtime.py
```
Access the application at `http://localhost:8001` once the server starts.

## 💻 How to Use

1. Select a character to chat with from the main page
2. Set up OpenAI API key if not already configured
3. Allow microphone access when prompted
4. Click "Talk" button to start speaking
5. Click the button again to stop recording
6. Listen to the character's voice response

## 🔍 System Requirements

- **Browser**: Latest versions of Chrome, Firefox, or Edge
- **Microphone**: Required for voice input
- **Internet**: Stable connection required
- **Minimum Specifications**:
  - CPU: Dual-core or better
  - RAM: 4GB minimum
  - Storage: 100MB available space

## 📁 Project Structure

```
.
├── api/                    # Backend API components
├── front/                  # Frontend files
│   ├── css/               # Stylesheets
│   ├── js/                # Frontend functionality
│   ├── index.html         # Main page
│   ├── haru.html          # Haru character page
│   ├── kei.html           # Kei character page
│   ├── realtime.html      # Low-latency chat page
├── model/                  # Live2D model assets
│   ├── haru/              # Haru model files
│   ├── kei/               # Kei model files
│   ├── momose/            # Momose model files
├── audio_util.py          # Audio processing utilities
├── realtime.py            # Main server script
├── requirements.txt       # Python dependencies
├── vercel.json           # Vercel deployment config
```

## 🚨 Troubleshooting

### Common Issues
1. **Microphone Not Working**
   - Check browser microphone permissions
   - Verify no other apps are using the microphone

2. **Voice Not Recognized**
   - Check microphone volume
   - Minimize background noise
   - Verify internet connection

3. **Character Not Displaying**
   - Refresh browser
   - Clear cache and try again

### API Key Issues
- Verify API key format (should start with sk-)
- Check if API key has sufficient credits
- Try re-entering the API key

# PRD: OS1 Samantha 100% Real Production Engine (Zero Dummy / Zero Mock)

## 1. Objective
Transform all simulated, placeholder, and mock features in OS1-HER into 100% real, operational implementations:
1. **Real Mac Computer Automation (`mac_automation.py` & `app.py`)**:
   - Direct macOS GUI control via AppleScript and Quartz CoreGraphics.
   - Real app launching (`open -a`), URL opening, Finder path revealing (`open`).
   - Real keystroke injection & typing into active applications.
   - Real native coordinate mouse clicks via Quartz / CoreGraphics.
   - Real display screencapture via `screencapture -x -t jpg`.
   - Real active frontmost window/app inspection (`get_frontmost_app()`, `list_running_apps()`).
   - Direct execution from `/os1/chat` and `/os1/actions` when user requests computer actions.

2. **Real Mobile Automation (`mobile_automation.py` & `app.py`)**:
   - Real Android ADB discovery (`adb devices -l`), tap (`input tap`), swipe, keyevents (HOME, BACK), screencap, and app launch.
   - Real iOS Simulator query (`xcrun simctl`) and Apple Shortcuts execution (`shortcuts run`).
   - Honest hardware diagnostics reporting when devices are not connected, with zero fake mock actions.

3. **Real Multimodal Vision Perception (`vision.py` & `connectors.py`)**:
   - Remove all hardcoded fake bounding boxes from `QwenVlConnector`.
   - Real desktop screen perception from live macOS screencapture + AppleScript window inspector.
   - Real camera perception from webcam canvas frame using Pillow metrics: real luminance, color temperature (warm room hues vs blue screen glare), and human presence via YCbCr skin chrominance analysis.

4. **Real Conversational Intelligence (`brain_qwen.py`, `brain_dual.py`, `app.py`)**:
   - Eliminate the 3-template modulo hack (`reply_templates[len % 3]`).
   - Multi-tier cognitive brain:
     - LLM provider integration: automatically detects local or remote OpenAI / Anthropic / Gemini endpoints if configured.
     - Comprehensive Semantic Dialogue Engine: full intent classification, contextual memory injection, conversation history tracking across turns, running app awareness, and authentic Spike Jonze *Her* Samantha persona.
     - Punctuation-based first-sentence streaming with acting tags (`<laughter>`, `<whisper>`, `[softly]`).

5. **Real Semantic Memory & Vector Retrieval (`connectors.py` & `store.py`)**:
   - Replace MD5 hash simulation with real TF-IDF / Cosine semantic similarity vector retrieval over SQLite memories.

6. **Real Native Mail / Inbox Integration (`store.py` & `app.py`)**:
   - Query real Apple Mail unread messages on macOS when available, alongside local SQLite spatial inbox.

7. **Voice and Audio Polish (`useOs1.ts`, `sound.ts`, `Screens.tsx`)**:
   - Male Operator voice for setup (`Daniel (English (UK))`).
   - Female Samantha voice for active conversation (`Samantha (English (US))`).
   - Zero-hanging speech synthesis watchdog with keep-alive heartbeat.
   - Microphone SpeechRecognition with real-time interim display and Web Audio Analyser.

---

## 2. Acceptance Criteria & Tasks
- [ ] `TASK-1`: Wire real Mac Automation into `chat_endpoint` and `dispatchAction`: replace dummy strings with real AppleScript/Quartz execution for app launch, path reveal, typing, clicking, and frontmost status.
- [ ] `TASK-2`: Wire real Mobile Automation: execute real ADB commands and iOS shortcuts, with honest diagnostics when no hardware is attached.
- [ ] `TASK-3`: Remove all hardcoded mock vision boxes from `connectors.py` and implement real screen OCR and camera pixel perception in `vision.py`.
- [ ] `TASK-4`: Replace the 3-template modulo hack in `brain_qwen.py` and `app.py` with a multi-tier conversational engine featuring conversation history, memory grounding, and visual awareness.
- [ ] `TASK-5`: Implement real semantic vector retrieval (TF-IDF / Cosine similarity) in `BgeSmallConnector` for memory queries.
- [ ] `TASK-6`: Integrate real Apple Mail status query via AppleScript for inbox actions.
- [ ] `TASK-7`: Full test verification across orchestrator, voice, and TypeScript UI with 0 errors.

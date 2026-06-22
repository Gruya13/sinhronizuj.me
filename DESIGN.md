# Design System: sinhronizuj.me

This document defines the visual design system, aesthetics, typography, color palette, and user interface layouts for the **sinhronizuj.me** platform. It is designed to look like a high-premium, state-of-the-art Digital Audio Workstation (DAW) and video translation application.

---

## 1. Visual & Aesthetic Principles

### Theme: Dark-Mode Studio
*   **Atmosphere**: Professional, focused, modern, and high-tech.
*   **Glassmorphism**: Translucent cards and panels with backdrop blur and subtle borders to create depth.
*   **Neon Accents & Glows**: Use soft neon glows for active states, AI operations, and highlights.
*   **Micro-Animations**: Smooth transitions, scale effects on hover, and pulsing glows for loading or active processing.

---

## 2. Design System Tokens

### Colors (HSL / Hex)
*   **Background (Deep Space)**: `#080B11` (Deep dark slate/blue)
*   **Surfaces (Translucent Slate)**: `rgba(18, 26, 41, 0.6)` with `backdrop-filter: blur(16px)`
*   **Borders (Subtle White)**: `rgba(255, 255, 255, 0.08)`
*   **Primary Accent (Neon Cyan)**: `#00F0FF` (Glowing cyan, used for navigation, playback cursor, active states)
*   **Secondary Accent (AI Purple)**: `#A855F7` (Deep purple, used for AI actions, translation, TTS generation)
*   **Success (Emerald Green)**: `#10B981` (Used for system status, online status, completions)
*   **Warning/Error (Coral Red)**: `#EF4444` (Used for errors, warnings, delete actions)

### Typography
*   **Primary Font**: `Outfit` or `Inter`, sans-serif.
*   **Headings**: Bold, high contrast, clean letter-spacing.
*   **Monospace (for logs/timecodes)**: `JetBrains Mono` or `Fira Code`.

---

## 3. Core Components

### Custom Rotary Knob (`Knob`)
*   A circular knob dial used for adjusting values like Volume, Pitch, and Speed.
*   Shows a glowing arc indicating the current percentage.
*   Draggable vertically to adjust.

### Studio Timeline (`StudioTimeline`)
*   Horizontal grid representing the video duration with timecodes.
*   Draws two waveforms: the original audio (top track) and synthesized audio (bottom track).
*   A vertical red cursor line showing current playback position.
*   Interactive: click to seek, drag bounds to zoom.

### Segment Card (`SegmentEditor`)
*   A card representing a single sentence/segment of the video.
*   Contains:
    *   **Timecodes**: Start and end times (e.g. `00:12.400 -> 00:15.120`).
    *   **Original Text**: Read-only text showing the transcribed speech.
    *   **Translation Input**: Interactive text area for editing the translated text.
    *   **AI Settings**: Voice selection dropdown (e.g., Male, Female, regional accents), Speed dial, Pitch dial, Volume dial.

---

## 4. Screen Layouts

### Screen 1: Landing Page
*   **Header**: Glassmorphic header with the logo `sinhronizuj.me` in Neon Cyan, and a "Prijavi se" (Sign In) button.
*   **Hero Section**: Large headline: "Sinhronizujte svoje video zapise na bilo koji jezik uz pomoć AI sinkronizacije". A sleek side-by-side video player demo demonstrating before/after translation.
*   **Call-to-Action**: "Pridruži se zatvorenoj beti" (Join Waitlist) button with glowing hover effect.

### Screen 2: Login & Waitlist Card
*   **Layout**: Centered glassmorphic card with backdrop blur.
*   **Forms**:
    *   *Login Mode*: Email, Password fields, and a button to login.
    *   *Waitlist Mode*: Full Name, Email, Use Case description, and "Pošalji zahtev" (Submit Request) button. Clicking register redirects here.

### Screen 3: Dashboard View
*   **Hardware Monitor Bar**: Slim banner at the top showing server latency, CPU/GPU usage, and Redis state (green dots).
*   **New Project Form**: A card to upload a new video (drag-and-drop file area) and enter the title.
*   **Projects Grid**: A responsive grid of existing projects showing:
    *   Video thumbnail preview.
    *   Project title and status badge (e.g., `Prevođenje`, `Spreman`, `Neuspešan`).
    *   Action buttons: "Otvori u Studiju" (Open in Studio) and "Obriši" (Delete).

### Screen 4: Studio (DAW Editor) View
*   **Navigation Header**: Shows project title, back-to-dashboard button, and "Izvezi video" (Export Video) action button.
*   **Main Workspace (Split Screen)**:
    *   *Left Side (Video Player)*: Video player showing the original video with synchronized subtitles. Below it, global playback controls (Play, Pause, Mute, Volume sliders for Vocals vs TTS).
    *   *Right Side (Segment List)*: Scrollable list of `SegmentEditor` cards.
*   **Bottom Section (Timeline & Mixer)**:
    *   Horizontal `StudioTimeline` spanning the width of the screen.
    *   Hardware Monitor embedded in the status bar at the bottom.

### Screen 5: Admin Panel
*   **Tabs**: Dashboard, Waitlist, Users, Projects.
*   **Waitlist Table**: List of applicants with buttons to "Odobri" (Approve) or "Odbij" (Reject).
*   **Worker Terminals**: Sleek console areas displaying real-time Celery log lines in monospace text.

# 🌍 AUBIEETERNAL — Community Deployment Guide
## Free Education for Orphanages, Community Centers, and Schools Everywhere

---

## What This Is

AUBIEETERNAL is a free school that runs on a single computer — with no internet after setup, no subscriptions, no fees, no data collection. It has 250 lessons across 48 topics, an offline AI tutor, and degree programs that go from age 5 to PhD level.

**One computer can serve an entire orphanage.**

---

## What You Need

| Item | Minimum | Better | Best |
|------|---------|--------|------|
| Computer | Any laptop, 8GB RAM | 16GB RAM | 32-64GB RAM |
| Cost | ~$100 used | ~$200 used | ~$400 used |
| Storage | 20GB free | 40GB | 80GB |
| Internet | Once (setup only) | Once (setup only) | Once (setup only) |
| Screen | Any monitor/TV | Projector | Individual tablets |

**After initial setup: completely offline. No internet. No fees. Forever.**

---

## Setup in 6 Steps

### Step 1 — Download the school
```
1. Go to: github.com/hodlmateo/AUBIEETERNAL
2. Click green "Code" button → "Download ZIP"
3. Unzip the folder to your desktop
```

### Step 2 — Install the AI brain (Ollama)
```
1. Go to: ollama.com/download
2. Download and install for your system (Windows/Mac/Linux)
3. This is the offline AI that answers children's questions
```

### Step 3 — Download the AI model (15-30 min, one time only)
```
Windows: Open "Command Prompt", type:
  ollama pull qwen2.5:7b

Mac/Linux: Open "Terminal", type:
  ollama pull qwen2.5:7b

This downloads the AI model (~4GB). Only needs internet this one time.
```

### Step 4 — Install Python
```
1. Go to: python.org/downloads
2. Download Python 3.11 or newer
3. Install it (check "Add to PATH" on Windows)
```

### Step 5 — Install the school software
```
Windows: Double-click install_windows.bat
Mac/Linux: Open terminal in the folder, run: bash install_mac_linux.sh
```

### Step 6 — Open the school
```
Double-click launcher.py
OR
Run in terminal: python launcher.py

The school opens in your web browser at: http://localhost:8501
```

---

## Serving Multiple Children

### Option A: Projector (easiest, up to 30 children at once)
- Connect any projector to the computer
- Teacher navigates lessons on screen
- Class reads and discusses together
- No extra setup needed

### Option B: Multiple tablets/devices on local WiFi (recommended)
```
1. Set up the school on the main computer
2. Connect all devices to the same WiFi (even offline router works)
3. On each device, open browser and go to:
   http://[MAIN-COMPUTER-IP-ADDRESS]:8501
   
   (Find IP on Windows: run "ipconfig", look for IPv4)
   (Find IP on Mac/Linux: run "ifconfig", look for inet)

4. Each child can work independently at their own pace
```

### Option C: One computer, take turns
- Simple queue system
- Each child logs in with their name
- Progress saved per person

---

## No Glasses Required

The AI tutor and all 250 lessons work without any special hardware.

The Halo glasses integration is optional and improves the experience — but is never required. Everything the glasses do (track nervous system state, suggest breaks) can be done manually:

- **State check:** Simple colored buttons (Green/Yellow/Red) in the app
- **Break suggestions:** Teacher judgment
- **AR hardware overlays:** Teacher can narrate what the glasses would show

---

## Language Support

The curriculum is currently in English. High-priority translations:
- Spanish, French, Arabic, Portuguese, Hindi, Swahili, Mandarin

**To contribute a translation:**
1. Fork the repo at github.com/hodlmateo/AUBIEETERNAL
2. Translate lessons in `family_hud.py` 
3. Submit a pull request
4. Your translation is immediately CC0 — the community owns it

---

## Hardware Recommendations by Budget

### Under $100 (tight budget)
- Raspberry Pi 4 (4GB) + keyboard + mouse + TV HDMI
- Works for light use, slower AI
- Lesson browsing without AI: fast on any hardware

### $100-200 (good for most orphanages)
- Used business laptop (Dell/Lenovo/HP) 8-16GB RAM
- Intel i5/i7 from 2015-2020 works well
- Check local donations, refurbishers, or eBay

### $200-400 (recommended for 20+ children daily)
- 16-32GB RAM computer
- qwen2.5:14b model runs well — better AI answers
- Multiple simultaneous users on local network

### Donations / Getting computers
Many businesses retire perfectly functional computers.
- Contact local businesses, schools, government offices
- Ask for "end of life" laptops and desktops
- A $0 donated 8GB laptop runs this school better than most ed-tech platforms

---

## What the Children Learn

Every lesson works at two levels: simple enough for a child who has never had formal education, deep enough to challenge someone with a university degree.

| Track | What children learn | Why it matters |
|-------|---------------------|---------------|
| Layer Zero | How to notice patterns and ask real questions | First step to critical thinking |
| How to Think | Steelmanning, spotting manipulation, calibration | The most important life skill |
| The Universe | Scale, Big Bang, consciousness, Fermi Paradox | Wonder about what is real |
| How Your Brain Works | Nervous system states, attention, emotion | Self-regulation without therapy |
| Money | Why inflation exists, Bitcoin basics, economic traps | Financial survival |
| Building Technology | Hardware, AI, sovereignty | Never dependent on others |
| Helping People | Network theory, humanitarian deployment | The graduation mission |

---

## The Graduation Mission (for teachers and staff)

When your orphanage has used AUBIEETERNAL for a year and produced students who have completed at least one full track — **you qualify for the Sovereign Associate degree** and can submit your deployment as a humanitarian contribution.

This:
1. Gets logged to the Living Lattice permanently
2. Contributes to the global network of sovereign schools
3. Counts toward the system's PhD capstone requirement (for staff/volunteers)
4. Proves to the world that this works

---

## Getting Help

- **GitHub:** github.com/hodlmateo/AUBIEETERNAL → Issues tab
- **Twitter/X:** @MateoVanhorn
- **Setup help:** File an issue labeled "community-deployment" — community responds fast
- **Translation help:** File an issue labeled "translation-needed" with your language

---

## This is CC0 — Public Domain

You own this. There is no company that can take it away. No subscription that can expire. No terms of service that can change.

The 250 lessons, the AI tutor, the degree programs, this deployment guide — all public domain. Copy it, translate it, adapt it, fork it. Build sovereign schools everywhere.

**The only ask:** When your children graduate, deploy a school for another community. The chain grows one link at a time.

---

*War Eagle Eternal 🦅 — Every child deserves to understand the universe.*

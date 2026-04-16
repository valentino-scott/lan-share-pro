# 🚀 Kali LAN Share — Offline File Sharing System

<p align="center">
  <img src="assets/session-ui.png" width="900"/>
</p>

<p align="center">
  <b>⚡ Secure • Offline • Lightning Fast LAN File Sharing</b>
</p>

---

A **high-performance LAN-based file sharing + chat system** built with **FastAPI**, designed for **offline environments**.

No internet. No setup complexity. Just **connect → share → done**.

---

## ✨ Features

* ⚡ **Ultra-fast local file sharing** (up to 10GB per file)
* 📡 **LAN-only access** — zero internet dependency
* 🔗 **Session-based sharing system**
* 📱 **QR code instant join**
* 💬 **Real-time chat with copy button**
* 📊 **Download tracking per user**
* 👥 **Live peer detection**
* 🧹 **Auto-cleanup sessions**
* 👀 **File preview (images & text)**
* 📋 **Sticky copy for messages (dev-friendly)**

---

## 📸 Screenshots

### 🏠 Home Interface

<p align="center">
  <img src="assets/home.png" width="800"/>
</p>

---

### 🔗 Create Session + QR Sharing

<p align="center">
  <img src="assets/create-session.png" width="800"/>
</p>

---

### 💻 Live Session Dashboard

<p align="center">
  <img src="assets/session-ui.png" width="800"/>
</p>

---

### 📂 File Upload & Download

<p align="center">
  <img src="assets/file-upload.png" width="800"/>
</p>

---

### 💬 Built-in Chat System

<p align="center">
  <img src="assets/chat.png" width="800"/>
</p>

---

## 🧠 How It Works

```text
Start Server → Create Session → Share Link/QR → Join → Transfer Files
```

1. Run the server
2. Create a session
3. Share link or QR
4. Others join via LAN
5. Upload/download instantly

---

## 📦 Requirements

* Python **3.9+**
* pip

---

## ⚙️ Installation

### 🪟 Windows

```bash
git clone https://github.com/valentino-scott/kali-lan-share.git
cd kali-lan-share

python -m venv venv
venv\Scripts\activate

pip install fastapi uvicorn python-multipart qrcode[pil]

python share.py
```

---

### 🐧 Linux (Kali / Ubuntu / Debian)

```bash
git clone https://github.com/valentino-scott/kali-lan-share.git
cd kali-lan-share

python3 -m venv venv
source venv/bin/activate

pip install fastapi uvicorn python-multipart qrcode[pil]

python3 share.py
```

---

### 🍎 macOS

```bash
git clone https://github.com/valentino-scott/kali-lan-share.git
cd kali-lan-share

python3 -m venv venv
source venv/bin/activate

pip install fastapi uvicorn python-multipart qrcode[pil]

python3 share.py
```

---

## ▶️ Usage

After running:

```bash
Local:   http://localhost:8000
Network: http://192.168.x.x:8000
```

### Quick Start

1. Open → `http://localhost:8000`
2. Click **Create Session**
3. Share:

   * Link
   * QR Code
4. Join via:

   ```
   http://YOUR-IP:8000/session/<SESSION_ID>
   ```

---

## 📂 Project Structure

```bash
.
├── share.py        # FastAPI backend
├── assets/         # Screenshots
└── README.md
```

---

## ⚡ Performance

| Method                 | Performance               |
| ---------------------- | ------------------------- |
| FastAPI (this project) | 🚀 High                   |
| python http.server     | 🐢 Basic                  |
| NGINX                  | ⚡ Very High (static only) |

✔ Handles **large files (GBs)**
✔ Supports **multiple users concurrently**

---

## 🔐 Security

* Designed for **local network only**
* No authentication (intentional for speed)

⚠️ If exposing externally:

* Add reverse proxy (NGINX)
* Add authentication

---

## 🧹 Session Lifecycle

* Default timeout: **60 minutes**
* Auto deletes:

  * Files
  * Messages
  * Sessions

---

## 🛠️ Tech Stack

* **Backend:** FastAPI
* **Server:** Uvicorn
* **Frontend:** HTML / CSS / JS
* **QR:** qrcode
* **Async Engine:** asyncio

---

## 📌 Use Cases

* 🏫 Classroom file sharing
* 🧑‍💻 Cybersecurity labs (Kali Linux)
* 🏢 Office LAN transfers
* ⚡ Quick file drops without internet

---

## 📄 Source Code

Main file:
👉 `share.py`

Repository:
👉 https://github.com/valentino-scott/kali-lan-share

---

## 🚀 Roadmap

* 🔐 Authentication system
* 📁 Folder uploads
* 🔄 Drag & drop UI
* 📡 WebRTC P2P transfer
* 📱 Mobile UI improvements

---

## 🧑‍💻 Author

**valentino-scott (traders_fx / Lennox_fx)**
Kenyan developer • Forex trader

---

## ⭐ Support

If you like this project:

* ⭐ Star the repo
* 🍴 Fork it
* 🚀 Improve it

---

## ⚠️ Disclaimer

For **local network use only**.
Use responsibly.

---

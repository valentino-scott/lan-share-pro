# share.py - Complete fixed version with double-click copy
"""
Kali LAN Share - Professional Offline File Sharing System
Run with: python share.py
"""

import os
import shutil
import uuid
import tempfile
import asyncio
import socket
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import qrcode
from io import BytesIO
import base64

# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class DownloadRecord:
    client_id: str
    client_ip: str
    downloaded_at: str

@dataclass
class FileMetadata:
    file_id: str
    original_filename: str
    size: int
    upload_timestamp: str
    storage_path: str
    mime_type: str
    downloads: List[DownloadRecord] = field(default_factory=list)
    
    def to_dict(self, client_id: str = None) -> dict:
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "size": self.size,
            "size_formatted": self.format_size(),
            "upload_timestamp": self.upload_timestamp,
            "download_count": len(self.downloads),
            "downloaded_by_me": client_id in [d.client_id for d in self.downloads] if client_id else False,
            "mime_type": self.mime_type,
            "previewable": self.is_previewable()
        }
    
    def format_size(self) -> str:
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def is_previewable(self) -> bool:
        preview_types = ['image/', 'text/']
        return any(self.mime_type.startswith(t) for t in preview_types)

@dataclass
class Message:
    message_id: str
    content: str
    timestamp: str
    client_ip: str
    client_id: str

@dataclass
class Session:
    session_id: str
    created_at: datetime
    last_activity: datetime
    timeout_minutes: int
    files: Dict[str, FileMetadata] = field(default_factory=dict)
    messages: List[Message] = field(default_factory=list)
    clients: Dict[str, str] = field(default_factory=dict)
    storage_path: Path = None
    
    def __post_init__(self):
        if not self.storage_path:
            self.storage_path = Path(tempfile.gettempdir()) / f"kali_share_{self.session_id}"
            self.storage_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() - self.last_activity > timedelta(minutes=self.timeout_minutes)
    
    def update_activity(self):
        self.last_activity = datetime.now()
    
    def add_client(self, client_id: str, ip_address: str):
        self.clients[client_id] = ip_address
        self.update_activity()
    
    def remove_client(self, client_id: str):
        if client_id in self.clients:
            del self.clients[client_id]
        self.update_activity()
    
    def get_peer_count(self) -> int:
        return len(self.clients)

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(self, timeout_minutes: int = 60) -> Session:
        session_id = str(uuid.uuid4())[:8]
        async with self._lock:
            session = Session(
                session_id=session_id,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                timeout_minutes=timeout_minutes
            )
            self.sessions[session_id] = session
            return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        async with self._lock:
            session = self.sessions.get(session_id)
        if session and session.is_expired:
            await self.delete_session(session_id)
            return None
        if session:
            session.update_activity()
        return session
    
    async def delete_session(self, session_id: str):
        async with self._lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if session.storage_path.exists():
                    shutil.rmtree(session.storage_path)
                del self.sessions[session_id]
    
    async def cleanup_expired(self):
        async with self._lock:
            expired = [sid for sid, s in self.sessions.items() if s.is_expired]
        for sid in expired:
            await self.delete_session(sid)

# ============================================================================
# FASTAPI APP
# ============================================================================

session_manager = SessionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(cleanup_worker())
    local_ip = get_local_ip()
    print(f"\n{'='*60}")
    print(f"KALI LAN SHARE - Professional File Sharing")
    print(f"{'='*60}")
    print(f"\n➜ Local:    http://localhost:8000")
    print(f"➜ Network:  http://{local_ip}:8000")
    print(f"\n➜ Features: File sharing, preview, download tracking")
    print(f"➜ Max file size: 10GB")
    print(f"➜ Session timeout: 60 minutes (auto-cleanup)")
    print(f"\nPress Ctrl+C to stop\n")
    yield
    for session in list(session_manager.sessions.values()):
        await session_manager.delete_session(session.session_id)

app = FastAPI(title="Kali LAN Share", lifespan=lifespan)

async def cleanup_worker():
    while True:
        await asyncio.sleep(30)
        await session_manager.cleanup_expired()

# ============================================================================
# HOME PAGE
# ============================================================================

HOME_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Kali LAN Share</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --kali-blue: #2C5F8A;
            --kali-blue-light: #3A7BA8;
            --kali-bg: #0D1117;
            --kali-card: #161B22;
            --kali-border: #30363D;
            --kali-text: #E6EDF3;
            --kali-text-dim: #8B949E;
            --kali-success: #238636;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Cantarell', 'Ubuntu', sans-serif;
            background: var(--kali-bg);
            color: var(--kali-text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .header {
            background: var(--kali-card);
            border-bottom: 1px solid var(--kali-border);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-content {
            max-width: 1200px;
            margin: 0 auto;
        }

        .logo h1 {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--kali-blue-light);
        }

        .logo p {
            font-size: 0.7rem;
            color: var(--kali-text-dim);
        }

        .main-container {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }

        .container {
            max-width: 1000px;
            width: 100%;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }

        .card {
            background: var(--kali-card);
            border: 1px solid var(--kali-border);
            border-radius: 12px;
            padding: 2rem;
            transition: transform 0.2s, border-color 0.2s;
        }

        .card:hover {
            border-color: var(--kali-blue);
            transform: translateY(-2px);
        }

        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--kali-blue);
            color: var(--kali-blue-light);
        }

        .form-group {
            margin-bottom: 1.25rem;
        }

        label {
            display: block;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--kali-text-dim);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        input {
            width: 100%;
            padding: 0.75rem 1rem;
            background: var(--kali-bg);
            border: 1px solid var(--kali-border);
            border-radius: 8px;
            font-size: 0.9rem;
            color: var(--kali-text);
            transition: all 0.2s;
        }

        input:focus {
            outline: none;
            border-color: var(--kali-blue);
            box-shadow: 0 0 0 3px rgba(44, 95, 138, 0.1);
        }

        .btn {
            width: 100%;
            padding: 0.85rem;
            background: var(--kali-blue);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .btn:hover {
            background: var(--kali-blue-light);
            transform: translateY(-1px);
        }

        .result-box {
            margin-top: 1.5rem;
            padding: 1.25rem;
            background: var(--kali-bg);
            border-radius: 10px;
            display: none;
            text-align: center;
        }

        .result-box.show {
            display: block;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .session-url {
            background: var(--kali-card);
            padding: 0.75rem;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.75rem;
            word-break: break-all;
            margin: 1rem 0;
            border: 1px solid var(--kali-border);
        }

        .qr-wrapper {
            text-align: center;
            margin: 1.5rem 0;
            padding: 1rem;
            background: white;
            border-radius: 10px;
            display: inline-block;
            width: 100%;
        }

        .qr-wrapper img {
            max-width: 160px;
            border-radius: 8px;
        }

        .info-text {
            grid-column: 1 / -1;
            text-align: center;
            padding: 1rem;
            background: var(--kali-card);
            border-radius: 10px;
            color: var(--kali-text-dim);
            font-size: 0.8rem;
        }

        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
                gap: 1rem;
            }
            .header { padding: 0.75rem 1rem; }
            .main-container { padding: 1rem; }
            .card { padding: 1.5rem; }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <h1>KALI LAN SHARE</h1>
                <p>SECURE · OFFLINE · LIGHTNING FAST</p>
            </div>
        </div>
    </header>
    
    <div class="main-container">
        <div class="container">
            <div class="card">
                <div class="card-title">CREATE SESSION</div>
                <form id="createForm">
                    <div class="form-group">
                        <label>SESSION TIMEOUT (MINUTES)</label>
                        <input type="number" id="timeout" value="60" min="5" max="480">
                    </div>
                    <button type="submit" class="btn">INITIATE SESSION</button>
                </form>
                <div id="result" class="result-box"></div>
            </div>
            
            <div class="card">
                <div class="card-title">JOIN SESSION</div>
                <form id="joinForm">
                    <div class="form-group">
                        <label>SESSION ID</label>
                        <input type="text" id="sessionId" placeholder="a1b2c3d4" required>
                    </div>
                    <button type="submit" class="btn">CONNECT</button>
                </form>
            </div>
            
            <div class="info-text">
                CREATE A SESSION → SHARE LINK OR QR CODE → PARTICIPANTS CAN UPLOAD/DOWNLOAD INSTANTLY
            </div>
        </div>
    </div>
    
    <script>
        const createForm = document.getElementById('createForm');
        const joinForm = document.getElementById('joinForm');
        
        createForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const timeout = document.getElementById('timeout').value;
            
            const response = await fetch('/api/session/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({timeout_minutes: parseInt(timeout)})
            });
            
            const data = await response.json();
            const resultDiv = document.getElementById('result');
            
            resultDiv.innerHTML = `
                <div>
                    <strong style="color: var(--kali-success);">✓ SESSION ACTIVATED</strong>
                    <div class="session-url">${data.join_url}</div>
                    <div class="qr-wrapper">
                        <img src="data:image/png;base64,${data.qr_code}" alt="QR">
                    </div>
                    <button onclick="window.location.href='/session/${data.session_id}'" class="btn" style="background: var(--kali-success);">OPEN SESSION</button>
                </div>
            `;
            resultDiv.classList.add('show');
        });
        
        joinForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const sessionId = document.getElementById('sessionId').value.trim();
            if (sessionId) window.location.href = '/session/' + sessionId;
        });
    </script>
</body>
</html>
"""

# ============================================================================
# SESSION PAGE - DOUBLE CLICK TO COPY, FIXED UI
# ============================================================================



SESSION_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>KALI SHARE · {session_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --kali-blue: #2C5F8A;
            --kali-blue-light: #3A7BA8;
            --kali-bg: #0D1117;
            --kali-card: #161B22;
            --kali-border: #30363D;
            --kali-text: #E6EDF3;
            --kali-text-dim: #8B949E;
            --kali-success: #238636;
            --kali-danger: #DA3633;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Cantarell', 'Ubuntu', sans-serif;
            background: var(--kali-bg);
            color: var(--kali-text);
            min-height: 100vh;
        }}

        .header {{
            background: var(--kali-card);
            border-bottom: 1px solid var(--kali-border);
            padding: 0.75rem 1.5rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .header-content {{
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .session-info {{
            display: flex;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
        }}

        .session-badge {{
            background: var(--kali-bg);
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-family: monospace;
            font-size: 0.8rem;
            border: 1px solid var(--kali-border);
            color: var(--kali-blue-light);
        }}

        .stats {{
            display: flex;
            gap: 1rem;
        }}

        .stat {{
            font-size: 0.8rem;
            color: var(--kali-text-dim);
        }}

        .stat-value {{
            color: var(--kali-blue-light);
            font-weight: 700;
            font-size: 1rem;
            margin-left: 0.3rem;
        }}

        .nav-buttons {{
            display: flex;
            gap: 0.5rem;
        }}

        .btn-icon {{
            background: var(--kali-bg);
            border: 1px solid var(--kali-border);
            padding: 0.4rem 1rem;
            border-radius: 6px;
            color: var(--kali-text);
            cursor: pointer;
            font-size: 0.8rem;
            transition: all 0.2s;
        }}

        .btn-icon:hover {{
            border-color: var(--kali-blue);
            color: var(--kali-blue-light);
        }}

        .main-container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 1.5rem;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}

        .panel {{
            background: var(--kali-card);
            border: 1px solid var(--kali-border);
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            height: calc(100vh - 100px);
            min-height: 500px;
        }}

        .panel-header {{
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--kali-border);
            background: var(--kali-bg);
        }}

        .panel-header h2 {{
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--kali-blue-light);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .upload-area {{
            padding: 1.5rem;
            border-bottom: 1px solid var(--kali-border);
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            background: var(--kali-bg);
        }}

        .upload-area:hover {{
            background: var(--kali-card);
            border-color: var(--kali-blue);
        }}

        .upload-icon {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            opacity: 0.7;
        }}

        .progress-container {{
            height: 2px;
            background: var(--kali-border);
            display: none;
        }}

        .progress-bar {{
            height: 100%;
            background: var(--kali-blue);
            width: 0%;
            transition: width 0.3s;
        }}

        .file-list {{
            flex: 1;
            overflow-y: auto;
            padding: 0.5rem;
        }}

        .file-item {{
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            border-radius: 8px;
            transition: all 0.2s;
        }}

        .file-item:hover {{
            background: var(--kali-bg);
        }}

        .file-item.downloaded {{
            border-left: 3px solid var(--kali-success);
        }}

        .file-info {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}

        .file-preview {{
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }}

        .file-details {{
            flex: 1;
            min-width: 120px;
        }}

        .file-name {{
            font-weight: 600;
            font-size: 0.85rem;
            margin-bottom: 0.2rem;
            word-break: break-word;
        }}

        .file-meta {{
            font-size: 0.7rem;
            color: var(--kali-text-dim);
        }}

        .file-badge {{
            display: inline-block;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            font-size: 0.6rem;
            font-weight: 600;
            margin-left: 0.5rem;
            background: rgba(35, 134, 54, 0.2);
            color: var(--kali-success);
        }}

        .file-actions {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}

        .file-actions button {{
            padding: 0.4rem 0.8rem;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
        }}

        .btn-download {{
            background: var(--kali-blue);
            color: white;
        }}

        .btn-download:hover {{
            background: var(--kali-blue-light);
        }}

        .btn-downloaded {{
            background: var(--kali-success);
            color: white;
        }}

        .btn-delete {{
            background: transparent;
            border: 1px solid var(--kali-danger);
            color: var(--kali-danger);
        }}

        .btn-delete:hover {{
            background: var(--kali-danger);
            color: white;
        }}

        .btn-preview {{
            background: transparent;
            border: 1px solid var(--kali-blue);
            color: var(--kali-blue-light);
        }}

        /* Chat Messages */
        .messages-container {{
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .message {{
            position: relative;
            padding: 1rem;
            padding-right: 3rem;
            background: var(--kali-bg);
            border-radius: 12px;
            transition: all 0.2s;
            border: 1px solid var(--kali-border);
        }}

        .message:hover {{
            border-color: var(--kali-blue);
            background: var(--kali-card);
        }}

        .message-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
            font-size: 0.7rem;
            color: var(--kali-text-dim);
        }}

        .message-content {{
            font-size: 0.9rem;
            line-height: 1.5;
            word-break: break-word;
            white-space: pre-wrap;
            max-width: 100%;
            overflow-x: auto;
        }}

        /* Code blocks styling */
        .message-content pre {{
            margin: 0.5rem 0;
            padding: 1rem;
            background: #0a0a0f;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.8rem;
        }}

        .message-content code {{
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 0.85rem;
            background: rgba(44, 95, 138, 0.2);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
        }}

        .message-content pre code {{
            background: transparent;
            padding: 0;
        }}

        /* Copy Icon Button */
        .copy-icon {{
            position: absolute;
            top: 0.75rem;
            right: 0.75rem;
            background: var(--kali-card);
            border: 1px solid var(--kali-border);
            border-radius: 6px;
            padding: 0.25rem 0.5rem;
            cursor: pointer;
            opacity: 0.6;
            transition: all 0.2s;
            font-size: 0.75rem;
            color: var(--kali-text-dim);
            z-index: 10;
        }}

        .copy-icon:hover {{
            opacity: 1;
            background: var(--kali-blue);
            color: white;
            border-color: var(--kali-blue);
        }}

        /* Copy animation */
        .copy-flash {{
            animation: copyFlash 0.3s ease;
        }}

        @keyframes copyFlash {{
            0% {{ background-color: var(--kali-bg); }}
            50% {{ background-color: var(--kali-success); }}
            100% {{ background-color: var(--kali-bg); }}
        }}

        .message-input-area {{
            padding: 1rem;
            border-top: 1px solid var(--kali-border);
            background: var(--kali-bg);
        }}

        .message-form {{
            display: flex;
            gap: 0.5rem;
        }}

        .message-input {{
            flex: 1;
            padding: 0.75rem;
            background: var(--kali-card);
            border: 1px solid var(--kali-border);
            border-radius: 8px;
            color: var(--kali-text);
            font-family: inherit;
            resize: vertical;
            font-size: 0.85rem;
            line-height: 1.4;
        }}

        .message-input:focus {{
            outline: none;
            border-color: var(--kali-blue);
        }}

        .send-btn {{
            padding: 0.75rem 1.5rem;
            background: var(--kali-blue);
            border: none;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.8rem;
            white-space: nowrap;
            transition: all 0.2s;
        }}

        .send-btn:hover {{
            background: var(--kali-blue-light);
        }}

        .empty-state {{
            text-align: center;
            padding: 2rem;
            color: var(--kali-text-dim);
            font-size: 0.8rem;
        }}

        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}

        .modal.active {{
            display: flex;
        }}

        .modal-content {{
            max-width: 90%;
            max-height: 90%;
            background: var(--kali-card);
            border-radius: 12px;
            overflow: hidden;
        }}

        .modal-header {{
            padding: 1rem;
            border-bottom: 1px solid var(--kali-border);
            display: flex;
            justify-content: space-between;
        }}

        .modal-body {{
            padding: 1rem;
            text-align: center;
            max-height: 80vh;
            overflow: auto;
        }}

        .modal-body img {{
            max-width: 100%;
            max-height: 70vh;
        }}

        .modal-body pre {{
            text-align: left;
            background: var(--kali-bg);
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.8rem;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .close-modal {{
            cursor: pointer;
            font-size: 1.2rem;
        }}

        .toast {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: var(--kali-success);
            color: white;
            padding: 0.7rem 1.2rem;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        }}

        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}

        ::-webkit-scrollbar {{
            width: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: var(--kali-bg);
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--kali-border);
            border-radius: 3px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--kali-blue);
        }}

        @media (max-width: 900px) {{
            .main-container {{
                grid-template-columns: 1fr;
                gap: 1rem;
                padding: 1rem;
            }}
            .panel {{
                height: auto;
                min-height: 400px;
                max-height: 60vh;
            }}
            .header {{
                padding: 0.5rem 1rem;
            }}
            .header-content {{
                flex-direction: column;
                align-items: stretch;
            }}
            .session-info {{
                justify-content: space-between;
            }}
            .file-info {{
                flex-direction: column;
                align-items: flex-start;
            }}
            .file-actions {{
                width: 100%;
                justify-content: flex-end;
            }}
            .send-btn {{
                padding: 0.7rem 1rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="session-info">
                <div class="session-badge">SESSION [{session_id}]</div>
                <div class="stats">
                    <div class="stat">📁 <span class="stat-value" id="fileCount">0</span></div>
                    <div class="stat">💬 <span class="stat-value" id="msgCount">0</span></div>
                    <div class="stat">👥 <span class="stat-value" id="peerCount">1</span></div>
                </div>
            </div>
            <div class="nav-buttons">
                <button class="btn-icon" onclick="refreshAll()">⟳ SYNC</button>
                <button class="btn-icon" onclick="window.location.href='/'">⌂ EXIT</button>
            </div>
        </div>
    </div>
    
    <div class="main-container">
        <div class="panel">
            <div class="panel-header"><h2>📂 FILE TRANSFER</h2></div>
            <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📤</div>
                <div>UPLOAD FILES</div>
                <div style="font-size: 0.7rem; color: var(--kali-text-dim);">MAX 10GB PER FILE</div>
            </div>
            <input type="file" id="fileInput" multiple style="display: none">
            <div class="progress-container" id="progressContainer">
                <div class="progress-bar" id="progressBar"></div>
            </div>
            <div class="file-list" id="fileList"><div class="empty-state">NO FILES</div></div>
        </div>
        
        <div class="panel">
            <div class="panel-header"><h2>💬 CHAT</h2></div>
            <div class="messages-container" id="messages"><div class="empty-state">NO MESSAGES</div></div>
            <div class="message-input-area">
                <form id="messageForm" class="message-form">
                    <textarea id="msgInput" class="message-input" rows="3" placeholder="Type your message... Click the copy icon or double-click any message to copy!"></textarea>
                    <button type="submit" class="send-btn">SEND</button>
                </form>
            </div>
        </div>
    </div>
    
    <div id="previewModal" class="modal">
        <div class="modal-content">
            <div class="modal-header"><span>PREVIEW</span><span class="close-modal" onclick="closePreview()">×</span></div>
            <div class="modal-body" id="previewBody"></div>
        </div>
    </div>
    
    <script>
        const sessionId = '{session_id}';
        
        let clientId = localStorage.getItem(`kali_client_${{sessionId}}`);
        if (!clientId) {{
            clientId = 'kali_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem(`kali_client_${{sessionId}}`, clientId);
        }}
        
        let downloadedFiles = new Set(JSON.parse(localStorage.getItem(`downloaded_${{sessionId}}`) || '[]'));
        
        function saveDownloaded(fileId) {{
            downloadedFiles.add(fileId);
            localStorage.setItem(`downloaded_${{sessionId}}`, JSON.stringify([...downloadedFiles]));
        }}
        
        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        async function loadFiles() {{
            try {{
                const res = await fetch(`/api/session/${{sessionId}}/files?client=${{clientId}}`);
                const data = await res.json();
                const files = Object.values(data.files || {{}});
                document.getElementById('fileCount').textContent = files.length;
                
                const container = document.getElementById('fileList');
                if (!files.length) {{
                    container.innerHTML = '<div class="empty-state">NO FILES</div>';
                    return;
                }}
                
                container.innerHTML = files.map(file => `
                    <div class="file-item ${{file.downloaded_by_me ? 'downloaded' : ''}}">
                        <div class="file-info">
                            <div class="file-preview">📄</div>
                            <div class="file-details">
                                <div class="file-name">${{escapeHtml(file.original_filename)}}
                                    ${{file.downloaded_by_me ? '<span class="file-badge">DOWNLOADED</span>' : ''}}
                                </div>
                                <div class="file-meta">${{file.size_formatted}} · ${{file.download_count}} DOWNLOADS</div>
                            </div>
                            <div class="file-actions">
                                ${{file.previewable ? `<button class="btn-preview" onclick="previewFile('${{file.file_id}}')">PREVIEW</button>` : ''}}
                                <button class="btn-download ${{file.downloaded_by_me ? 'btn-downloaded' : ''}}" onclick="downloadFile('${{file.file_id}}')">
                                    ${{file.downloaded_by_me ? 'DOWNLOADED' : 'DOWNLOAD'}}
                                </button>
                                <button class="btn-delete" onclick="deleteFile('${{file.file_id}}')">DELETE</button>
                            </div>
                        </div>
                    </div>
                `).join('');
            }} catch (error) {{
                console.error('Error loading files:', error);
            }}
        }}
        
        async function previewFile(fileId) {{
            const res = await fetch(`/api/session/${{sessionId}}/preview/${{fileId}}`);
            if (res.ok) {{
                const data = await res.json();
                const modal = document.getElementById('previewModal');
                const body = document.getElementById('previewBody');
                
                if (data.type === 'image') {{
                    body.innerHTML = `<img src="data:${{data.mime}};base64,${{data.content}}">`;
                }} else if (data.type === 'text') {{
                    body.innerHTML = `<pre>${{escapeHtml(data.content)}}</pre>`;
                }}
                modal.classList.add('active');
            }}
        }}
        
        function closePreview() {{
            document.getElementById('previewModal').classList.remove('active');
        }}
        
        function copyMessage(text, element) {{
            navigator.clipboard.writeText(text).then(() => {{
                if (element) {{
                    element.classList.add('copy-flash');
                }}
                showToast('✓ Copied to clipboard');
                setTimeout(() => {{
                    if (element) {{
                        element.classList.remove('copy-flash');
                    }}
                }}, 300);
            }}).catch(() => {{
                showToast('✗ Failed to copy');
            }});
        }}
        
        async function loadMessages() {{
            try {{
                const res = await fetch(`/api/session/${{sessionId}}/messages`);
                const data = await res.json();
                document.getElementById('msgCount').textContent = data.messages.length;
                
                const container = document.getElementById('messages');
                if (!data.messages.length) {{
                    container.innerHTML = '<div class="empty-state">NO MESSAGES</div>';
                    return;
                }}
                
                container.innerHTML = data.messages.map((msg, idx) => `
                    <div class="message" data-message-idx="${{idx}}">
                        <div class="message-header">
                            <span>💬 ${{escapeHtml(msg.client_ip)}}</span>
                            <span>${{new Date(msg.timestamp).toLocaleTimeString()}}</span>
                        </div>
                        <div class="message-content">${{escapeHtml(msg.content)}}</div>
                        <button class="copy-icon" onclick="event.stopPropagation(); copyMessage(this.parentElement.querySelector('.message-content').innerText, this.parentElement)">📋 COPY</button>
                    </div>
                `).join('');
                
                // Add double-click event listeners to all messages
                document.querySelectorAll('.message').forEach(msgElement => {{
                    msgElement.addEventListener('dblclick', function(e) {{
                        e.stopPropagation();
                        const text = this.querySelector('.message-content').innerText;
                        copyMessage(text, this);
                    }});
                }});
            }} catch (error) {{
                console.error('Error loading messages:', error);
            }}
        }}
        
        async function loadPeers() {{
            try {{
                const res = await fetch(`/api/session/${{sessionId}}/info`);
                const data = await res.json();
                document.getElementById('peerCount').textContent = data.client_count;
            }} catch (error) {{
                console.error('Error loading peers:', error);
            }}
        }}
        
        async function sendMessage() {{
            const input = document.getElementById('msgInput');
            const content = input.value.trim();
            if (!content) {{
                showToast('Cannot send empty message');
                return;
            }}
            
            try {{
                const response = await fetch(`/api/session/${{sessionId}}/message`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        content: content,
                        client_id: clientId
                    }})
                }});
                
                if (response.ok) {{
                    input.value = '';
                    showToast('✓ Message sent');
                    await loadMessages();
                }} else {{
                    showToast('✗ Failed to send');
                }}
            }} catch (error) {{
                console.error('Error sending message:', error);
                showToast('✗ Network error');
            }}
        }}
        
        async function uploadFiles(files) {{
            const progressContainer = document.getElementById('progressContainer');
            const bar = document.getElementById('progressBar');
            
            for (const file of files) {{
                const formData = new FormData();
                formData.append('file', file);
                progressContainer.style.display = 'block';
                
                const xhr = new XMLHttpRequest();
                xhr.upload.onprogress = (e) => {{
                    if (e.lengthComputable) {{
                        const percent = (e.loaded / e.total) * 100;
                        bar.style.width = percent + '%';
                    }}
                }};
                await new Promise((resolve, reject) => {{
                    xhr.onload = () => resolve();
                    xhr.onerror = () => reject();
                    xhr.open('POST', `/api/session/${{sessionId}}/upload`);
                    xhr.send(formData);
                }});
            }}
            progressContainer.style.display = 'none';
            bar.style.width = '0%';
            await loadFiles();
            showToast('UPLOAD COMPLETE');
        }}
        
        async function downloadFile(fileId) {{
            window.open(`/api/session/${{sessionId}}/download/${{fileId}}?client=${{clientId}}`, '_blank');
            saveDownloaded(fileId);
            showToast('DOWNLOAD STARTED');
            await loadFiles();
        }}
        
        async function deleteFile(fileId) {{
            if (confirm('DELETE THIS FILE?')) {{
                await fetch(`/api/session/${{sessionId}}/file/${{fileId}}`, {{method: 'DELETE'}});
                await loadFiles();
                showToast('FILE DELETED');
            }}
        }}
        
        function showToast(msg) {{
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.textContent = msg;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 2000);
        }}
        
        function refreshAll() {{
            loadFiles(); loadMessages(); loadPeers();
        }}
        
        document.getElementById('fileInput').onchange = (e) => {{
            if (e.target.files.length) uploadFiles(Array.from(e.target.files));
            e.target.value = '';
        }};
        
        document.getElementById('messageForm').onsubmit = (e) => {{
            e.preventDefault();
            sendMessage();
        }};
        
        fetch(`/api/session/${{sessionId}}/register?client=${{clientId}}`);
        
        loadFiles(); loadMessages(); loadPeers();
        setInterval(refreshAll, 3000);
        
        window.addEventListener('beforeunload', () => {{
            fetch(`/api/session/${{sessionId}}/unregister?client=${{clientId}}`, {{method: 'POST'}});
        }});
    </script>
</body>
</html>
"""
# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home():
    return HOME_PAGE

@app.get("/session/{session_id}", response_class=HTMLResponse)
async def session_page(session_id: str, request: Request):
    session = await session_manager.get_session(session_id)
    if not session:
        return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head><title>Session Not Found</title></head>
            <body style="font-family: system-ui; text-align: center; padding: 50px; background: #0D1117; color: #E6EDF3;">
                <h1>404</h1>
                <p>Session not found or expired</p>
                <a href="/" style="color: #2C5F8A;">Create new session →</a>
            </body>
            </html>
        """, status_code=404)
    
    return HTMLResponse(content=SESSION_PAGE.format(session_id=session_id))

@app.get("/api/session/{session_id}/register")
async def register_client(session_id: str, client: str, request: Request):
    session = await session_manager.get_session(session_id)
    if session:
        session.add_client(client, request.client.host)
    return {"success": True}

@app.post("/api/session/{session_id}/unregister")
async def unregister_client(session_id: str, client: str):
    session = await session_manager.get_session(session_id)
    if session:
        session.remove_client(client)
    return {"success": True}

@app.post("/api/session/create")
async def create_session(timeout_minutes: int = 60):
    session = await session_manager.create_session(timeout_minutes)
    server_ip = get_local_ip()
    join_url = f"http://{server_ip}:8000/session/{session.session_id}"
    
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(join_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_code = base64.b64encode(buffered.getvalue()).decode()
    
    return {"session_id": session.session_id, "join_url": join_url, "qr_code": qr_code}

@app.post("/api/session/{session_id}/upload")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10GB)")
    
    file_id = str(uuid.uuid4())[:12]
    safe_name = f"{file_id}_{file.filename.replace('/', '_')}"
    file_path = session.storage_path / safe_name
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    mime_map = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif',
        'txt': 'text/plain', 'py': 'text/x-python', 'js': 'text/javascript', 'html': 'text/html',
        'json': 'application/json', 'xml': 'application/xml', 'pdf': 'application/pdf'
    }
    mime = mime_map.get(ext, 'application/octet-stream')
    
    metadata = FileMetadata(
        file_id=file_id,
        original_filename=file.filename,
        size=len(content),
        upload_timestamp=datetime.now().isoformat(),
        storage_path=str(file_path),
        mime_type=mime
    )
    session.files[file_id] = metadata
    session.update_activity()
    
    return {"file_id": file_id}

@app.get("/api/session/{session_id}/files")
async def list_files(session_id: str, client: str = None):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"files": {fid: f.to_dict(client) for fid, f in session.files.items()}}

@app.get("/api/session/{session_id}/preview/{file_id}")
async def preview_file(session_id: str, file_id: str):
    session = await session_manager.get_session(session_id)
    if not session or file_id not in session.files:
        raise HTTPException(404, "File not found")
    
    meta = session.files[file_id]
    if not meta.is_previewable():
        raise HTTPException(400, "Preview not available")
    
    with open(meta.storage_path, "rb") as f:
        content = f.read(1024 * 1024)
    
    if meta.mime_type.startswith('image/'):
        return {"type": "image", "mime": meta.mime_type, "content": base64.b64encode(content).decode()}
    else:
        try:
            text = content.decode('utf-8', errors='ignore')[:50000]
            return {"type": "text", "content": text}
        except:
            raise HTTPException(400, "Preview not available")

@app.get("/api/session/{session_id}/download/{file_id}")
async def download_file(session_id: str, file_id: str, client: str = None, request: Request = None):
    session = await session_manager.get_session(session_id)
    if not session or file_id not in session.files:
        raise HTTPException(404, "File not found")
    
    meta = session.files[file_id]
    if client:
        download = DownloadRecord(
            client_id=client,
            client_ip=request.client.host if request else "unknown",
            downloaded_at=datetime.now().isoformat()
        )
        meta.downloads.append(download)
        session.update_activity()
    
    return FileResponse(
        path=meta.storage_path,
        filename=meta.original_filename,
        media_type=meta.mime_type
    )

@app.delete("/api/session/{session_id}/file/{file_id}")
async def delete_file(session_id: str, file_id: str):
    session = await session_manager.get_session(session_id)
    if not session or file_id not in session.files:
        raise HTTPException(404, "File not found")
    
    Path(session.files[file_id].storage_path).unlink(missing_ok=True)
    del session.files[file_id]
    session.update_activity()
    return {"success": True}

@app.post("/api/session/{session_id}/message")
async def send_message(session_id: str, request: Request):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    try:
        data = await request.json()
        content = data.get('content', '')
        client_id = data.get('client_id', 'unknown')
        
        if not content:
            raise HTTPException(400, "Message content is empty")
        
        message = Message(
            message_id=str(uuid.uuid4())[:8],
            content=content,
            timestamp=datetime.now().isoformat(),
            client_ip=request.client.host,
            client_id=client_id
        )
        session.messages.append(message)
        session.update_activity()
        
        return {"success": True, "message_id": message.message_id}
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")
        raise HTTPException(400, f"Failed to send message: {str(e)}")

@app.get("/api/session/{session_id}/messages")
async def get_messages(session_id: str):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"messages": [{"client_ip": m.client_ip, "content": m.content, "timestamp": m.timestamp} for m in session.messages]}

@app.get("/api/session/{session_id}/info")
async def session_info(session_id: str):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"client_count": session.get_peer_count(), "file_count": len(session.files), "message_count": len(session.messages)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

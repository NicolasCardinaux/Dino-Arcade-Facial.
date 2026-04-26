import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import pyautogui
import threading
import webview
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import time
import os
import json
import urllib.parse

# --- Configuración de Inteligencia Artificial (MediaPipe) ---
base_options = python.BaseOptions(model_asset_path='face_landmarker.task')
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    num_faces=1,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
detector = vision.FaceLandmarker.create_from_options(options)

# --- Variables Globales ---
current_frame = None
current_mar = 0.0
current_nose_y = 0.0

mar_threshold = 0.05
nose_y_baseline = 0.0
calibrated = False
game_started = False
paused = False

space_pressed = False
down_pressed = False
pyautogui.PAUSE = 0.0

# Colores Dinámicos de Fondo
current_bg_color = "#f7f7f7"
bg_color_bgr = (247, 247, 247)
text_color = (0, 0, 0)

# --- Manejadores del Archivo de Ranking ---
RANKING_FILE = 'ranking.json'

def load_ranking():
    if os.path.exists(RANKING_FILE):
        try:
            with open(RANKING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_ranking(scores):
    with open(RANKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(scores, f, ensure_ascii=False, indent=4)

def get_distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

# --- Servidor HTTP (Archivos Web y Transmisión MJPEG) ---
class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Servir assets del juego local (t-rex-runner) para no depender de internet y evitar CORS
        if self.path.startswith('/t-rex-runner/'):
            try:
                req_path = self.path.split('?')[0]
                rel_path = req_path[len('/t-rex-runner/'):]
                filepath = os.path.join(os.getcwd(), 't-rex-runner', rel_path.replace('/', os.sep))
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    with open(filepath, 'rb') as f:
                        self.send_response(200)
                        if filepath.endswith('.css'): self.send_header('Content-type', 'text/css')
                        elif filepath.endswith('.js'): self.send_header('Content-type', 'application/javascript')
                        elif filepath.endswith('.png'): self.send_header('Content-type', 'image/png')
                        elif filepath.endswith('.html'): self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(f.read())
                else:
                    self.send_response(404)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
            return

        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                if current_frame is not None:
                    ret, jpeg = cv2.imencode('.jpg', current_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    if ret:
                        try:
                            self.wfile.write(b'--jpgboundary\r\n')
                            self.send_header('Content-type', 'image/jpeg')
                            self.send_header('Content-length', str(len(jpeg)))
                            self.end_headers()
                            self.wfile.write(jpeg.tobytes())
                        except:
                            break
                time.sleep(0.05)
        elif self.path == '/calibrate':
            global calibrated, mar_threshold, nose_y_baseline
            mar_threshold = current_mar * 1.5 if current_mar > 0.01 else 0.05
            nose_y_baseline = current_nose_y
            calibrated = True
            self.send_response(200)
            self.end_headers()
        elif self.path.startswith('/pause'):
            global paused
            state = self.path.split('=')[1] if '=' in self.path else '0'
            paused = (state == '1')
            self.send_response(200)
            self.end_headers()
        elif self.path.startswith('/ranking'):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            scores = load_ranking()
            
            if 'reset' in query:
                scores = []
                save_ranking(scores)
            elif 'add_name' in query and 'add_score' in query:
                name = query['add_name'][0]
                try:
                    score = int(query['add_score'][0])
                except:
                    score = 0
                
                existing = next((s for s in scores if s['name'].lower() == name.lower()), None)
                if existing:
                    if score > existing['score']:
                        existing['score'] = score
                else:
                    scores.append({'name': name, 'score': score})
                
                scores.sort(key=lambda x: x['score'], reverse=True)
                scores = scores[:3]
                save_ranking(scores)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(scores).encode('utf-8'))
        elif self.path == '/reset':
            global game_started
            calibrated = False
            game_started = False
            paused = False
            self.send_response(200)
            self.end_headers()
        elif self.path.startswith('/set_dark_mode'):
            global current_bg_color, bg_color_bgr, text_color
            state = self.path.split('=')[1] if '=' in self.path else '0'
            if state == '1':
                current_bg_color = "#202124"
                bg_color_bgr = (36, 33, 32)
                text_color = (255, 255, 255)
            else:
                current_bg_color = "#f7f7f7"
                bg_color_bgr = (247, 247, 247)
                text_color = (0, 0, 0)
            self.send_response(200)
            self.end_headers()
        elif self.path == '/close':
            self.send_response(200)
            self.end_headers()
            os._exit(0)
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """<!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; background: #f7f7f7; font-family: Arial, sans-serif; }
                    
                    /* Transiciones suaves para el modo noche */
                    body, html, #game-container, #bottom-cover, #pip, #leaderboard-container, #instructions-container { 
                        transition: background-color 0.5s ease, color 0.5s ease;
                    }
                    
                    #game-container { 
                        width: 100%; 
                        height: 100%; 
                        position: relative;
                        background: #f7f7f7;
                    }
                    
                    /* Iframe local: No hay problemas de CORS */
                    iframe { 
                        width: 820px; 
                        height: 260px; /* Altura restringida para que el canvas se centre correctamente */
                        border: none; 
                        position: absolute;
                        top: 0px; 
                        left: 20px; 
                        z-index: 1;
                    }
                    
                    #bottom-cover {
                        position: absolute;
                        top: 260px; 
                        left: 0;
                        width: 100%;
                        height: 400px;
                        background-color: #f7f7f7;
                        z-index: 10; 
                    }
                    
                    /* Feed de la cámara PiP */
                    #pip {
                        position: absolute;
                        top: 10px; 
                        right: 20px;
                        width: 320px;
                        border: 3px solid #e0e0e0;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        z-index: 100;
                        background: #f7f7f7;
                        cursor: pointer;
                    }

                    #focus-trap {
                        position: absolute;
                        top: 0; left: 0; width: 100%; height: 100%;
                        z-index: 50; 
                        background: transparent;
                    }
                    
                    /* Controles */
                    #controls-container {
                        position: absolute;
                        top: 260px; 
                        right: 20px;
                        width: 326px; 
                        display: flex;
                        flex-direction: column;
                        gap: 8px;
                        z-index: 100;
                    }
                    #controls {
                        display: flex;
                        gap: 8px;
                    }
                    .btn {
                        flex: 1;
                        padding: 12px 5px;
                        font-family: Arial, sans-serif;
                        font-size: 13px;
                        font-weight: bold;
                        border-radius: 8px;
                        border: 2px solid;
                        background: white;
                        cursor: pointer;
                        text-align: center;
                        transition: 0.2s;
                    }
                    .btn:hover { background: #f0f0f0; }
                    .btn-pause { border-color: #ff9800; color: #e65100; }
                    .btn-reset { border-color: #2196f3; color: #0d47a1; }
                    .btn-calibrate { border-color: #4CAF50; color: white; background: #4CAF50; }
                    .btn-calibrate:hover { background: #388E3C !important; }
                    .btn-close { border-color: #d32f2f; color: white; background: #f44336; }
                    .btn-close:hover { background: #c62828 !important; }

                    /* Leaderboard Top 3 */
                    #leaderboard-container {
                        position: absolute;
                        top: 270px; 
                        left: 20px;
                        width: 320px;
                        background: #f7f7f7;
                        border: 3px solid #e0e0e0;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        padding: 12px;
                        z-index: 100;
                    }
                    .rank-item { 
                        display: flex; 
                        justify-content: space-between; 
                        font-size: 15px; 
                        margin: 6px 0; 
                        font-weight: bold; 
                        padding: 6px;
                        border-radius: 6px;
                    }
                    .gold { color: #d4af37; background: rgba(255, 215, 0, 0.1); border-left: 4px solid #d4af37; }
                    .silver { color: #9e9e9e; background: rgba(192, 192, 192, 0.1); border-left: 4px solid #9e9e9e; }
                    .bronze { color: #cd7f32; background: rgba(205, 127, 50, 0.1); border-left: 4px solid #cd7f32; }
                    
                    /* Instrucciones de Juego */
                    #instructions-container {
                        position: absolute;
                        top: 270px; 
                        left: 410px;
                        width: 400px;
                        box-sizing: border-box;
                        background: #f7f7f7;
                        border: 3px solid #e0e0e0;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        padding: 12px 15px;
                        z-index: 100;
                        font-family: Arial, sans-serif;
                    }
                    #instructions-container h3 {
                        margin: 0 0 10px 0; 
                        text-align: center; 
                        border-bottom: 2px solid #ddd; 
                        padding-bottom: 5px;
                        color: #2196f3;
                    }
                    #instructions-container ol {
                        margin: 0;
                        padding-left: 20px;
                        font-size: 13.5px;
                        line-height: 1.6;
                    }
                    #instructions-container li { margin-bottom: 5px; }
                    .instr-highlight { font-weight: bold; color: #ff9800; }
                    
                    .btn-reset-rank {
                        width: 100%; 
                        margin-top: 10px; 
                        background: transparent; 
                        border: 1px solid #d32f2f; 
                        color: #d32f2f; 
                        padding: 6px; 
                        border-radius: 4px; 
                        cursor: pointer; 
                        font-size: 11px; 
                        font-weight: bold;
                        transition: 0.2s;
                    }
                    .btn-reset-rank:hover { background: #ffebee; }
                </style>
                <script>
                    let currentPlayerName = "";
                    let currentPlayerMaxScore = 0;
                    let isPlayerRegistered = false;

                    // Lógica del Ranking vía Servidor Python
                    function loadScores() {
                        fetch('/ranking')
                            .then(r => r.json())
                            .then(data => renderScores(data));
                    }

                    function saveScore(name, score) {
                        if (score === 0 || !name) return;
                        fetch(`/ranking?add_name=${encodeURIComponent(name)}&add_score=${score}`)
                            .then(r => r.json())
                            .then(data => renderScores(data));
                    }

                    function resetRanking() {
                        let pass = prompt("Para restablecer el ranking, ingresa la contraseña:");
                        if (pass === "admin") {
                            fetch('/ranking?reset=1')
                                .then(r => r.json())
                                .then(data => {
                                    renderScores(data);
                                    alert("Ranking restablecido exitosamente.");
                                });
                        } else if (pass !== null) {
                            alert("Contraseña incorrecta.");
                        }
                    }

                    function renderScores(scores) {
                        if (!scores) return;
                        let html = '';
                        let medals = ['🥇', '🥈', '🥉'];
                        let classes = ['gold', 'silver', 'bronze'];
                        
                        let isDark = document.body.style.backgroundColor === 'rgb(32, 33, 36)' || document.body.style.backgroundColor === '#202124';
                        let scoreColor = isDark ? '#fff' : '#333';

                        for(let i=0; i<3; i++) {
                            let name = scores[i] ? scores[i].name : "---";
                            let score = scores[i] ? scores[i].score : "0";
                            html += `<div class="rank-item ${classes[i]}">
                                <span>${medals[i]} ${i+1}. ${name}</span> 
                                <span style="color:${scoreColor}">${score}</span>
                            </div>`;
                        }
                        document.getElementById('top3-list').innerHTML = html;
                    }

                    function addPlayer() {
                        let nameInput = document.getElementById('player-name');
                        let name = nameInput.value.trim();
                        if (!name) {
                            alert("Por favor, ingresa un nombre.");
                            return;
                        }
                        
                        currentPlayerName = name;
                        currentPlayerMaxScore = 0;
                        isPlayerRegistered = true;
                        
                        nameInput.disabled = true;
                        document.getElementById('btn-add-player').disabled = true;
                        
                        let calBtn = document.getElementById('btn-calibrate');
                        calBtn.disabled = false;
                        calBtn.style.opacity = "1";
                        
                        alert("Nombre agregado exitosamente: " + name + "\\n\\n¡Ya puedes CALIBRAR y jugar!");
                    }

                    function doCalibrate() {
                        if (!isPlayerRegistered) return;
                        
                        fetch('/calibrate');
                        var trap = document.getElementById('focus-trap');
                        if (trap) trap.style.display = 'none';
                        document.querySelector('iframe').focus();
                    }

                    function togglePause() {
                        var btn = document.getElementById('btn-pause');
                        var btnReset = document.getElementById('btn-reset');
                        if (btn.innerText === "PAUSAR") {
                            btn.innerText = "REANUDAR";
                            btnReset.disabled = false;
                            btnReset.style.opacity = "1";
                            fetch('/pause?state=1');
                        } else {
                            btn.innerText = "PAUSAR";
                            btnReset.disabled = true;
                            btnReset.style.opacity = "0.5";
                            fetch('/pause?state=0');
                        }
                        document.querySelector('iframe').focus();
                    }

                    function doReset() {
                        // Al darle a Nuevo Jugador, guardamos el puntaje máximo del jugador actual en el podio
                        if (isPlayerRegistered && currentPlayerMaxScore > 0) {
                            saveScore(currentPlayerName, currentPlayerMaxScore);
                        }
                        
                        // Resetear UI para el siguiente jugador
                        currentPlayerName = "";
                        currentPlayerMaxScore = 0;
                        isPlayerRegistered = false;
                        
                        let nameInput = document.getElementById('player-name');
                        nameInput.value = "";
                        nameInput.disabled = false;
                        document.getElementById('btn-add-player').disabled = false;
                        
                        let calBtn = document.getElementById('btn-calibrate');
                        calBtn.disabled = true;
                        calBtn.style.opacity = "0.5";

                        fetch('/reset');
                        var trap = document.getElementById('focus-trap');
                        if (trap) trap.style.display = 'block';
                        
                        var btn = document.getElementById('btn-pause');
                        btn.innerText = "PAUSAR";
                        
                        var btnReset = document.getElementById('btn-reset');
                        btnReset.disabled = true;
                        btnReset.style.opacity = "0.5";
                    }

                    function doClose() {
                        if (isPlayerRegistered && currentPlayerMaxScore > 0) {
                            saveScore(currentPlayerName, currentPlayerMaxScore);
                        }
                        fetch('/close');
                    }

                    window.addEventListener('keydown', function(e) {
                        if (e.key.toLowerCase() === 'c') {
                            if (!isPlayerRegistered) {
                                alert("Primero debes agregar tu nombre en el panel izquierdo antes de calibrar.");
                                return;
                            }
                            doCalibrate();
                        }
                        if (e.key.toLowerCase() === 'z') {
                            doClose();
                        }
                    });
                    
                    window.onload = function() {
                        window.focus();
                        loadScores(); // Inicializar scores desde el backend
                        
                        let isGameOver = false;

                        // Loop de conexión con el juego y extracción de puntaje
                        setInterval(function() {
                            let iframe = document.querySelector('iframe');
                            if (!iframe.contentWindow || !iframe.contentWindow.Runner) return;
                            
                            let runner = iframe.contentWindow.Runner.instance_;
                            if (!runner) return;

                            // Sincronización 100% precisa del modo noche directo del DOM del juego
                            let isDark = iframe.contentWindow.document.body.classList.contains('inverted');
                            let color = isDark ? '#202124' : '#f7f7f7';
                            let textColor = isDark ? '#ffffff' : '#000000';
                            
                            if (document.body.style.backgroundColor !== color) {
                                document.body.style.backgroundColor = color;
                                document.getElementById('game-container').style.backgroundColor = color;
                                document.getElementById('bottom-cover').style.backgroundColor = color;
                                document.getElementById('pip').style.backgroundColor = color;
                                document.getElementById('leaderboard-container').style.backgroundColor = color;
                                document.getElementById('instructions-container').style.backgroundColor = color;
                                document.getElementById('leaderboard-container').style.color = textColor;
                                document.getElementById('instructions-container').style.color = textColor;
                                
                                fetch('/set_dark_mode?state=' + (isDark ? '1' : '0'));
                                loadScores(); // Forzar re-render para actualizar el color de los puntos
                            }

                            // Extracción automática del puntaje al chocar
                            if (runner.crashed && !isGameOver) {
                                isGameOver = true;
                                let distance = runner.distanceRan;
                                let coef = runner.distanceMeter ? runner.distanceMeter.config.COEFFICIENT : 0.025;
                                let score = Math.round(distance * coef);
                                
                                // Actualizamos el puntaje máximo de la sesión de este jugador
                                if (isPlayerRegistered && score > currentPlayerMaxScore) {
                                    currentPlayerMaxScore = score;
                                }
                            } else if (!runner.crashed) {
                                isGameOver = false;
                            }
                        }, 500);
                    }
                </script>
            </head>
            <body>
                <div id="game-container">
                    <iframe src="/t-rex-runner/index.html" scrolling="no"></iframe>
                    <div id="bottom-cover"></div>
                    <div id="focus-trap" onclick="window.focus();"></div>
                </div>
                
                <div id="leaderboard-container">
                    <h3 style="margin: 0 0 10px 0; text-align: center; border-bottom: 2px solid #ddd; padding-bottom: 5px;">🏆 TOP 3 JUGADORES 🏆</h3>
                    <div style="display: flex; gap: 5px; margin-bottom: 15px;">
                        <input type="text" id="player-name" placeholder="Ingresa tu nombre..." style="flex:1; padding: 8px; border-radius: 6px; border: 2px solid #ccc; font-weight: bold; font-size: 14px;"/>
                        <button id="btn-add-player" onclick="addPlayer()" style="background: #2196f3; color: white; border: none; border-radius: 6px; padding: 0 10px; font-weight: bold; cursor: pointer;">Agregar</button>
                    </div>
                    <div id="top3-list">
                        <!-- Generado por JS -->
                    </div>
                    <button class="btn-reset-rank" onclick="resetRanking()">RESTABLECER RANKING</button>
                </div>
                
                <div id="instructions-container">
                    <h3>🎮 CÓMO JUGAR 🎮</h3>
                    <ol>
                        <li>Mirar derecho a la cámara y <span class="instr-highlight">cerrar la boca</span>.</li>
                        <li>Ingresa tu nombre en el ranking a la izquierda y dale a <b>Agregar</b>.</li>
                        <li>Presiona el botón verde <b>CALIBRAR</b> (o la letra <span class="instr-highlight">C</span>).</li>
                        <li>Para <b>SALTAR</b>: <span class="instr-highlight">Abre la boca</span>.</li>
                        <li>Para <b>AGACHARTE</b>: <span class="instr-highlight">Baja un poco la cabeza</span>.</li>
                        <li>¡Diviértete!</li>
                        <li>Al terminar, pulsa <b>PAUSAR</b> y luego <b>NUEVO JUGADOR</b> para guardar tu récord.</li>
                    </ol>
                </div>

                <img id="pip" src="/cam.mjpg" onclick="doCalibrate()" title="Clica aquí o presiona C para calibrar" />
                <div id="controls-container">
                    <button id="btn-calibrate" class="btn btn-calibrate" onclick="doCalibrate()" style="opacity: 0.5;" disabled>CALIBRAR (Letra 'C')</button>
                    <div id="controls">
                        <button id="btn-pause" class="btn btn-pause" onclick="togglePause()">PAUSAR</button>
                        <button id="btn-reset" class="btn btn-reset" onclick="doReset()" style="opacity: 0.5;" disabled>NUEVO JUGADOR</button>
                    </div>
                    <button class="btn-close btn" onclick="doClose()">FINALIZAR JUEGO</button>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
            
    def log_message(self, format, *args):
        pass

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

def start_server():
    server = ThreadedHTTPServer(('localhost', 8080), CamHandler)
    server.serve_forever()

# --- Bucle Principal de Video y Detección Facial (OpenCV) ---
def video_loop():
    global current_frame, calibrated, mar_threshold, nose_y_baseline
    global space_pressed, down_pressed, current_mar, current_nose_y, game_started, paused
    
    cap = cv2.VideoCapture(0)
    
    while True:
        success, frame = cap.read()
        if not success:
            continue
            
        frame = cv2.flip(frame, 1)
        h_cam, w_cam, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = detector.detect(mp_image)
        
        display_frame = frame.copy()
        
        if results.face_landmarks:
            face = results.face_landmarks[0]
            landmarks = [(int(lm.x * w_cam), int(lm.y * h_cam)) for lm in face]
            
            p_top, p_bottom, p_left, p_right = landmarks[13], landmarks[14], landmarks[78], landmarks[308]
            v_dist = get_distance(p_top, p_bottom)
            h_dist = get_distance(p_left, p_right)
            current_mar = v_dist / h_dist if h_dist > 0 else 0
            
            current_nose_y = landmarks[1][1]
            f_top, f_bottom, f_left, f_right = landmarks[10], landmarks[152], landmarks[234], landmarks[454]
            face_height = get_distance(f_top, f_bottom)
            
            if not calibrated:
                cv2.rectangle(display_frame, (f_left[0], f_top[1]), (f_right[0], f_bottom[1]), (200, 255, 200), 2)
                cv2.circle(display_frame, landmarks[1], 6, (255, 0, 0), -1) # Nariz azul
                
                cv2.rectangle(display_frame, (0, h_cam - 90), (w_cam, h_cam), bg_color_bgr, -1)
                
                cv2.putText(display_frame, "CALIBRACION: Boca CERRADA", (15, h_cam - 60), cv2.FONT_HERSHEY_DUPLEX, 0.7, text_color, 2)
                cv2.putText(display_frame, "Presiona 'C' para iniciar", (15, h_cam - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                cv2.rectangle(display_frame, (f_left[0], f_top[1]), (f_right[0], f_bottom[1]), (0, 255, 0), 2)
                cv2.circle(display_frame, landmarks[1], 6, (255, 0, 0), -1) # Nariz azul
                cv2.circle(display_frame, p_top, 5, (0, 0, 255), -1) # Boca rojo
                cv2.circle(display_frame, p_bottom, 5, (0, 0, 255), -1)
                
                is_mouth_open = current_mar > mar_threshold
                is_face_close = (current_nose_y - nose_y_baseline) > (face_height * 0.12)
                
                if paused:
                    cv2.putText(display_frame, "PAUSADO", (w_cam//2 - 90, h_cam//2), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 165, 255), 3)
                    if space_pressed:
                        pyautogui.keyUp('space')
                        space_pressed = False
                    if down_pressed:
                        pyautogui.keyUp('down')
                        down_pressed = False
                else:
                    if is_mouth_open and not space_pressed:
                        if not game_started:
                            game_started = True
                            pyautogui.click(x=600, y=300) 
                        pyautogui.keyDown('space')
                        space_pressed = True
                    elif not is_mouth_open and space_pressed:
                        pyautogui.keyUp('space')
                        space_pressed = False
                        
                    if is_face_close and not down_pressed:
                        pyautogui.keyDown('down')
                        down_pressed = True
                    elif not is_face_close and down_pressed:
                        pyautogui.keyUp('down')
                        down_pressed = False
                    
                color_m = (0, 255, 0) if is_mouth_open else (0, 0, 255)
                color_p = (0, 255, 0) if is_face_close else (0, 0, 255)
                
                overlay = display_frame.copy()
                cv2.rectangle(overlay, (0, h_cam - 80), (w_cam, h_cam), bg_color_bgr, -1)
                cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame)
                
                cv2.putText(display_frame, f"Boca: {'ABIERTA' if is_mouth_open else 'Cerrada'}", (10, h_cam - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_m, 2)
                cv2.putText(display_frame, f"Cabeza: {'ABAJO' if is_face_close else 'Normal'}", (10, h_cam - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_p, 2)
        else:
            cv2.rectangle(display_frame, (0, 0), (w_cam, h_cam), bg_color_bgr, -1)
            cv2.putText(display_frame, "Rostro NO detectado", (w_cam//2 - 120, h_cam//2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
        current_frame = display_frame

if __name__ == '__main__':
    threading.Thread(target=video_loop, daemon=True).start()
    threading.Thread(target=start_server, daemon=True).start()
    
    time.sleep(1)
    window = webview.create_window('Dino de Chrome - Integrado Definitivo', 'http://localhost:8080', width=1200, height=650, resizable=False)
    webview.start()

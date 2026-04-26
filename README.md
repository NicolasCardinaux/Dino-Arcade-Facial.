# Dino Arcade Facial 🦖🎮

Una versión interactiva, educativa y altamente inmersiva del clásico juego del Dinosaurio de Chrome (T-Rex Runner), controlada totalmente a través de gestos faciales utilizando Inteligencia Artificial.

![Dino Arcade Facial Demo](./readme_assets/demo.png) *(Puedes agregar una captura de pantalla del juego aquí)*

Este proyecto fue refactorizado y optimizado para ser utilizado en presentaciones en vivo o aulas, integrando un clon local del juego original, un sistema de ranking persistente y una interfaz inmersiva (con soporte de Modo Noche automático) para garantizar una experiencia de usuario perfecta.

## 🌟 Características Principales

- **Control por Gestos Faciales (IA):** Olvídate del teclado. La aplicación utiliza **MediaPipe Tasks API** para detectar tu rostro en tiempo real de manera muy eficiente.
  - **Saltar:** Abre la boca.
  - **Agacharse:** Inclina la cabeza ligeramente hacia abajo.
- **Renderizado Local Sin Lag:** Integra una copia íntegra de `t-rex-runner` dentro de una interfaz Webview nativa, sirviendo los archivos a través de un servidor HTTP local para evadir bloqueos de internet y problemas de latencia CORS.
- **Top 3 de Jugadores (Leaderboard):** Incluye un ranking persistente guardado en un archivo físico (`ranking.json`), garantizando que los récords de los alumnos no se pierdan al cerrar el juego.
- **Modo Noche Inteligente:** Cuando el dinosaurio llega a puntajes altos y el juego invierte sus colores, toda la interfaz (botones, paneles, ranking) se adapta mágicamente al modo noche en tiempo real.
- **Cámara PiP (Picture-in-Picture):** El usuario puede ver qué está leyendo la IA en todo momento en una pequeña pantalla superior derecha con un overlay visualizador de gestos.
- **Flujo Anti-Trampas / Control de Aulas:** Botones enlazados lógicamente (es obligatorio registrar el nombre y pausar el juego para resetear la partida), así como una contraseña (`admin`) para evitar reseteos accidentales del podio por parte de los alumnos.

---

## 🛠️ Requisitos de Instalación

1. **Python 3.10 o superior** instalado en el sistema.
2. Clona o descarga este repositorio en tu computadora.
3. Abre una terminal en la carpeta del proyecto e instala las dependencias utilizando:

```bash
pip install -r requirements.txt
```

> **Dependencias principales:** `opencv-python`, `mediapipe`, `pywebview`, `pyautogui`.
> **Nota:** Ya no es necesario compilar librerías pesadas en C++ (como dlib). El modelo de MediaPipe garantiza máxima compatibilidad en Windows, Mac y Linux.

4. Asegúrate de tener una cámara web conectada.

---

## 🚀 Cómo Ejecutar el Juego

Una vez instaladas las dependencias, simplemente ejecuta el archivo maestro desde tu terminal:

```bash
python dino_definitivo.py
```

Se abrirá una ventana de 1200x650. **No intentes redimensionarla**, está pixel-perfect calculada para darte una experiencia Arcade inmersiva.

---

## 🎮 Instrucciones de Juego (Para Alumnos)

1. **Siéntate y mira derecho a la cámara**, manteniendo la **boca cerrada**.
2. **Escribe tu nombre** en la caja debajo de *Top 3 Jugadores* y presiona el botón azul **Agregar**.
3. Presiona el botón verde **CALIBRAR** (o la tecla `C`) para que la IA tome tu pose base de descanso.
4. Para **SALTAR**: ¡Abre la boca! 😲
5. Para **AGACHARTE**: Inclina levemente la cabeza hacia abajo. 🙇
6. Si chocas y pierdes, dale al botón naranja **PAUSAR**, y luego al botón azul **NUEVO JUGADOR**. Esto guardará automáticamente tu mejor puntaje en el ranking general.
7. ¡El siguiente compañero puede tomar su turno!

---

## ⚙️ Funciones de Administrador

### Restablecer Ranking
Al finalizar tu clase o demostración, si deseas limpiar los puntajes para el día siguiente:
1. Presiona el botón rojo **RESTABLECER RANKING** (debajo de los 3 nombres).
2. El sistema te pedirá una clave de seguridad.
3. Escribe `admin` y dale a aceptar. Todo el historial se borrará.

### Forzar Cierre Rápido
Si necesitas apagar rápidamente todo el sistema sin usar el ratón, presiona la tecla `Z`.

---

## 🧠 Estructura Interna (Para Desarrolladores)

El sistema opera bajo **tres hilos paralelos (Multithreading)** para que la interfaz gráfica nunca se trabe mientras se procesa la visión por computadora:

1. **Bucle OpenCV (Video Loop):** Lee la cámara (a 30+ FPS), ejecuta MediaPipe Face Landmarker y extrae el MAR (Mouth Aspect Ratio) usando trigonometría básica entre los nodos de los labios superior e inferior (13 y 14).
2. **Servidor HTTP (Backend):** 
   - Procesa los comandos JS de la interfaz (pausar, calibrar, modo oscuro).
   - Sirve el juego original desde la carpeta local `/t-rex-runner/`.
   - Lee y escribe el archivo `ranking.json` para persistencia del sistema.
   - Envía el feed de la cámara a través del formato MJPEG (`/cam.mjpg`) hacia la interfaz.
3. **Webview (Frontend):** Utiliza Edge/Chromium subyacente a través de `pywebview` para renderizar el DOM y conectar todas las interacciones del usuario en una app de escritorio nativa e independiente.

---

Desarrollado para fines educativos. ¡Que disfruten jugando con la cara! 🦖

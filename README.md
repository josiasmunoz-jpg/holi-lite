# Holi Lite

Mascota de escritorio para Windows: un agujero negro chiquito con ojos redondos que se mueve,
te mira, se posa sobre las ventanas, se duerme y tiene emociones propias. Una vez al día le da
hambre y sueño; si lo cuidas gana confianza, que se ve como planetas que nacen chicos y crecen.

## Descargar
Baja el último `HoliLite-Setup-x.y.z.exe` desde [Releases](https://github.com/josiasmunoz-jpg/holi-lite/releases/latest)
y ábrelo. Holi avisa solo cuando hay una versión nueva (Opciones > Actualizar).

## Cómo usarlo
- Arrástralo (clic izquierdo o derecho) y lánzalo. Si lo zamarreas, se marea.
- Pasa el mouse encima despacito para hacerle cariño. Doble clic: se pone cariñoso.
- Clic derecho sobre Holi, o sobre su ícono en la bandeja: menú circular (Comer, Dormir,
  Planetas, Ocultar, Pausar y Opciones).
- Clic en el ícono de la bandeja: Holi aparece en el centro de la pantalla.

## Instalar
Doble clic en `instalar.bat`: arma la aplicación, crea el instalador `entregar\HoliLite-Setup-<versión>.exe`
y lo instala en este PC. Tus planetas y ajustes se mantienen.

Para dársela a otra persona basta con el instalador: un solo archivo, sin Python ni permisos de administrador.
Como no está firmado, Windows puede mostrar "Windows protegió su PC": se pasa con "Más información" y
"Ejecutar de todas formas". Para desinstalar: Configuración > Aplicaciones > Holi Lite.

## Si algo falla
Holi no se cierra por un error: lo anota en `%APPDATA%\HoliLite\errores.txt` y sigue. Si se cierra de golpe,
Windows lo vuelve a abrir. En Opciones > Reportar se copia el detalle para pegarlo en el chat.

## Desarrollo
`run.bat` lo abre desde el código (crea `.venv` la primera vez).
`tools\make_icon.py` regenera `assets\blob.ico` con el dibujo actual de Holi.
La versión está en `holi\__init__.py`: al subir un cambio de versión a `main`, GitHub arma el instalador
y lo publica solo (`.github/workflows/publicar.yml`).

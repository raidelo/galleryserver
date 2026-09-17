# Galería local

Sirve una carpeta del disco como galería web: imágenes, GIFs y vídeos, con las
subcarpetas mostradas como hojas de contacto para orientarte.

## Uso

```bash
cd /la/carpeta/que/quieras
python ruta/a/gallery.py
```

Abre el navegador solo en `http://localhost:8800/`.

Opciones:

| Opción | Qué hace |
| --- | --- |
| `gallery.py ~/Fotos` | sirve esa carpeta en lugar de la actual |
| `-p 9000` | cambia el puerto (si está ocupado busca el siguiente libre) |
| `--host 0.0.0.0` | accesible desde otros equipos de tu red |
| `--all` | incluye archivos y carpetas ocultos |
| `--no-browser` | no abre el navegador al arrancar |

## Dependencias

Ninguna obligatoria: funciona con la biblioteca estándar de Python 3.8+.

- **Pillow** (`pip install pillow`) genera miniaturas. Sin él las imágenes se
  cargan completas en la rejilla, que va más lento con carpetas grandes.
- **ffmpeg** en el PATH saca el fotograma de portada de los vídeos. Sin él cada
  vídeo aparece como una ficha con su nombre y tamaño, y se reproduce igual.

## Estructura

```
gallery.py        servidor: listado, miniaturas, envío de archivos con Range
static/index.html estructura de la página
static/style.css  estilos
static/app.js     navegación, rejilla y visor
```

El backend solo devuelve JSON y archivos; el HTML es estático y se pinta en el
navegador. No hay motor de plantillas.

## Atajos

| Tecla | Acción |
| --- | --- |
| `/` | ir al filtro |
| `Retroceso` | subir a la carpeta madre |
| `←` `→` `Espacio` | moverse entre archivos en el visor |
| `Inicio` `Fin` | primer y último archivo |
| `Esc` | cerrar el visor o limpiar el filtro |

Click sobre una foto abierta alterna entre ajustada a pantalla y tamaño real.
Al pasar el ratón, los GIFs se animan y los vídeos muestran una vista previa sin
sonido.

## Notas

- Solo se sirven archivos de imagen, GIF o vídeo dentro de la carpeta indicada;
  cualquier ruta que salga de ahí devuelve 403.
- Los vídeos se envían con soporte de `Range`, así que puedes saltar por la barra
  de reproducción sin descargar el archivo entero.
- Formatos como `.mkv` o `.avi` se sirven, pero que se reproduzcan depende de tu
  navegador (`.mp4` y `.webm` van siempre).
- El escaneo de cada subcarpeta tiene un tope de entradas para que abrir un
  directorio enorme siga siendo instantáneo; por eso a veces verás "más de N
  archivos".

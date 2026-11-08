# Guía Didáctica: sc-found-t

## Objetivo
Aprender a usar `sc-found-t` para encontrar correos de contacto público de creadores de YouTube y Twitch con el objetivo de proponer colaboraciones profesionales.

## ¿Qué hace el script?
El script explora páginas públicas de canales de YouTube y Twitch para extraer direcciones de correo electrónico que los creadores han publicado para contacto de negocio. No usa APIs privadas, no adivina direcciones ni compra listas.

## Casos de uso típicos

### 1. Buscar contactos de un canal específico
```bash
# Canal suelto
.venv/bin/python run.py @nombre_del_canal

# Con varias opciones separadas por espacios
.venv/bin/python run.py "@canal1 @canal2 twitch.tv/streamer"
```

### 2. Buscar por palabra clave
```bash
# Buscar canales relacionados con un tema
.venv/bin/python run.py --search "cocina española"

# Con filtros de audiencia
.venv/bin/python run.py --search "minecraft" --min-subs 10000

# Solo YouTube, ordenando por vistas
.venv/bin/python run.py --search "tutoriales" --search-platform youtube --search-sort vistas
```

### 3. Filtrar solo correos de negocio
```bash
.venv/bin/python run.py @canal --only-business
```
Esto deja solo emails con roles como: `contacto`, `colaboraciones`, `prensa`, `gestión`.

## Componentes principales

### Entrada de datos
- **Canales sueltos**: `@handle`, `URL completa`, o `twitch.tv/usuario`
- **Fichero**: Un texto con un canal por línea (archivo `input/example.txt` incluye ejemplos)
- **Búsqueda por palabra clave**: Usa `--search "tu tema"`

### Opciones más útiles para principiantes

| Opción | Cuándo usarla |
|---|---|
| `--no-crawl` | Solo quieres emails de la bio, sin visitar webs |
| `--min-subs 5000` | Solo canales con al menos 5000 suscriptores |
| `--only-business` | Solo quieres correos profesionales |
| `--delay 2.0` | Si ves muchos timeouts, aumenta el retraso |

### Flujo de trabajo recomendado

1. **Primero busca por palabra clave** para descubrir canales:
   ```bash
   .venv/bin/python run.py --search "cocina mexicana" --min-subs 1000
   ```

2. **Revisa la lista generada** (`busqueda_canales.csv` en la carpeta `out/`)

3. **Ejecuta el análisis completo** de los canales seleccionados:
   ```bash
   .venv/bin/python run.py input/mis_canales.txt --only-business
   ```

4. **Revisa los resultados** en `contactos_20261105_1234.csv`

## Cómo funciona el filtrado

El script puntua cada correo encontrado:

- `mailto:` declarado en la web: +25 puntos
- Sección `colaboraciones`/`partnerships`: +70 puntos
- Texto `contacto`/`hola`: +60 puntos
- Sección `prensa`: +55 puntos
- Sección `gestión`: +50 puntos
- Correo genérico: +20 puntos

Luego deduplica, quedando solo un email por dirección (el de mayor puntuación).

También filtra automáticamente:
- Correos `noreply@`, `no-reply@`, `donotreply@`
- Dominios `example.com`, `tuemail@`, `nombre@ejemplo.com`
- Correos de dominios que no son los del creador (a menos que sean Gmail, Outlook, etc.)

## Consejos prácticos

### Para YouTube
- No necesita configuración especial básica
- Si YouTube pide verificación de bot, usa `--cookies-from-browser firefox`
- El orden de búsqueda es: descripción → pestaña About → sitio web externo

### Para Twitch
- **Necesitas credenciales** de developer.twitch.tv
- Configura `TWITCH_CLIENT_ID` y `TWITCH_CLIENT_SECRET` como variables de entorno
- La búsqueda de Twitch solo encuentra el nombre, no el tema del canal
- Es mejor buscar el canal en YouTube primero, luego usar Twitch solo para confirmar

### Evitando problemas
- **No quites el `--contact-email`** del User-Agent a menos que vayas a identificarte realmente
- Usa `--delay` mayor si ves muchos errores de "demasiadas peticiones"
- `--max-domains-total 60` es el límite global de webs que se visitarán
- El caché (`--cache-ttl 168`) guarda resultados por 7 días para no repetir trabajo

## Legal y ética

- Solo se visited páginas públicas
- Respetar `robots.txt` (a menos que lo desactives)
- Los correos son de negocio publicados para ser contactados
- Siempre incluye baja en tu primer correo
- No hagas envíos masivos sin consentimiento

## ¿Qué aprenderás con esto?

- Cómo trabajar con herramientas de línea de comandos en Python
- Manejo de APIs de YouTube y Twitch (oficiales y no-oficiales)
- Extracción y clasificación de datos de páginas web
- buenas prácticas de scraping responsable
- Estructura de datos y procesamiento de resultados
# sc-found-t

Busca **correos de contacto públicos** de canales de YouTube y Twitch para proponer
colaboraciones. Solo lee lo que el creador ya publica: la bio del canal, el enlace
de "Contacto" que YouTube muestra en la pestaña *About*, y las páginas públicas de
contacto de los sitios web que el creador enlaza.

Sin APIs de pago, sin adivinar casillas, sin listas compradas.

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Uso

```bash
# Un canal suelto
.venv/bin/python run.py @mkbhd

# Varios separados por comas o espacios
.venv/bin/python run.py "@mkbhd @DotCSV twitch.tv/ibai"

# Un fichero con un canal por línea
.venv/bin/python run.py input/example.txt -o out

# Solo la bio, sin visitar webs externas
.venv/bin/python run.py @mkbhd --no-crawl

# Solo casillas de contacto/negocios, no cuentas personales
.venv/bin/python run.py input/ejemplo.txt --only-business
```

```bash
# Buscar por palabra clave y sacar emails de lo que aparezca
.venv/bin/python run.py --search "cocina española"

# Solo una plataforma, ordenando por audiencia y quedándote con los grandes
.venv/bin/python run.py --search "minecraft español" \
    --search-platform youtube --search-sort vistas --min-subs 50000

# Buscando canales, no videos (deduplica por canal)
.venv/bin/python run.py --search "recetas" --search-type canal
```

También se puede combinar con targets sueltos: lo que salga de `--search` se
analiza junto a los canales que indiques.

Salida en `out/`: `contactos_<fecha>.csv`, `.json` y un `.md` con el informe.
Cuando usas `--search` además sale un `busqueda_canales.csv` con los canales
encontrados, para poder revisar la lista antes de escribir.

## Búsqueda por palabra clave

**YouTube** no necesita nada: `yt-dlp` consulta la página pública de resultados
y devuelve el canal de cada video, que se deduplica antes de gastar nada más.
`--search-sort` cambia el orden (relevancia, vistas, fecha) y `--search-type
canal` filtra por tipo de canal en vez de video.

**Twitch** sí necesita credenciales, porque no hay búsqueda pública sin token.
Regístrala en <https://dev.twitch.tv/console/apps> y exporta:

```bash
export TWITCH_CLIENT_ID=...
export TWITCH_CLIENT_SECRET=...
```

Es una app de servidor a servidor, no la cuenta de ningún creador. El token
sale por `client_credentials` y no da acceso a datos privados. Sin esas
variables, `--search` sigue funcionando en YouTube y avisa de que Twitch se
queda fuera.

## Opciones

| Flag | Qué hace |
|---|---|
| `-s, --search` | Palabra clave: descubre canales antes de buscar emails |
| `--search-platform` | `youtube`, `twitch` o `todos` |
| `--search-sort` | `relevancia`, `vistas` o `fecha` |
| `--search-type` | `video` (dedup por canal) o `canal` |
| `--search-limit` | Máximo de canales por plataforma (40) |
| `--live-only` | En Twitch, solo los que estén en directo |
| `--min-subs N` | No rastrea canales por debajo de N suscriptores |
| `-o, --outdir` | Carpeta de salida (por defecto `out/`) |
| `-c, --concurrency` | Canales en paralelo (4) |
| `--delay` | Segundos entre peticiones al mismo dominio (1.5) |
| `--max-pages` | Páginas por dominio (6) |
| `--max-domains` | Dominios por creador (5) |
| `--max-domains-total` | Tope global de dominios en toda la ejecución (60) |
| `--no-crawl` | Solo busca en la bio, no visita webs |
| `--only-business` | Deja solo `contacto`, `colaboraciones`, `prensa`, `gestión` |
| `--min-score N` | Filtra por puntuación mínima |
| `--any-domain` | Acepta correos de terceros hallados en plataformas (más ruido) |
| `--ignore-robots` | Ignora `robots.txt` en sitios externos |
| `--cache-ttl` | Horas de caché en `.cache/` (168) |
| `--contact-email` | Tu email; va en el User-Agent para que te puedan identificar |
| `--cookies-from-browser` | `firefox`, `chrome`, `brave`… si YouTube te pide verificación |

## Dónde busca, y en qué orden

1. **Descripción del canal** (YouTube y Twitch). Si el canal lo has buscado por
   palabra clave, esto es lo primero que se mira de cada resultado.
2. **Pestaña `/about` de YouTube**, que es donde está el enlace de contacto real
   del creador (lo que YouTube llama *business inquiries*) y el resto de su
   sección de enlaces.
3. **Sitios externos** que el creador enlaza: primero los que suelen tener
   contacto declarado (Patreon, Ko-fi, Linktree, About.me, Buy Me a Coffee…) y
   luego su web propia, probando `/contacto`, `/press`, `/colaboraciones`,
   `/partnerships`, `/sponsors`, `/booking`, `/management`…
4. Correos escritos a mano para evitar bots: `nombre (at) gmail (dot) com`.

## Cómo filtra

- Descarta `noreply@`, `example.com`, `tuemail@`, `nombre@ejemplo.com`.
- Descarta los correos cuyo dominio no es el de la web visitada, salvo que sean
  de un proveedor consumer (gmail, hotmail…) o un `mailto:` declarado. Así
  desaparece el ruido de los portales de soporte de Patreon o Zendesk.
- Puntuúa cada contacto: `mailto:` declarado +25, `colaboraciones/`partnerships`
  70, `contacto`/`hola` 60, `prensa` 55, `gestión` 50, genérico 20.
- Deduplica por email conservando el de mayor puntuación.

## Etiqueta

El script va con `--contact-email` en el User-Agent
(`sc-found-t/1.0 (+collaboration-outreach bot; contact: TU-EMAIL-ACA)`).
Es lo honesto: el administrador del sitio puede ver quién eres y pedirte que
pares. No lo quites si no vas a identificarte.

## Límites que conviene conocer

- **Twitch no da los enlaces del canal.** Su `/about` se pinta en JavaScript y
  el endpoint público solo devuelve la bio. Si el streamer no pone un correo en
  la bio, no habrá resultado; conviene pasarle su canal de YouTube o su web.
- **La búsqueda de Twitch solo ve el nombre, no la temática.** Su API oficial
  compara con el login o el nombre del canal, así que busca bien a quien se
  llama por su canal (`cocinacarmen`), no a quien hace recetas con otro nombre.
  Para eso, busca en YouTube y cruza con la web del creador.
- **`--min-subs` no filtra la lista de salida**, solo decide a quién se rastrea:
  los suscriptores solo se saben al resolver cada canal. En Twitch no hay dato
  de seguidores, así que el filtro no descarta nada allí.
- **YouTube** puede pedir verificación de edad o de bots. Si pasa, usa
  `--cookies-from-browser firefox`.
- **No valida que el buzón exista.** Todos vienen de páginas públicas, pero
  revisa el dominio antes de escribir: `hola@midominio.com` en una web que no es
  del creador suele ser la casilla de soporte de un proveedor de pagos.
- Los correos personales (`nombre.apellido@gmail.com`) se marcan como
  `sin_clasificar`. Usa `--only-business` para quedarte con las casillas
  profesionales.

## Legal y ethics

- Solo se visited páginas públicas, respetando `robots.txt` (salvo que lo
  desactives explícitamente) y con un retardo por dominio.
- Datos de contacto **de negocio publicados para ser contactados**. Nada de
  registros filtrados, bases de datos compradas ni casillas adivinadas.
- Incluye siempre un enlace de baja en tu primer correo y no hagas envíos
  masivos sin consentimiento.
# Fortaleza Estampados — fotos para redes

Cada 30 minutos GitHub Actions lee el Google Sheet "productos", arma la foto de cada fila nueva
(prenda por capas, igual que el sitio) y la guarda en `posts/<id>.jpg`.

URL publica de cada foto:
`https://raw.githubusercontent.com/USUARIO/REPO/main/posts/<id>.jpg`
(el `<id>` es el de la columna `id`; los espacios y simbolos raros se cambian por `-`).

## Puesta en marcha
1. Repo publico nuevo en GitHub (rama `main`) y subir todo el contenido de esta carpeta (incluida `.github/`).
2. Settings > Secrets and variables > Actions > pestaña **Variables** > New repository variable:
   - Nombre: `SHEET_CSV_URL`
   - Valor: la URL del CSV publicado de tu Sheet (la misma `SHEET_CSV_URL` de catalogo.html).
3. Settings > Actions > General > Workflow permissions: **Read and write permissions**.
4. Pestaña Actions > "Generar fotos para redes" > Run workflow (primera corrida).

## Reglas
- Solo se procesan filas que tengan `diseno`. Usa `familia`, `color`, `escala`, `dx`, `dy` como el sitio.
- Si cambias diseno, color, familia, escala, dx o dy de una fila, la foto se regenera sola.
- Color desconocido -> Blanco (aparece un AVISO en el log). Una fila con error no frena a las demas.
- Para cambiar el look (fondo, tamano) edita `render_posts.py` y sube `VERSION_RENDER` para regenerar todo.
- Si GitHub pausa el flujo programado por inactividad, reactivalo en la pestaña Actions.

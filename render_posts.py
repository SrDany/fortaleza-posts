#!/usr/bin/env python3
"""Fortaleza Estampados: genera las fotos para redes (montaje por capas) desde el Google Sheet.

Replica capas.js del sitio: tela de color + diseno PNG + sombras (multiply) + brillos (screen).
Por cada fila con columna `diseno` crea posts/<id>.jpg (1080x1080).
Solo re-renderiza lo nuevo o lo que cambio (manifest.json guarda una huella por fila).

Variables de entorno:
  SHEET_CSV_URL  (opcional) URL del CSV publicado del Sheet. Si falta, se usa el del sitio.
"""
import csv
import hashlib
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

RAIZ = os.path.dirname(os.path.abspath(__file__))
BASES = {
    "tee":  dict(w=1100, h=1200, x=31,   y=21, ancho=38, alto=48),
    "polo": dict(w=1100, h=1200, x=33,   y=30, ancho=34, alto=40),
    "saco": dict(w=1400, h=1050, x=38.5, y=33, ancho=25, alto=23),
}
FONDO = (245, 245, 242)
SALIDA = 1080
# CSV publicado del Sheet "productos" (el mismo que usa el sitio). Se puede sobreescribir con la variable SHEET_CSV_URL.
SHEET_CSV_POR_DEFECTO = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vSW8cZeRPj4JAFbjGqg2SmZzyiKmwRvQfSBZrGI6gwCpJbL1YaEAio6fXOhjgpntojFaXRwDK-9PY89/pub?gid=0&single=true&output=csv"
)
VERSION_RENDER = "1"  # subelo si cambias el aspecto del montaje para re-renderizar todo

with open(os.path.join(RAIZ, "colores.json"), encoding="utf-8") as f:
    COLORES = json.load(f)
COLORES_LC = {k.strip().lower(): v for k, v in COLORES.items()}


def base_de_fila(familia, nombre):
    """Igual que baseDeLinea() de capas.js."""
    familia = (familia or "").strip().lower()
    if familia == "buzo":
        return "saco"
    if familia == "polo" or re.search(r"polo", nombre or "", re.I):
        return "polo"
    return "tee"


def num(v, defecto):
    try:
        v = float(str(v).replace(",", ".").strip())
        return v
    except (ValueError, AttributeError):
        return defecto


def luminosidad(hexc):
    r, g, b = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def abrir_diseno(ruta):
    if re.match(r"^https?://", ruta, re.I):
        url = urllib.parse.quote(ruta, safe=":/%?&=#")
        req = urllib.request.Request(url, headers={"User-Agent": "fortaleza-posts/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGBA")
    return Image.open(ruta).convert("RGBA")


def render(base, diseno, hexc, escala=1.0, dx=0.0, dy=0.0):
    B = BASES[base]
    W, H = B["w"], B["h"]
    ruta = os.path.join(RAIZ, "assets", "bases")
    sombras = Image.open(os.path.join(ruta, f"{base}_sombras.webp")).convert("RGBA")
    brillos = Image.open(os.path.join(ruta, f"{base}_brillos.webp")).convert("RGBA")

    rgb = np.array([int(hexc[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32) / 255
    cur = np.ones((H, W, 3), dtype=np.float32) * rgb

    e = escala if escala and escala > 0 else 1.0
    ancho_pct, alto_pct = B["ancho"] * e, B["alto"] * e
    x_pct = B["x"] + B["ancho"] / 2 - ancho_pct / 2 + dx
    y_pct = B["y"] + dy
    bx, by = x_pct / 100 * W, y_pct / 100 * H
    bw, bh = ancho_pct / 100 * W, alto_pct / 100 * H
    k = min(bw / diseno.width, bh / diseno.height)  # object-fit: contain
    nw, nh = max(1, round(diseno.width * k)), max(1, round(diseno.height * k))
    d = diseno.resize((nw, nh), Image.LANCZOS)
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    capa.paste(d, (round(bx + (bw - nw) / 2), round(by)), d)  # object-position: center top
    c = np.array(capa, dtype=np.float32) / 255
    cur = cur * (1 - c[..., 3:4]) + c[..., :3] * c[..., 3:4]

    s = np.array(sombras, dtype=np.float32) / 255
    sa = s[..., 3:4]
    cur = cur * (1 - sa) + (cur * s[..., :3]) * sa  # multiply

    op = 0.16 * (1 - luminosidad(hexc)) ** 2
    bl = np.array(brillos, dtype=np.float32) / 255
    ba = bl[..., 3:4] * op
    cur = cur * (1 - ba) + (1 - (1 - cur) * (1 - bl[..., :3])) * ba  # screen

    fondo = np.array(FONDO, dtype=np.float32) / 255
    out = fondo * (1 - sa) + cur * sa  # la silueta recorta la prenda
    img = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB")
    lado = max(W, H)
    lienzo = Image.new("RGB", (lado, lado), FONDO)
    lienzo.paste(img, ((lado - W) // 2, (lado - H) // 2))
    return lienzo.resize((SALIDA, SALIDA), Image.LANCZOS)


def leer_filas(origen):
    if re.match(r"^https?://", origen, re.I):
        sep = "&" if "?" in origen else "?"
        with urllib.request.urlopen(origen + sep + "nocache=1", timeout=60) as r:
            texto = r.read().decode("utf-8-sig")
    else:
        with open(origen, encoding="utf-8-sig") as f:
            texto = f.read()
    return list(csv.DictReader(io.StringIO(texto)))


def nombre_archivo(id_):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", id_.strip()).strip("-")


def main():
    origen = os.environ.get("SHEET_CSV_URL") or (sys.argv[1] if len(sys.argv) > 1 else "") or SHEET_CSV_POR_DEFECTO
    carpeta = os.path.join(RAIZ, "posts")
    os.makedirs(carpeta, exist_ok=True)
    ruta_manifest = os.path.join(RAIZ, "manifest.json")
    manifest = json.load(open(ruta_manifest, encoding="utf-8")) if os.path.exists(ruta_manifest) else {}

    hechos, omitidos, errores = 0, 0, 0
    filas = leer_filas(origen)
    encabezados = [k for k in (filas[0].keys() if filas else []) if isinstance(k, str)]
    print(f"Encabezados recibidos: {encabezados}")
    con_id = sum(1 for f in filas if (f.get("id") or "").strip())
    con_diseno = sum(1 for f in filas if (f.get("id") or "").strip() and (f.get("diseno") or "").strip())
    print(f"Filas leidas: {len(filas)} | con id: {con_id} | con id y diseno: {con_diseno}")
    for fila in filas:
        # DictReader guarda las celdas sobrantes bajo la clave None (como lista): se ignoran
        fila = {k.strip().lower(): (v or "").strip() for k, v in fila.items() if isinstance(k, str)}
        id_, diseno_url = fila.get("id", ""), fila.get("diseno", "")
        if not id_ or not diseno_url:
            continue  # fila sin diseno por capas: no hay montaje que hacer
        archivo = nombre_archivo(id_) + ".jpg"
        color_nombre = fila.get("color", "") or "Blanco"
        hexc = COLORES_LC.get(color_nombre.lower())
        if not hexc:
            print(f"AVISO {id_}: color '{color_nombre}' no existe en la paleta; uso Blanco")
            hexc = COLORES_LC["blanco"]
        base = base_de_fila(fila.get("familia"), fila.get("nombre"))
        escala, dx, dy = num(fila.get("escala"), 1.0), num(fila.get("dx"), 0.0), num(fila.get("dy"), 0.0)
        huella = hashlib.sha1(json.dumps([VERSION_RENDER, diseno_url, hexc, base, escala, dx, dy]).encode()).hexdigest()
        if manifest.get(archivo) == huella and os.path.exists(os.path.join(carpeta, archivo)):
            omitidos += 1
            continue
        try:
            img = render(base, abrir_diseno(diseno_url), hexc, escala, dx, dy)
            img.save(os.path.join(carpeta, archivo), "JPEG", quality=90, optimize=True)
            manifest[archivo] = huella
            hechos += 1
            print(f"OK   {id_} -> posts/{archivo} ({base}, {color_nombre})")
        except Exception as ex:  # una fila mala no debe frenar las demas
            errores += 1
            print(f"ERROR {id_}: {ex}")

    with open(ruta_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Listo: {hechos} nuevas/actualizadas, {omitidos} sin cambios, {errores} con error")
    if not (hechos or omitidos):
        # Nada procesado: que la corrida falle en rojo en vez de quedar "verde" sin hacer nada
        print("ATENCION: no se proceso ninguna fila. Revisa que el CSV publicado tenga las columnas "
              "id y diseno (arriba salen los encabezados que se recibieron).")
        sys.exit(1)


if __name__ == "__main__":
    main()

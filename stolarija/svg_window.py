"""
SVG Window Visualizer — generira vizualni prikaz prozora/vrata za PDF ponude.

Podržava:
- Jednokrilni, dvokrilni, trokrilni, fiksni, klizni, kip-turn
- Dimenzije u mm, skalirano na SVG viewBox
- Boja profila (opciono)
- WeasyPrint renderira SVG nativno

Nula dependency — čisti Python string builder.
"""


def generate_window_svg(
    width_mm,
    height_mm,
    wing_config="double",
    element_type="window",
    profile_color="#4a5568",
    glass_color="#bfdbfe",
    frame_width=40,
):
    """
    Generira SVG string za prozor/vrata.

    Args:
        width_mm: širina u mm
        height_mm: visina u mm
        wing_config: fixed|single|double|triple|sliding|tilt_turn
        element_type: window|door|mosquito|facade
        profile_color: boja profila (hex)
        glass_color: boja stakla (hex)
        frame_width: debljina okvira u SVG jedinicama

    Returns:
        str: SVG markup
    """
    # Skaliraj na SVG (max 300px širine)
    scale = 300 / max(width_mm, height_mm)
    w = width_mm * scale
    h = height_mm * scale
    fw = frame_width  # frame width
    pad = 10

    svg_w = w + pad * 2
    svg_h = h + pad * 2 + 30  # +30 za dimenzije

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_w:.0f} {svg_h:.0f}" '
        f'width="{svg_w:.0f}" height="{svg_h:.0f}">'
    )

    # Pozadina
    parts.append(f'<rect width="{svg_w:.0f}" height="{svg_h:.0f}" fill="none"/>')

    ox, oy = pad, pad  # origin

    # Vanjski okvir (profil)
    parts.append(f'<rect x="{ox:.0f}" y="{oy:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{profile_color}" rx="3"/>')

    # Unutarnje staklo
    gx = ox + fw
    gy = oy + fw
    gw = w - fw * 2
    gh = h - fw * 2

    if gw <= 0 or gh <= 0:
        # Previše mali za detalje
        parts.append(
            f'<rect x="{ox + 5:.0f}" y="{oy + 5:.0f}" '
            f'width="{max(w - 10, 1):.0f}" height="{max(h - 10, 1):.0f}" '
            f'fill="{glass_color}" rx="2"/>'
        )
    elif wing_config == "fixed":
        # Fiksno — jedno staklo, križ
        parts.append(
            f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" fill="{glass_color}" rx="2"/>'
        )

    elif wing_config == "single":
        # Jednokrilno — jedno staklo + handle + dijagonala
        parts.append(
            f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" fill="{glass_color}" rx="2"/>'
        )
        # Dijagonala (otvaranje)
        cx = gx + gw / 2
        parts.append(
            f'<line x1="{gx:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>'
        )
        parts.append(
            f'<line x1="{gx + gw:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>'
        )
        # Handle
        hx = gx + gw - 8
        hy = gy + gh / 2
        parts.append(f'<rect x="{hx:.0f}" y="{hy - 12:.0f}" width="4" height="24" fill="{profile_color}" rx="2"/>')

    elif wing_config == "double":
        # Dvokrilno — dva stakla + srednji profil
        half = gw / 2
        mid = fw / 2
        # Lijevo krilo
        parts.append(
            f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{half - mid:.0f}" height="{gh:.0f}" fill="{glass_color}" rx="2"/>'
        )
        # Srednji profil
        parts.append(
            f'<rect x="{gx + half - mid:.0f}" y="{gy:.0f}" '
            f'width="{mid * 2:.0f}" height="{gh:.0f}" fill="{profile_color}"/>'
        )
        # Desno krilo
        parts.append(
            f'<rect x="{gx + half + mid:.0f}" y="{gy:.0f}" '
            f'width="{half - mid:.0f}" height="{gh:.0f}" '
            f'fill="{glass_color}" rx="2"/>'
        )
        # Dijagonale
        lx = gx + (half - mid) / 2
        rx = gx + half + mid + (half - mid) / 2
        parts.append(
            f'<line x1="{gx:.0f}" y1="{gy + gh:.0f}" x2="{lx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>'
        )
        parts.append(
            f'<line x1="{gx + half - mid:.0f}" y1="{gy + gh:.0f}" x2="{lx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>'
        )
        parts.append(
            f'<line x1="{gx + half + mid:.0f}" y1="{gy + gh:.0f}" x2="{rx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>'
        )
        parts.append(
            f'<line x1="{gx + gw:.0f}" y1="{gy + gh:.0f}" x2="{rx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>'
        )
        # Handles
        parts.append(
            f'<rect x="{gx + half - mid - 6:.0f}" y="{gy + gh / 2 - 12:.0f}" '
            f'width="4" height="24" fill="{profile_color}" rx="2"/>'
        )
        parts.append(
            f'<rect x="{gx + half + mid + 2:.0f}" y="{gy + gh / 2 - 12:.0f}" '
            f'width="4" height="24" fill="{profile_color}" rx="2"/>'
        )

    elif wing_config == "triple":
        # Trokrilno — tri stakla
        third = gw / 3
        mid = fw / 2
        for i in range(3):
            sx = gx + i * third + (mid if i > 0 else 0)
            sw = third - mid
            parts.append(
                f'<rect x="{sx:.0f}" y="{gy:.0f}" width="{sw:.0f}" height="{gh:.0f}" fill="{glass_color}" rx="2"/>'
            )
        # Profili između
        parts.append(
            f'<rect x="{gx + third - mid:.0f}" y="{gy:.0f}" '
            f'width="{mid * 2:.0f}" height="{gh:.0f}" fill="{profile_color}"/>'
        )
        parts.append(
            f'<rect x="{gx + 2 * third - mid:.0f}" y="{gy:.0f}" '
            f'width="{mid * 2:.0f}" height="{gh:.0f}" fill="{profile_color}"/>'
        )

    elif wing_config == "sliding":
        # Klizno — dva stakla s strelicama
        half = gw / 2
        parts.append(
            f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{half:.0f}" height="{gh:.0f}" fill="{glass_color}" rx="2"/>'
        )
        parts.append(
            f'<rect x="{gx + half:.0f}" y="{gy:.0f}" width="{half:.0f}" height="{gh:.0f}" '
            f'fill="{glass_color}" rx="2" opacity="0.7"/>'
        )
        # Strelice (klizanje)
        ay = gy + gh / 2
        parts.append(
            f'<text x="{gx + half / 2:.0f}" y="{ay:.0f}" '
            f'text-anchor="middle" font-size="16" fill="{profile_color}" opacity="0.5">⇆</text>'
        )

    elif wing_config == "tilt_turn":
        # Kip-turn — jedno staklo + dijagonala + horizontalna
        parts.append(
            f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" fill="{glass_color}" rx="2"/>'
        )
        cx = gx + gw / 2
        # Nagib (horizontalna linija gore)
        parts.append(
            f'<line x1="{gx:.0f}" y1="{gy:.0f}" x2="{cx:.0f}" y2="{gy + gh / 3:.0f}" '
            f'stroke="{profile_color}" stroke-width="1" opacity="0.4" stroke-dasharray="4"/>'
        )
        parts.append(
            f'<line x1="{gx + gw:.0f}" y1="{gy:.0f}" x2="{cx:.0f}" y2="{gy + gh / 3:.0f}" '
            f'stroke="{profile_color}" stroke-width="1" opacity="0.4" stroke-dasharray="4"/>'
        )
        # Zaokret (dijagonala dolje)
        parts.append(
            f'<line x1="{gx:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>'
        )
        parts.append(
            f'<line x1="{gx + gw:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
            f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>'
        )
        # Handle
        parts.append(
            f'<rect x="{gx + gw - 8:.0f}" y="{gy + gh / 2 - 12:.0f}" '
            f'width="4" height="24" fill="{profile_color}" rx="2"/>'
        )
    else:
        # Fallback
        parts.append(
            f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" fill="{glass_color}" rx="2"/>'
        )

    # Dimenzije tekst
    ty = oy + h + 20
    parts.append(
        f'<text x="{ox + w / 2:.0f}" y="{ty:.0f}" text-anchor="middle" '
        f'font-family="Arial" font-size="12" fill="#666">'
        f"{width_mm} × {height_mm} mm</text>"
    )

    # Širina strelica (gore)
    ay = oy - 3
    parts.append(
        f'<line x1="{ox:.0f}" y1="{ay:.0f}" x2="{ox + w:.0f}" y2="{ay:.0f}" '
        f'stroke="#999" stroke-width="0.5" marker-start="url(#arrow)" marker-end="url(#arrow)"/>'
    )

    # Visina strelica (lijevo)
    ax = ox - 3
    parts.append(
        f'<line x1="{ax:.0f}" y1="{oy:.0f}" x2="{ax:.0f}" y2="{oy + h:.0f}" stroke="#999" stroke-width="0.5"/>'
    )

    # Arrow marker def
    parts.insert(
        1,
        '<defs><marker id="arrow" markerWidth="6" markerHeight="6" '
        'refX="3" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" '
        'fill="#999" stroke="none"/></marker></defs>',
    )

    parts.append("</svg>")
    return "\n".join(parts)


def generate_door_svg(
    width_mm,
    height_mm,
    wing_config="single_left",
    swing_direction="inward",
    element_type="interior_door",
    profile_color="#78716c",
    door_color="#d4c5a9",
    frame_width=30,
):
    """
    SVG vizualizacija sobnih vrata — tlocrt (pogled odozgo).

    Prikazuje:
    - Okvir (stok)
    - Krilo vrata s lukom otvaranja
    - L/D oznaku
    - Smjer otvaranja (u/van prostorije)
    - Dimenzije
    """
    # Tlocrt: fiksna visina, sirina proporcionalna
    scale = 200 / max(width_mm, 1)
    w = width_mm * scale
    wall_d = 30  # debljina zida u SVG
    pad = 40

    svg_w = w + pad * 2
    svg_h = w + pad * 2 + 50  # kvadratni prostor za luk + dimenzije

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_w:.0f} {svg_h:.0f}" '
        f'width="{svg_w:.0f}" height="{svg_h:.0f}">'
    )

    # Defs
    parts.append(
        "<defs>"
        '<marker id="darrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">'
        '<path d="M0,0 L6,3 L0,6" fill="#999"/></marker></defs>'
    )

    ox = pad
    oy = pad

    is_left = "left" in wing_config or wing_config == "single"
    is_inward = swing_direction != "outward"

    # Zid (dva segmenta oko otvora)
    parts.append(
        f'<rect x="{ox - 10:.0f}" y="{oy:.0f}" width="10" height="{wall_d}" fill="#64748b" rx="1"/>'
    )  # lijevi zid
    parts.append(
        f'<rect x="{ox + w:.0f}" y="{oy:.0f}" width="10" height="{wall_d}" fill="#64748b" rx="1"/>'
    )  # desni zid

    # Stok
    parts.append(f'<rect x="{ox:.0f}" y="{oy:.0f}" width="{w:.0f}" height="{wall_d}" fill="{profile_color}" rx="2"/>')

    # Krilo vrata (linija)
    door_w = w - 10  # krilo je uze od otvora

    if is_left:
        # Sarke lijevo
        hinge_x = ox + 5
        ox + door_w

        if is_inward:
            # Otvaranje u prostoriju (dolje)
            parts.append(
                f'<line x1="{hinge_x:.0f}" y1="{oy + wall_d:.0f}" '
                f'x2="{hinge_x + door_w:.0f}" y2="{oy + wall_d:.0f}" '
                f'stroke="{door_color}" stroke-width="4" stroke-linecap="round"/>'
            )
            # Luk otvaranja (90 stupnjeva dolje-desno)
            r = door_w
            parts.append(
                f'<path d="M{hinge_x + door_w:.0f},{oy + wall_d:.0f} '
                f'A{r:.0f},{r:.0f} 0 0,1 {hinge_x:.0f},{oy + wall_d + r:.0f}" '
                f'fill="none" stroke="{door_color}" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>'
            )
            # Oznaka L
            parts.append(
                f'<text x="{hinge_x + door_w / 2:.0f}" y="{oy + wall_d + door_w / 2:.0f}" '
                f'text-anchor="middle" font-size="16" font-weight="bold" fill="{door_color}" opacity="0.5">L</text>'
            )
        else:
            # Otvaranje van (gore)
            parts.append(
                f'<line x1="{hinge_x:.0f}" y1="{oy:.0f}" '
                f'x2="{hinge_x + door_w:.0f}" y2="{oy:.0f}" '
                f'stroke="{door_color}" stroke-width="4" stroke-linecap="round"/>'
            )
            r = door_w
            parts.append(
                f'<path d="M{hinge_x + door_w:.0f},{oy:.0f} '
                f'A{r:.0f},{r:.0f} 0 0,0 {hinge_x:.0f},{oy - r:.0f}" '
                f'fill="none" stroke="{door_color}" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>'
            )
            parts.append(
                f'<text x="{hinge_x + door_w / 2:.0f}" y="{oy - door_w / 3:.0f}" '
                f'text-anchor="middle" font-size="16" font-weight="bold" fill="{door_color}" opacity="0.5">L</text>'
            )
    else:
        # Sarke desno
        hinge_x = ox + w - 5

        if is_inward:
            parts.append(
                f'<line x1="{hinge_x:.0f}" y1="{oy + wall_d:.0f}" '
                f'x2="{hinge_x - door_w:.0f}" y2="{oy + wall_d:.0f}" '
                f'stroke="{door_color}" stroke-width="4" stroke-linecap="round"/>'
            )
            r = door_w
            parts.append(
                f'<path d="M{hinge_x - door_w:.0f},{oy + wall_d:.0f} '
                f'A{r:.0f},{r:.0f} 0 0,0 {hinge_x:.0f},{oy + wall_d + r:.0f}" '
                f'fill="none" stroke="{door_color}" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>'
            )
            parts.append(
                f'<text x="{hinge_x - door_w / 2:.0f}" y="{oy + wall_d + door_w / 2:.0f}" '
                f'text-anchor="middle" font-size="16" font-weight="bold" fill="{door_color}" opacity="0.5">D</text>'
            )
        else:
            parts.append(
                f'<line x1="{hinge_x:.0f}" y1="{oy:.0f}" '
                f'x2="{hinge_x - door_w:.0f}" y2="{oy:.0f}" '
                f'stroke="{door_color}" stroke-width="4" stroke-linecap="round"/>'
            )
            r = door_w
            parts.append(
                f'<path d="M{hinge_x - door_w:.0f},{oy:.0f} '
                f'A{r:.0f},{r:.0f} 0 0,1 {hinge_x:.0f},{oy - r:.0f}" '
                f'fill="none" stroke="{door_color}" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>'
            )
            parts.append(
                f'<text x="{hinge_x - door_w / 2:.0f}" y="{oy - door_w / 3:.0f}" '
                f'text-anchor="middle" font-size="16" font-weight="bold" fill="{door_color}" opacity="0.5">D</text>'
            )

    # Sarke oznaka (crni krug)
    if is_left:
        parts.append(f'<circle cx="{ox + 5:.0f}" cy="{oy + wall_d / 2:.0f}" r="3" fill="#1a1a2e"/>')
    else:
        parts.append(f'<circle cx="{ox + w - 5:.0f}" cy="{oy + wall_d / 2:.0f}" r="3" fill="#1a1a2e"/>')

    # Dimenzije
    ty = max(oy + wall_d + w + 15, oy + wall_d + 60)
    parts.append(
        f'<text x="{ox + w / 2:.0f}" y="{ty:.0f}" text-anchor="middle" '
        f'font-family="Arial" font-size="11" fill="#666">'
        f"{width_mm} mm | {'L' if is_left else 'D'} | "
        f"{'u prostoriju' if is_inward else 'van prostorije'}</text>"
    )

    # Smjer strelica
    oy + wall_d / 2
    if is_inward:
        parts.append(
            f'<text x="{ox + w / 2:.0f}" y="{oy + wall_d + 15:.0f}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8">&#8595; u prostoriju</text>'
        )
    else:
        parts.append(
            f'<text x="{ox + w / 2:.0f}" y="{oy - 8:.0f}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8">&#8593; van prostorije</text>'
        )

    parts.append("</svg>")
    return chr(10).join(parts)


def generate_mosquito_svg(
    width_mm, height_mm, mounting_type="fixed_frame", mesh_color="#94a3b8", frame_color="#4a5568"
):
    """SVG za komarnik — jednostavan okvir s mrezom."""
    scale = 200 / max(width_mm, height_mm, 1)
    w = width_mm * scale
    h = height_mm * scale
    fw = 15
    pad = 10

    svg_w = w + pad * 2
    svg_h = h + pad * 2 + 25

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_w:.0f} {svg_h:.0f}" '
        f'width="{svg_w:.0f}" height="{svg_h:.0f}">'
    )

    ox, oy = pad, pad

    # Okvir
    parts.append(f'<rect x="{ox:.0f}" y="{oy:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{frame_color}" rx="2"/>')

    # Mreza (cross-hatch pattern)
    gx, gy = ox + fw, oy + fw
    gw, gh = w - fw * 2, h - fw * 2
    if gw > 0 and gh > 0:
        parts.append(
            f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" fill="rgba(148,163,184,0.1)" rx="1"/>'
        )
        # Horizontalne linije mreze
        step = 8
        for i in range(int(gh / step)):
            ly = gy + i * step
            parts.append(
                f'<line x1="{gx:.0f}" y1="{ly:.0f}" x2="{gx + gw:.0f}" y2="{ly:.0f}" '
                f'stroke="{mesh_color}" stroke-width="0.3" opacity="0.4"/>'
            )
        # Vertikalne
        for i in range(int(gw / step)):
            lx = gx + i * step
            parts.append(
                f'<line x1="{lx:.0f}" y1="{gy:.0f}" x2="{lx:.0f}" y2="{gy + gh:.0f}" '
                f'stroke="{mesh_color}" stroke-width="0.3" opacity="0.4"/>'
            )

    # Montaza tip oznaka
    mounting_labels = {
        "fixed_frame": "fiksni okvir",
        "roller": "roletni",
        "plisse": "plise",
        "magnetic": "magnetni",
        "velcro": "velcro",
    }
    label = mounting_labels.get(mounting_type, mounting_type)

    ty = oy + h + 18
    parts.append(
        f'<text x="{ox + w / 2:.0f}" y="{ty:.0f}" text-anchor="middle" '
        f'font-family="Arial" font-size="11" fill="#666">'
        f"{width_mm}x{height_mm}mm | {label}</text>"
    )

    parts.append("</svg>")
    return chr(10).join(parts)

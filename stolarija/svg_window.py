"""
SVG Window Visualizer — generira vizualni prikaz prozora/vrata za PDF ponude.

Podržava:
- Jednokrilni, dvokrilni, trokrilni, fiksni, klizni, kip-turn
- Dimenzije u mm, skalirano na SVG viewBox
- Boja profila (opciono)
- WeasyPrint renderira SVG nativno

Nula dependency — čisti Python string builder.
"""


def generate_window_svg(width_mm, height_mm, wing_config='double',
                        element_type='window', profile_color='#4a5568',
                        glass_color='#bfdbfe', frame_width=40):
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
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'viewBox="0 0 {svg_w:.0f} {svg_h:.0f}" '
                 f'width="{svg_w:.0f}" height="{svg_h:.0f}">')

    # Pozadina
    parts.append(f'<rect width="{svg_w:.0f}" height="{svg_h:.0f}" fill="none"/>')

    ox, oy = pad, pad  # origin

    # Vanjski okvir (profil)
    parts.append(f'<rect x="{ox:.0f}" y="{oy:.0f}" width="{w:.0f}" height="{h:.0f}" '
                 f'fill="{profile_color}" rx="3"/>')

    # Unutarnje staklo
    gx = ox + fw
    gy = oy + fw
    gw = w - fw * 2
    gh = h - fw * 2

    if gw <= 0 or gh <= 0:
        # Previše mali za detalje
        parts.append(f'<rect x="{ox+5:.0f}" y="{oy+5:.0f}" '
                     f'width="{max(w-10,1):.0f}" height="{max(h-10,1):.0f}" '
                     f'fill="{glass_color}" rx="2"/>')
    elif wing_config == 'fixed':
        # Fiksno — jedno staklo, križ
        parts.append(f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2"/>')

    elif wing_config == 'single':
        # Jednokrilno — jedno staklo + handle + dijagonala
        parts.append(f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2"/>')
        # Dijagonala (otvaranje)
        cx = gx + gw / 2
        parts.append(f'<line x1="{gx:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>')
        parts.append(f'<line x1="{gx + gw:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>')
        # Handle
        hx = gx + gw - 8
        hy = gy + gh / 2
        parts.append(f'<rect x="{hx:.0f}" y="{hy - 12:.0f}" width="4" height="24" '
                     f'fill="{profile_color}" rx="2"/>')

    elif wing_config == 'double':
        # Dvokrilno — dva stakla + srednji profil
        half = gw / 2
        mid = fw / 2
        # Lijevo krilo
        parts.append(f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{half - mid:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2"/>')
        # Srednji profil
        parts.append(f'<rect x="{gx + half - mid:.0f}" y="{gy:.0f}" '
                     f'width="{mid * 2:.0f}" height="{gh:.0f}" fill="{profile_color}"/>')
        # Desno krilo
        parts.append(f'<rect x="{gx + half + mid:.0f}" y="{gy:.0f}" '
                     f'width="{half - mid:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2"/>')
        # Dijagonale
        lx = gx + (half - mid) / 2
        rx = gx + half + mid + (half - mid) / 2
        parts.append(f'<line x1="{gx:.0f}" y1="{gy + gh:.0f}" x2="{lx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>')
        parts.append(f'<line x1="{gx + half - mid:.0f}" y1="{gy + gh:.0f}" x2="{lx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>')
        parts.append(f'<line x1="{gx + half + mid:.0f}" y1="{gy + gh:.0f}" x2="{rx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>')
        parts.append(f'<line x1="{gx + gw:.0f}" y1="{gy + gh:.0f}" x2="{rx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1" opacity="0.4"/>')
        # Handles
        parts.append(f'<rect x="{gx + half - mid - 6:.0f}" y="{gy + gh/2 - 12:.0f}" '
                     f'width="4" height="24" fill="{profile_color}" rx="2"/>')
        parts.append(f'<rect x="{gx + half + mid + 2:.0f}" y="{gy + gh/2 - 12:.0f}" '
                     f'width="4" height="24" fill="{profile_color}" rx="2"/>')

    elif wing_config == 'triple':
        # Trokrilno — tri stakla
        third = gw / 3
        mid = fw / 2
        for i in range(3):
            sx = gx + i * third + (mid if i > 0 else 0)
            sw = third - mid
            parts.append(f'<rect x="{sx:.0f}" y="{gy:.0f}" width="{sw:.0f}" height="{gh:.0f}" '
                         f'fill="{glass_color}" rx="2"/>')
        # Profili između
        parts.append(f'<rect x="{gx + third - mid:.0f}" y="{gy:.0f}" '
                     f'width="{mid * 2:.0f}" height="{gh:.0f}" fill="{profile_color}"/>')
        parts.append(f'<rect x="{gx + 2 * third - mid:.0f}" y="{gy:.0f}" '
                     f'width="{mid * 2:.0f}" height="{gh:.0f}" fill="{profile_color}"/>')

    elif wing_config == 'sliding':
        # Klizno — dva stakla s strelicama
        half = gw / 2
        parts.append(f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{half:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2"/>')
        parts.append(f'<rect x="{gx + half:.0f}" y="{gy:.0f}" width="{half:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2" opacity="0.7"/>')
        # Strelice (klizanje)
        ay = gy + gh / 2
        parts.append(f'<text x="{gx + half/2:.0f}" y="{ay:.0f}" '
                     f'text-anchor="middle" font-size="16" fill="{profile_color}" opacity="0.5">⇆</text>')

    elif wing_config == 'tilt_turn':
        # Kip-turn — jedno staklo + dijagonala + horizontalna
        parts.append(f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2"/>')
        cx = gx + gw / 2
        # Nagib (horizontalna linija gore)
        parts.append(f'<line x1="{gx:.0f}" y1="{gy:.0f}" x2="{cx:.0f}" y2="{gy + gh/3:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1" opacity="0.4" stroke-dasharray="4"/>')
        parts.append(f'<line x1="{gx + gw:.0f}" y1="{gy:.0f}" x2="{cx:.0f}" y2="{gy + gh/3:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1" opacity="0.4" stroke-dasharray="4"/>')
        # Zaokret (dijagonala dolje)
        parts.append(f'<line x1="{gx:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>')
        parts.append(f'<line x1="{gx + gw:.0f}" y1="{gy + gh:.0f}" x2="{cx:.0f}" y2="{gy:.0f}" '
                     f'stroke="{profile_color}" stroke-width="1.5" opacity="0.5"/>')
        # Handle
        parts.append(f'<rect x="{gx + gw - 8:.0f}" y="{gy + gh/2 - 12:.0f}" '
                     f'width="4" height="24" fill="{profile_color}" rx="2"/>')
    else:
        # Fallback
        parts.append(f'<rect x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" '
                     f'fill="{glass_color}" rx="2"/>')

    # Dimenzije tekst
    ty = oy + h + 20
    parts.append(f'<text x="{ox + w/2:.0f}" y="{ty:.0f}" text-anchor="middle" '
                 f'font-family="Arial" font-size="12" fill="#666">'
                 f'{width_mm} × {height_mm} mm</text>')

    # Širina strelica (gore)
    ay = oy - 3
    parts.append(f'<line x1="{ox:.0f}" y1="{ay:.0f}" x2="{ox + w:.0f}" y2="{ay:.0f}" '
                 f'stroke="#999" stroke-width="0.5" marker-start="url(#arrow)" marker-end="url(#arrow)"/>')

    # Visina strelica (lijevo)
    ax = ox - 3
    parts.append(f'<line x1="{ax:.0f}" y1="{oy:.0f}" x2="{ax:.0f}" y2="{oy + h:.0f}" '
                 f'stroke="#999" stroke-width="0.5"/>')

    # Arrow marker def
    parts.insert(1, '<defs><marker id="arrow" markerWidth="6" markerHeight="6" '
                    'refX="3" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" '
                    'fill="#999" stroke="none"/></marker></defs>')

    parts.append('</svg>')
    return '\n'.join(parts)

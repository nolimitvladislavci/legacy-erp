import re

with open("memio_world/views_play.py", "r") as f:
    lines = f.readlines()

# Find start and end of _build_book_pages
start = None
end = None
for i, line in enumerate(lines):
    if "def _build_book_pages(" in line:
        start = i
    if start is not None and i > start and line.strip() == "return pages":
        end = i + 1
        break

if start is None or end is None:
    print(f"NOT FOUND: start={start}, end={end}")
    exit(1)

print(f"Replacing lines {start+1}-{end}")

new_func = '''def _build_book_pages(story, lang):
    """Build page list for the book flip engine."""
    import html as _html

    title = getattr(story, f"title_{lang}", "") or story.title_hr
    text = getattr(story, f"text_{lang}", "") or story.text_hr
    paragraphs = [p.strip() for p in text.split("\\n") if p.strip()]

    cover_img = ""
    if story.cover_image:
        try:
            cover_img = story.cover_image.image_url or ""
        except Exception:
            pass

    illustrations = []
    try:
        for item in story.illustrations.using("memio_world").all():
            url = getattr(item, "thumbnail_url", "") or getattr(item, "media_url", "")
            if url:
                illustrations.append(url)
    except Exception:
        pass

    pages = []
    layout_cycle = ["topimg", "text", "split", "overlay", "text", "topimg"]

    # Cover
    pages.append({
        "type": "cover",
        "title": title,
        "author": story.attribution or (story.get_source_display() if hasattr(story, "get_source_display") else ""),
        "cover_img": cover_img,
        "type_label": story.get_story_type_display() if hasattr(story, "get_story_type_display") else "",
        "country": story.country_of_origin or "",
        "reading_time": story.reading_time_minutes,
    })

    # Content — 2 paragraphs per page
    page_num = 1
    first_text = True
    for i in range(0, len(paragraphs), 2):
        chunk = paragraphs[i : i + 2]
        parts = []
        for j, p in enumerate(chunk):
            escaped = _html.escape(p)
            if first_text and j == 0:
                parts.append(f'<p class="drop-cap">{escaped}</p>')
                first_text = False
            else:
                parts.append(f"<p>{escaped}</p>")
        text_html = "".join(parts)

        lay_idx = (page_num - 1) % len(layout_cycle)
        layout = layout_cycle[lay_idx]

        img = ""
        if page_num - 1 < len(illustrations):
            img = illustrations[page_num - 1]
        elif cover_img and page_num == 1:
            img = cover_img
            layout = "fullbleed"

        if not img:
            layout = "text"

        pages.append({
            "type": "page",
            "layout": layout,
            "text": text_html,
            "image": img,
            "page_num": str(page_num),
        })
        page_num += 1

    # Moral
    if story.moral_lesson:
        pages.append({
            "type": "moral",
            "text": _html.escape(story.moral_lesson),
        })

    return pages
'''

lines[start:end] = [new_func]

with open("memio_world/views_play.py", "w") as f:
    f.writelines(lines)
print("OK")

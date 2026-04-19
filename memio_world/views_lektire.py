"""
memio_world/views_lektire.py — Lektire views
"""

import logging

from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from memio_world.lektire_models import LektiraBook, LektiraChapter, LektiraProgress, LektiraQuiz
from memio_world.views_auth import login_required_play

logger = logging.getLogger("memio_world.lektire")


def lektire_home(request):
    """Lista svih lektira, grupirano po razredu."""
    grade_filter = request.GET.get("razred")
    qs = LektiraBook.objects.using("memio_world").filter(is_published=True)
    if grade_filter:
        qs = qs.filter(grade=grade_filter)

    # Grupiraj po razredu
    by_grade = {}
    for book in qs.order_by("grade", "position", "title"):
        by_grade.setdefault(book.grade, []).append(book)

    # Napredak za logiranog djeteta
    progress_map = {}
    parent = getattr(request, "play_parent", None)
    if parent:
        child = getattr(request, "play_child", None)
        if child:
            for p in LektiraProgress.objects.using("memio_world").filter(child=child):
                progress_map[str(p.book_id)] = p

    return render(
        request,
        "memio_world/lektire_home.html",
        {
            "nav": "read",
            "by_grade": by_grade,
            "grade_filter": grade_filter,
            "grades": range(1, 9),
            "progress_map": progress_map,
        },
    )


def lektira_detail(request, slug):
    """Detalj jedne lektire."""
    book = get_object_or_404(LektiraBook.objects.using("memio_world"), slug=slug, is_published=True)
    chapters = list(book.chapters.order_by("number"))

    # Napredak
    progress = None
    parent = getattr(request, "play_parent", None)
    if parent:
        child = getattr(request, "play_child", None)
        if child:
            progress, _ = LektiraProgress.objects.using("memio_world").get_or_create(child=child, book=book)

    # Kviz
    quiz = None
    try:
        quiz = book.quiz if book.quiz.is_published else None
    except LektiraQuiz.DoesNotExist:
        pass

    return render(
        request,
        "memio_world/lektira_detail.html",
        {
            "nav": "read",
            "book": book,
            "chapters": chapters,
            "progress": progress,
            "quiz": quiz,
            "chapters_read_set": set(progress.chapters_read) if progress else set(),
        },
    )


def lektira_chapter_read(request, slug, chapter_num):
    """Čitanje poglavlja — prikaži tekst ili sažetak."""
    book = get_object_or_404(LektiraBook.objects.using("memio_world"), slug=slug, is_published=True)
    chapter = get_object_or_404(LektiraChapter.objects.using("memio_world"), book=book, number=chapter_num)

    # Pronađi napredak
    progress = None
    parent = getattr(request, "play_parent", None)
    if parent:
        child = getattr(request, "play_child", None)
        if child:
            progress, _ = LektiraProgress.objects.using("memio_world").get_or_create(child=child, book=book)

    already_read = progress and (chapter.number in progress.chapters_read)
    prev_chapter = book.chapters.filter(number__lt=chapter_num).order_by("-number").first()
    next_chapter = book.chapters.filter(number__gt=chapter_num).order_by("number").first()

    return render(
        request,
        "memio_world/lektira_chapter.html",
        {
            "nav": "read",
            "book": book,
            "chapter": chapter,
            "progress": progress,
            "already_read": already_read,
            "prev_chapter": prev_chapter,
            "next_chapter": next_chapter,
            "show_summary": already_read,  # Sažetak vidljiv tek nakon čitanja
        },
    )


@login_required_play
@require_POST
def lektira_mark_read(request, slug, chapter_num):
    """Dijete označi poglavlje kao pročitano (HTMX POST)."""
    book = get_object_or_404(LektiraBook.objects.using("memio_world"), slug=slug, is_published=True)
    chapter = get_object_or_404(LektiraChapter.objects.using("memio_world"), book=book, number=chapter_num)

    child = getattr(request, "play_child", None)
    if not child:
        return JsonResponse({"error": "Nema aktivnog profila djeteta"}, status=403)

    progress, _ = LektiraProgress.objects.using("memio_world").get_or_create(child=child, book=book)
    progress.mark_chapter_read(chapter.number)

    logger.info("Lektira pročitana: %s P%s (%s)", book.slug, chapter_num, child.name)

    return JsonResponse(
        {
            "ok": True,
            "completion_pct": progress.completion_pct,
            "status": progress.status,
            "xp_awarded": progress.xp_awarded if progress.status == "completed" else 0,
            "show_summary": True,
            "summary": chapter.summary,
            "discussion_questions": chapter.discussion_questions,
        }
    )

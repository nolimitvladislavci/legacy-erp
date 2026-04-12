import logging

logger = logging.getLogger(__name__)
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import viewsets

from core.company_utils import get_user_company
from partners.models import Partner

from .models import Project, ProjectPhoto, ProjectUpdate
from .serializers import ProjectPhotoSerializer, ProjectSerializer


@login_required
def index(request):
    q = request.GET.get("q", "")
    status_f = request.GET.get("status", "")
    company = get_user_company(request)
    qs = Project.objects.filter(company=company).select_related("client", "company", "manager").order_by("-created_at") if company else Project.objects.none()
    if q:
        qs = qs.filter(Q(name__icontains=q)|Q(code__icontains=q)|Q(location__icontains=q))
    if status_f:
        qs = qs.filter(status=status_f)

    STATUS_CHOICES = [
        ("planning", "Planiranje"), ("active", "Aktivan"),
        ("on_hold", "Pauza"), ("completed", "Završen"), ("cancelled", "Otkazan"),
    ]
    return render(request, "projects/project_list.html", {
        "projects": qs,
        "q": q,
        "status_f": status_f,
        "status_choices": STATUS_CHOICES,
        "total": qs.count(),
    })


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    photos = project.photos.order_by("-uploaded_at")
    updates = project.updates.order_by("-created_at")

    # Work hours from worktime module
    total_hours = 0
    work_entries = []
    try:
        from worktime.models import Project as WTProject
        from worktime.models import TimeEntry
        wt_proj = WTProject.objects.filter(code=project.code).first()
        if wt_proj:
            work_entries = TimeEntry.objects.filter(project=wt_proj).order_by("-date")[:10]
            total_hours_agg = TimeEntry.objects.filter(project=wt_proj).aggregate(s=Sum("duration"))
            total_hours = total_hours_agg["s"] or 0
    except Exception:
        pass

    # Budget usage
    budget_used_pct = 0
    if project.budget and project.budget > 0:
        try:
            from worktime.models import Project as WTProject
            from worktime.models import TimeEntry
            wt_proj = WTProject.objects.filter(code=project.code).first()
            if wt_proj:
                cost = 0
                for entry in TimeEntry.objects.filter(project=wt_proj).select_related("user"):
                    try:
                        ep = entry.user.employee_profile
                        rate = float(ep.hourly_rate or wt_proj.hourly_rate or 0)
                    except Exception:
                        rate = float(wt_proj.hourly_rate or 0)
                    cost += float(entry.duration or 0) * rate
                budget_used_pct = min(int(cost / float(project.budget) * 100), 100)
        except Exception:
            pass

    from django.contrib.auth import get_user_model
    User = get_user_model()
    team_members = project.team.all()
    # Filtriraj radnike po firmi PROJEKTA (ne po prijavljenom useru)
    workers_qs = User.objects.filter(is_active=True).exclude(
        pk__in=team_members.values_list('pk', flat=True)
    )
    if project.company:
        try:
            from accounts.models import UserProfile
            company_user_ids = UserProfile.objects.filter(
                company=project.company
            ).values_list('user_id', flat=True)
            workers_qs = workers_qs.filter(pk__in=company_user_ids)
        except Exception:
            pass
    all_workers = workers_qs.order_by('first_name', 'last_name')

    return render(request, "projects/project_detail.html", {
        "project": project,
        "photos": photos,
        "updates": updates,
        "work_entries": work_entries,
        "total_hours": total_hours,
        "budget_used_pct": budget_used_pct,
        "team_members": team_members,
        "all_workers": all_workers,
    })


@login_required
def project_create(request):
    if request.method == "POST":
        try:
            p = Project(
                name=request.POST["name"],
                code=request.POST["code"],
                description=request.POST.get("description", ""),
                location=request.POST.get("location", ""),
                status=request.POST.get("status", "planning"),
                budget=request.POST.get("budget", 0) or 0,
                is_public="is_public" in request.POST,
            )
            p.company = get_user_company(request)
            client_id = request.POST.get("client")
            if client_id:
                p.client = Partner.objects.get(pk=client_id)
            manager_id = request.POST.get("manager")
            if manager_id:
                p.manager = User.objects.get(pk=manager_id)
            start = request.POST.get("start_date")
            end = request.POST.get("end_date")
            if start: p.start_date = start
            if end: p.end_date = end
            p.save()
            messages.success(request, f"Projekt {p.name} kreiran.")
            next_url = request.POST.get("next") or request.GET.get("next") or ""
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect("project_detail", pk=p.pk)
        except Exception as e:
            messages.error(request, str(e))
    next_url = request.GET.get("next", "")
    return render(request, "projects/project_form.html", {
        "companies": [get_user_company(request)] if get_user_company(request) else [],
        "clients": Partner.objects.filter(is_active=True).order_by("name"),
        "managers": User.objects.filter(is_active=True).order_by("first_name"),
        "next_url": next_url,
        "action": "Novi projekt",
        "status_choices": [
            ("planning","Planiranje"),("active","Aktivan"),
            ("on_hold","Pauza"),("completed","Završen"),("cancelled","Otkazan"),
        ],
    })


@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        try:
            project.name = request.POST["name"]
            project.code = request.POST["code"]
            project.description = request.POST.get("description", "")
            project.location = request.POST.get("location", "")
            project.status = request.POST.get("status", "planning")
            project.budget = request.POST.get("budget", 0) or 0
            project.is_public = "is_public" in request.POST
            project.company = get_user_company(request) or project.company
            client_id = request.POST.get("client")
            project.client = Partner.objects.get(pk=client_id) if client_id else None
            manager_id = request.POST.get("manager")
            project.manager = User.objects.get(pk=manager_id) if manager_id else None
            start = request.POST.get("start_date")
            end = request.POST.get("end_date")
            if start: project.start_date = start
            if end: project.end_date = end
            project.save()
            messages.success(request, f"Projekt {project.name} ažuriran.")
            return redirect("project_detail", pk=project.pk)
        except Exception as e:
            messages.error(request, str(e))
    return render(request, "projects/project_form.html", {
        "project": project,
        "companies": [get_user_company(request)] if get_user_company(request) else [],
        "clients": Partner.objects.filter(is_active=True).order_by("name"),
        "managers": User.objects.filter(is_active=True).order_by("first_name"),
        "action": "Uredi projekt",
        "status_choices": [
            ("planning","Planiranje"),("active","Aktivan"),
            ("on_hold","Pauza"),("completed","Završen"),("cancelled","Otkazan"),
        ],
    })


@login_required
def upload_photo(request):
    if request.method == "POST":
        try:
            project = Project.objects.get(pk=request.POST["project_id"])
            photo = ProjectPhoto(
                project=project,
                uploaded_by=request.user,
                caption=request.POST.get("caption", ""),
                is_public="is_public" in request.POST,
                image=request.FILES["image"],
            )
            photo.save()
            return JsonResponse({"status": "ok", "id": photo.pk})
        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)}, status=400)
    return JsonResponse({"error": "POST only"}, status=405)


@login_required
def project_update_add(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        try:
            ProjectUpdate.objects.create(
                project=project,
                author=request.user,
                title=request.POST.get("title", "Ažuriranje"),
                content=request.POST["content"],
                is_public="is_public" in request.POST,
            )
            messages.success(request, _("Ažuriranje dodano."))
        except Exception as e:
            messages.error(request, str(e))
    return redirect("project_detail", pk=pk)



@login_required
@require_POST
@login_required
@require_POST
def project_team_add(request, pk):
    """Add a user to project team."""
    project = get_object_or_404(Project, pk=pk)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user_id = request.POST.get('user_id', '').strip()
    if not user_id:
        messages.error(request, _('Odaberi radnika iz liste.'))
        return redirect('project_detail', pk=pk)
    try:
        user = User.objects.get(pk=user_id)
        project.team.add(user)
        messages.success(request, f'✅ {user.get_full_name() or user.username} dodan u tim.')
    except User.DoesNotExist:
        messages.error(request, _('Korisnik nije pronađen.'))
    return redirect('project_detail', pk=pk)


@login_required
@require_POST
def project_team_remove(request, pk):
    """Remove a user from project team."""
    project = get_object_or_404(Project, pk=pk)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user_id = request.POST.get('user_id')
    if user_id:
        try:
            user = User.objects.get(pk=user_id)
            project.team.remove(user)
            messages.success(request, f'{user.get_full_name() or user.username} uklonjen iz tima.')
        except User.DoesNotExist:
            pass
    return redirect('project_detail', pk=pk)

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class ProjectPhotoViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return ProjectPhoto.objects.all()
    def get_serializer_class(self):
        return ProjectPhotoSerializer

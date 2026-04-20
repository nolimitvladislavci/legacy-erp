from django.views.generic import ListView, DetailView
from core.base_view import TenantView
from .models import Animal, AdoptionRequest, FosterFamily


class AnimalListView(TenantView, ListView):
    model = Animal
    template_name = "shelter/animal_list.html"
    context_object_name = "animals"

    def get_queryset(self):
        qs = Animal.objects.filter(company=self.company)
        status = self.request.GET.get("status")
        species = self.request.GET.get("species")
        if status:
            qs = qs.filter(status=status)
        if species:
            qs = qs.filter(species=species)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Animal.STATUS_CHOICES
        ctx["species_choices"] = Animal.SPECIES_CHOICES
        ctx["total"] = Animal.objects.filter(company=self.company).count()
        return ctx


class AnimalDetailView(TenantView, DetailView):
    model = Animal
    template_name = "shelter/animal_detail.html"
    context_object_name = "animal"

    def get_queryset(self):
        return Animal.objects.filter(company=self.company)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["vet_visits"] = self.object.vet_visits.all()
        ctx["adoption_requests"] = self.object.adoption_requests.all()
        return ctx


class AnimalCreateView(TenantView):
    template_name = "shelter/animal_form.html"

    def get(self, request):
        return self.render(
            request,
            {
                "form": type(
                    "F",
                    (),
                    {"species": type("F2", (), {"field": type("F3", (), {"choices": Animal.SPECIES_CHOICES})()})()},
                )()
            },
        )

    def post(self, request):
        name = request.POST.get("name", "").strip()
        if not name:
            return self.render(request, {"error": "Ime je obavezno"})
        animal = Animal.objects.create(
            company=self.company,
            created_by=request.user,
            name=name,
            species=request.POST.get("species", "dog"),
            breed=request.POST.get("breed", ""),
            gender=request.POST.get("gender", "U"),
            kennel_number=request.POST.get("kennel_number", ""),
            microchip_number=request.POST.get("microchip_number", ""),
            is_microchipped="is_microchipped" in request.POST,
            is_vaccinated="is_vaccinated" in request.POST,
            is_neutered="is_neutered" in request.POST,
            intake_reason=request.POST.get("intake_reason", ""),
        )
        from django.shortcuts import redirect

        return redirect("shelter:animal_detail", pk=animal.pk)


class AdoptionListView(TenantView, ListView):
    model = AdoptionRequest
    template_name = "shelter/adoption_list.html"
    context_object_name = "requests"

    def get_queryset(self):
        return AdoptionRequest.objects.filter(company=self.company).select_related("animal")


class FosterFamilyListView(TenantView, ListView):
    model = FosterFamily
    template_name = "shelter/foster_list.html"
    context_object_name = "families"

    def get_queryset(self):
        return FosterFamily.objects.filter(company=self.company, is_active=True)

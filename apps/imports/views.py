from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from .forms import ImportForm
from .models import ImportBatch
from .parser import CSVFormatError, parse_csv
from .services import import_statement


class ImportView(LoginRequiredMixin, View):
    template_name = "imports/upload.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ImportForm(user=request.user)})

    def post(self, request):
        form = ImportForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            try:
                parsed = parse_csv(
                    upload.read(), preferred_date_order=form.cleaned_data["date_order"]
                )
            except CSVFormatError as exc:
                form.add_error("file", str(exc))
            else:
                batch = import_statement(
                    user=request.user,
                    account=form.cleaned_data["account"],
                    filename=upload.name,
                    parsed=parsed,
                )
                return redirect("imports:detail", pk=batch.pk)
        return render(request, self.template_name, {"form": form})


class ImportDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        batch = get_object_or_404(ImportBatch, pk=pk, user=request.user)
        batch.refresh_from_db()
        return render(request, "imports/detail.html", {"batch": batch})


class ImportHistoryView(LoginRequiredMixin, ListView):
    template_name = "imports/history.html"
    context_object_name = "batches"

    def get_queryset(self):
        return ImportBatch.objects.filter(user=self.request.user).select_related("account")

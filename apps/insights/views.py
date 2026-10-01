from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .analytics import dashboard


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "insights/dashboard.html"

    def get_context_data(self, **kwargs):
        data = dashboard(self.request.user)
        return super().get_context_data(
            data=data,
            chart_data={"cashflow": data["cashflow"], "categories": data["categories"]},
            **kwargs,
        )

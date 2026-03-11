# apps/faq/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View

from .models import FAQItem, FAQFile
from .forms import FAQItemForm, FAQFileForm


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_admin


class HtmxMixin:
    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return [self.partial_template_name]
        return [self.template_name]


class FAQListView(LoginRequiredMixin, ListView):
    model = FAQItem
    template_name = "faq/faq_list.html"
    context_object_name = "faq_items"

    def get_queryset(self):
        return FAQItem.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["faq_files"] = FAQFile.objects.all()
        context["is_admin"] = self.request.user.is_admin
        return context


class FAQItemCreateView(LoginRequiredMixin, AdminRequiredMixin, HtmxMixin, CreateView):
    model = FAQItem
    form_class = FAQItemForm
    template_name = "faq/faq_form.html"
    partial_template_name = "faq/partials/faq_form.html"
    success_url = reverse_lazy("faq:list")

    def form_valid(self, form):
        super().form_valid(form)  # Сохраняем объект

        if self.request.headers.get("HX-Request"):
            # Возвращаем пустой ответ с заголовком редиректа
            # from django.http import HttpResponse
            response = HttpResponse("")
            response["HX-Redirect"] = str(self.success_url)
            return response

        return redirect(self.success_url)


class FAQItemDetailView(LoginRequiredMixin, DetailView):
    model = FAQItem
    template_name = "faq/partials/faq_card.html"
    context_object_name = "item"


class FAQItemUpdateView(LoginRequiredMixin, AdminRequiredMixin, HtmxMixin, UpdateView):
    model = FAQItem
    form_class = FAQItemForm
    template_name = "faq/faq_form.html"
    partial_template_name = "faq/partials/faq_form.html"
    success_url = reverse_lazy("faq:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_edit"] = True
        return context

    def form_valid(self, form):
        super().form_valid(form)

        if self.request.headers.get("HX-Request"):
            # from django.http import HttpResponse
            response = HttpResponse("")
            response["HX-Redirect"] = str(self.success_url)
            return response

        return redirect(self.success_url)


class FAQItemDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = FAQItem
    success_url = reverse_lazy("faq:list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()

        if request.headers.get("HX-Request"):
            return HttpResponse("", headers={
                "HX-Trigger": "faqItemDeleted",
                "HX-Redirect": str(self.success_url)
            })
        return super().delete(request, *args, **kwargs)


class FAQFileUploadView(LoginRequiredMixin, AdminRequiredMixin, HtmxMixin, CreateView):
    model = FAQFile
    form_class = FAQFileForm
    template_name = "faq/file_form.html"
    partial_template_name = "faq/partials/file_form.html"
    success_url = reverse_lazy("faq:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get("HX-Request"):
            return self.render_to_response(
                self.get_context_data(form=FAQFileForm(), success=True)
            )
        return response


class FAQFileDownloadView(LoginRequiredMixin, View):
    """Скачивание файла"""

    def get(self, request, pk):
        file_obj = get_object_or_404(FAQFile, pk=pk)
        response = FileResponse(file_obj.file, as_attachment=True)
        return response


class FAQFileDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = FAQFile
    success_url = reverse_lazy("faq:list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()

        if request.headers.get("HX-Request"):
            return HttpResponse("", headers={"HX-Trigger": "faqFileDeleted"})
        return super().delete(request, *args, **kwargs)
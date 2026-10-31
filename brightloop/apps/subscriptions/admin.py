from django.contrib import admin

from .models import QuotationTemplate, QuotationTemplateLine, Subscription, SubscriptionLine


class SubscriptionLineInline(admin.TabularInline):
    model = SubscriptionLine
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "plan", "status", "start_date", "next_billing_date", "is_paused")
    list_filter = ("status", "is_paused")
    search_fields = ("number", "customer__full_name", "customer__user__email")
    inlines = [SubscriptionLineInline]


class TemplateLineInline(admin.TabularInline):
    model = QuotationTemplateLine
    extra = 0


@admin.register(QuotationTemplate)
class QuotationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "plan", "validity_days", "payment_term_days", "is_active")
    inlines = [TemplateLineInline]

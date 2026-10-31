from django.contrib import admin

from .models import DiscountRedemption, Invoice, InvoiceLine, Payment


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "customer", "period_start", "period_end", "total_amount",
                    "amount_paid", "outstanding_amount", "due_date", "status")
    list_filter = ("status",)
    search_fields = ("invoice_number", "customer__full_name")
    inlines = [InvoiceLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "payment_method", "payment_date", "status")
    list_filter = ("status", "payment_method")


admin.site.register(DiscountRedemption)

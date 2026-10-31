from django.contrib import admin

from .models import DiscountRule, Plan, Product, ProductVariant, TaxRule


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "sales_price", "cost_price", "status")
    list_filter = ("status", "product_type")
    search_fields = ("name",)
    inlines = [VariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "attribute", "extra_price", "status")
    list_filter = ("status",)
    search_fields = ("name", "product__name")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "price", "billing_period", "is_available", "start_date", "end_date")
    list_filter = ("billing_period", "is_available")
    search_fields = ("name", "product__name")


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "percentage", "is_active")


@admin.register(DiscountRule)
class DiscountRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "discount_type", "value", "applies_to", "times_used", "usage_limit", "is_active")
    list_filter = ("discount_type", "applies_to", "is_active")

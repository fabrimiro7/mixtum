import django_filters
from django.db import models
from .models import Link


class LinkFilter(django_filters.FilterSet):
    label = django_filters.CharFilter(lookup_expr="exact")
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Link
        fields = ["label"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            models.Q(title__icontains=value)
            | models.Q(description__icontains=value)
            | models.Q(url__icontains=value)
        )

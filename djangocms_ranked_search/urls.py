from django.urls import path

from .views import CMSWeightedSearchView

app_name = "ranked_search"

urlpatterns = [
    path("", CMSWeightedSearchView.as_view(), name="search"),
]

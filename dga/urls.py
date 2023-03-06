from django.urls import path
from dga import views

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
]
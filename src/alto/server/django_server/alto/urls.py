from django.urls import path

from . import views

urlpatterns = [
    path('pathvector/<str:path_vector>', views.AltoView.as_view(), name='alto'),
]

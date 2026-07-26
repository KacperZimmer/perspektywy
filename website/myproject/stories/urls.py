from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('element/<int:id>/', views.view_event, name='view_event')
]
from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('rating/', views.leaderboard, name='leaderboard'),
    path('api/attempts/<int:pk>/events/', views.AttemptEventAPI.as_view()),
    path('accounts/', include('accounts.urls')),
    path('teacher/new/', views.editor, name='test-create'),
    path('teacher/tests/<int:pk>/', views.editor, name='test-edit'),
    path('teacher/tests/<int:pk>/results/', views.results, name='test-results'),
    path('attempts/<int:pk>/', views.room, name='attempt-room'),
    path('api/tests/lookup/', views.LookupAPI.as_view()),
    path('api/tests/<str:code>/start/', views.StartAPI.as_view()),
    path('api/attempts/<int:pk>/', views.AttemptAPI.as_view()),
    path('api/attempts/<int:pk>/<str:operation>/', views.AttemptAPI.as_view()),
    path('api/teacher/tests/', views.TeacherTestAPI.as_view()),
    path('api/teacher/tests/<int:pk>/', views.TeacherTestAPI.as_view()),
    path('api/teacher/tests/<int:pk>/<str:operation>/', views.TeacherTestAPI.as_view()),
]

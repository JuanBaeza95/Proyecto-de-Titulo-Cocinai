"""
URL configuration for cocinAI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from usuarios import views as user_views

def logout_view(request):
    """Vista personalizada para logout que maneja GET"""
    logout(request)
    return redirect('login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('login'), name='root_redirect'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', logout_view, name='logout'),
    path('inventario/', include('inventario.urls', namespace='inventario')),
    path('compras/', include('compras.urls', namespace='compras')),
    path('produccion/', include('produccion.urls', namespace='produccion')),
    path('ventas/', include('ventas.urls', namespace='ventas')),
    path('prediccion/', include('prediccion.urls', namespace='prediccion')),
    path('usuarios/', include('usuarios.urls', namespace='usuarios')),
    path('dashboard/', login_required(user_views.dashboard), name='dashboard'),
    
]

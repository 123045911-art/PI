<!DOCTYPE html>
<html lang="es">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@yield('title', 'Dashboard') | Conteo de Personas</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <link rel="stylesheet" href="{{ asset('css/dashboard.css') }}">
    @stack('styles')
</head>

<body>
    <div id="sidebar-menu" class="sidebar-modern d-flex flex-column align-items-center py-4"> {{-- sidebar --}}
        <img src="{{ asset('images/LogoVisioflow.png') }}" alt="Logo" class="logo mb-3"> {{-- logo --}}
        <span class="company-name">VISIOFLOW</span> {{-- nombre --}}
        <hr class="divider"> {{-- SEPARADOR --}}

        <ul class="nav nav-pills flex-column text-center w-100 mt-2">
            <li class="nav-item mb-3">
                <a href="{{ url('/') }}" class="nav-link modern-link @if(Request::is('/')) active @endif">
                    <i class="fas fa-home icon"></i>
                    <span class="label">Dashboard</span>
                </a>
            </li>
            <li class="nav-item mb-3">
                <a href="{{ route('areas.index') }}"
                    class="nav-link modern-link @if(Request::is('areas*')) active @endif">
                    <i class="fas fa-map icon"></i>
                    <span class="label">Áreas</span>
                </a>
            </li>
            <li class="nav-item mb-3">
                <a href="{{ route('eventos.index') }}"
                    class="nav-link modern-link @if(Request::is('eventos*')) active @endif">
                    <i class="fas fa-calendar icon"></i>
                    <span class="label">Historial</span>
                </a>
            </li>
        </ul>
    </div>
    <div class="main-content">
        <header class="bg-white shadow-sm p-4 sticky-top d-flex justify-content-between align-items-center">
            <h1 class="h3 mb-0 text-dark">@yield('title', 'Dashboard')</h1>
            <span class="text-muted d-none d-md-block">
                <i class="far fa-calendar-alt me-2"></i> {{ \Carbon\Carbon::now()->format('d M, Y') }}
            </span>
        </header>
        <main class="flex-grow-1 p-4">
            @if (session('success'))
                <div class="alert alert-success alert-dismissible fade show" role="alert">
                    <strong>Éxito:</strong> {{ session('success') }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            @endif
            @if (session('error'))
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    <strong>Error:</strong> {{ session('error') }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            @endif
            @yield('content')
        </main>
    </div>
    {{-- Scripts --}}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    @stack('scripts')
</body>

</html>
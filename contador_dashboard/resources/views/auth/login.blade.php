<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VISIOFLOW | Iniciar Sesión</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <style>
        body {
            background-color: #0f172a;
            background-image: radial-gradient(circle at center, #1e293b 0%, #0f172a 100%);
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 1.5rem;
            padding: 3rem;
            width: 100%;
            max-width: 450px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .logo {
            width: 80px;
            margin-bottom: 1rem;
        }
        .text-gradient {
            background: linear-gradient(to right, #818cf8, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }
        .form-control {
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
            padding: 0.8rem 1.2rem;
            border-radius: 0.75rem;
        }
        .form-control:focus {
            background: rgba(0, 0, 0, 0.3);
            border-color: #6366f1;
            box-shadow: 0 0 0 0.25rem rgba(99, 102, 241, 0.25);
            color: white;
        }
        .btn-primary {
            background: #6366f1;
            border: none;
            padding: 0.8rem;
            border-radius: 0.75rem;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-primary:hover {
            background: #4f46e5;
            transform: translateY(-1px);
        }
        .label-custom {
            color: #94a3b8;
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="login-card text-center">
        <img src="{{ asset('images/LogoVisioflow.png') }}" alt="Logo" class="logo">
        <h1 class="h2 text-gradient mb-4">VISIOFLOW</h1>
        <p class="text-secondary small mb-4">Ingresa tus credenciales para acceder al dashboard</p>

        @if($errors->any())
            <div class="alert alert-danger py-2 small mb-4">
                {{ $errors->first() }}
            </div>
        @endif

        @if(session('info'))
            <div class="alert alert-info py-2 small mb-4">
                {{ session('info') }}
            </div>
        @endif

        <form action="{{ route('login.post') }}" method="POST">
            @csrf
            <div class="mb-3 text-start">
                <label class="label-custom">Usuario</label>
                <input type="text" name="username" class="form-control" placeholder="Tu nombre de usuario" required value="{{ old('username') }}">
            </div>
            <div class="mb-4 text-start">
                <label class="label-custom">Contraseña</label>
                <input type="password" name="password" class="form-control" placeholder="••••••••" required>
            </div>
            <button type="submit" class="btn-primary w-100">Iniciar Sesión</button>
        </form>
        
        <p class="mt-4 text-secondary x-small" style="font-size: 0.7rem;">&copy; {{ date('Y') }} VISIOFLOW Systems</p>
    </div>
</body>
</html>

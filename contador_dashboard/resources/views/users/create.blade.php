@extends('layouts.app')

@section('title', 'Nuevo Usuario')

@section('content')
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card shadow-sm border-0 rounded-4">
            <div class="card-body p-4">
                <div class="mb-4 d-flex align-items-center gap-3">
                    <a href="{{ route('users.index') }}" class="btn btn-outline-secondary btn-sm rounded-circle"><i class="fas fa-arrow-left"></i></a>
                    <h4 class="fw-bold mb-0">Crear Nuevo Usuario</h4>
                </div>

                <form action="{{ route('users.store') }}" method="POST">
                    @csrf
                    <div class="mb-3">
                        <label for="username" class="form-label text-muted small fw-bold">Nombre de Usuario</label>
                        <input type="text" name="username" id="username" class="form-control" placeholder="Ej: admin_sucursal" required value="{{ old('username') }}">
                        @error('username') <span class="text-danger small">{{ $message }}</span> @enderror
                    </div>

                    <div class="mb-3">
                        <label for="password" class="form-label text-muted small fw-bold">Contraseña</label>
                        <input type="password" name="password" id="password" class="form-control" placeholder="Mínimo 4 caracteres" required>
                        @error('password') <span class="text-danger small">{{ $message }}</span> @enderror
                    </div>

                    <div class="mb-4">
                        <div class="form-check form-switch bg-light p-3 rounded-3 border">
                            <input class="form-check-input ms-0 me-3" type="checkbox" role="switch" id="is_admin" name="is_admin">
                            <label class="form-check-label fw-bold small" for="is_admin">Asignar como Administrador</label>
                            <div class="text-muted extra-small" style="font-size: 0.75rem;">Permite gestionar otros usuarios y la configuración de las cámaras.</div>
                        </div>
                    </div>

                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary py-2 fw-bold">Guardar Usuario</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
@endsection

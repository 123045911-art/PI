@extends('layouts.app')

@section('title', 'Editar Usuario')

@section('content')
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card shadow-sm border-0 rounded-4">
            <div class="card-body p-4">
                <div class="mb-4 d-flex align-items-center gap-3">
                    <a href="{{ route('users.index') }}" class="btn btn-outline-secondary btn-sm rounded-circle"><i class="fas fa-arrow-left"></i></a>
                    <h4 class="fw-bold mb-0">Editar Usuario: {{ $user->username }}</h4>
                </div>

                <form action="{{ route('users.update', $user->id) }}" method="POST">
                    @csrf
                    @method('PUT')
                    
                    <div class="mb-3">
                        <label for="username" class="form-label text-muted small fw-bold">Nombre de Usuario</label>
                        <input type="text" name="username" id="username" class="form-control" value="{{ $user->username }}" required autocomplete="off">
                        @error('username') <span class="text-danger small">{{ $message }}</span> @enderror
                    </div>

                    <div class="mb-3">
                        <label for="password" class="form-label text-muted small fw-bold">Nueva Contraseña <span class="text-secondary opacity-50 fw-normal">(opcional)</span></label>
                        <input type="password" name="password" id="password" class="form-control" placeholder="Dejar en blanco para no cambiar">
                        @error('password') <span class="text-danger small">{{ $message }}</span> @enderror
                    </div>

                    <div class="mb-4">
                        <div class="form-check form-switch bg-light p-3 rounded-3 border">
                            <input class="form-check-input ms-0 me-3" type="checkbox" role="switch" id="is_admin" name="is_admin" {{ $user->is_admin ? 'checked' : '' }}>
                            <label class="form-check-label fw-bold small" for="is_admin">Es Administrador</label>
                            <div class="text-info extra-small" style="font-size: 0.75rem;">Otorga permisos de gestión completa del sistema.</div>
                        </div>
                    </div>

                    <div class="d-grid mt-4">
                        <button type="submit" class="btn btn-primary py-2 fw-bold shadow-sm">Guardar Cambios</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
@endsection

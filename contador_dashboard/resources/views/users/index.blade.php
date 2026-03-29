@extends('layouts.app')

@section('title', 'Gestión de Usuarios')

@section('content')
<div class="card shadow-sm border-0 rounded-4">
    <div class="card-body p-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h4 class="fw-bold mb-1">Listado de Usuarios</h4>
                <p class="text-muted small mb-0">Administra los accesos al dashboard y al sistema de cámaras.</p>
            </div>
            <a href="{{ route('users.create') }}" class="btn btn-primary d-flex align-items-center gap-2">
                <i class="fas fa-user-plus"></i> Nuevo Usuario
            </a>
        </div>

        <form action="{{ route('users.index') }}" method="GET" class="mb-4">
            <div class="input-group">
                <span class="input-group-text bg-white border-end-0"><i class="fas fa-search text-muted"></i></span>
                <input type="text" name="name" class="form-control border-start-0 ps-0" placeholder="Buscar por nombre..." value="{{ request('name') }}">
                <button class="btn btn-outline-secondary" type="submit">Buscar</button>
            </div>
        </form>

        <div class="table-responsive">
            <table class="table table-hover align-middle">
                <thead class="bg-light">
                    <tr>
                        <th class="ps-4">ID</th>
                        <th>Nombre de Usuario</th>
                        <th>Rol</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    @forelse($users as $user)
                    <tr>
                        <td class="ps-4 text-muted small">#{{ $user['id'] }}</td>
                        <td class="fw-semibold">{{ $user['username'] }}</td>
                        <td>
                            @if($user['is_admin'])
                            <span class="badge bg-indigo-subtle text-indigo border border-indigo-subtle px-3 py-2 rounded-pill">
                                <i class="fas fa-shield-alt me-1"></i> Administrador
                            </span>
                            @else
                            <span class="badge bg-light text-secondary border px-3 py-2 rounded-pill">
                                <i class="fas fa-user me-1"></i> Usuario
                            </span>
                            @endif
                        </td>
                        <td>
                            <div class="d-flex gap-2">
                                <a href="{{ route('users.edit', $user['id']) }}" class="btn btn-sm btn-outline-primary px-3">
                                    <i class="fas fa-edit me-1"></i> Editar
                                </a>
                                <form action="{{ route('users.destroy', $user['id']) }}" method="POST" onsubmit="return confirm('¿Eliminar este usuario?')">
                                    @csrf
                                    @method('DELETE')
                                    <button type="submit" class="btn btn-sm btn-outline-danger px-3">
                                        <i class="fas fa-trash-alt me-1"></i> Eliminar
                                    </button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    @empty
                    <tr>
                        <td colspan="4" class="text-center py-5">
                            <div class="py-3">
                                <i class="fas fa-users-slash display-4 text-muted mb-3 d-block"></i>
                                <p class="text-muted">No se encontraron usuarios.</p>
                            </div>
                        </td>
                    </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </div>
</div>

<style>
    .bg-indigo-subtle { background-color: rgba(99, 102, 241, 0.1) !important; }
    .text-indigo { color: #6366f1 !important; }
    .border-indigo-subtle { border-color: rgba(99, 102, 241, 0.2) !important; }
    .table thead th { 
        font-size: 0.75rem; 
        text-transform: uppercase; 
        letter-spacing: 0.05em;
        font-weight: 700;
        color: #64748b;
        background: #f8fafc;
        border-top: none;
    }
</style>
@endsection

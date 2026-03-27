@extends('layouts.app') 
@section('title', 'Gestión de Áreas')
@section('content')
    <div class="container mt-4">
        <p class="lead">Listado de las áreas definidas en la aplicación</p>
        <div class="card shadow-sm mt-4">
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead>
                            <tr>
                                <th>ID BD</th>
                                <th>Nombre del área</th>
                                <th>Personas dentro</th>
                                <th>Última actualización</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            @forelse ($areas as $area)
                            <tr>
                                <td>{{ $area->id }}</td>
                                <td><span class="fw-bold">{{ $area->name }}</span></td>
                                <td>
                                    {{ $area->estado->people_count ?? 0 }}
                                    @if (!$area->estado)
                                        <span class="badge bg-danger ms-2">Sin datos</span>
                                    @endif
                                </td>
                                <td>{{ $area->estado->last_update ?? 'N/A' }}</td>
                                <td>
                                    <a href="{{ route('areas.edit', $area) }}" class="btn btn-sm btn-info text-white me-2">
                                        Renombrar
                                    </a>
                                    
                                    {{-- Formulario para Eliminar --}}
                                    <form action="{{ route('areas.destroy', $area) }}" method="POST" class="d-inline" onsubmit="return confirm('¿Estás seguro de que quieres eliminar el área {{ $area->name }} y todos sus eventos? Esta acción es irreversible.');">
                                        @csrf
                                        @method('DELETE')
                                        <button type="submit" class="btn btn-sm btn-danger">Eliminar</button>
                                    </form>
                                </td>
                            </tr>
                            @empty
                            <tr>
                                <td colspan="5" class="text-center">No hay áreas registradas. Ejecuta la app para crear algunas</td>
                            </tr>
                            @endforelse
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
@endsection
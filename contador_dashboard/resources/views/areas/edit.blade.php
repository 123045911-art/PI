@extends('layouts.app')
@section('title', 'Renombrar Área')
@section('content')
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-6 offset-md-3">
                <div class="card shadow-sm">
                    <div class="card-header bg-info text-white">
                        <h2>Renombrar área: {{ $area->name }}</h2>
                    </div>
                    <div class="card-body">
                        {{-- Formulario de actualización --}}
                        <form action="{{ route('areas.update', $area) }}" method="POST">
                            @csrf
                            @method('PUT') {{-- Método HTTP necesario para la acción update --}}
                            <div class="mb-3">
                                <label for="name" class="form-label fw-bold">Nuevo nombre del área</label>
                                <input type="text" class="form-control @error('name') is-invalid @enderror" id="name" name="name" value="{{ old('name', $area->name) }}" required>
                                {{-- Mostrar errores de validación--}}
                                @error('name')
                                    <div class="invalid-feedback">
                                        {{ $message }}
                                    </div>
                                @enderror
                            </div>
                            <button type="submit" class="btn btn-primary">Guardar cambios</button>
                            <a href="{{ route('areas.index') }}" class="btn btn-secondary">Cancelar</a>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
@endsection
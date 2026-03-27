@extends('layouts.app')
@section('title', 'Historial completo de eventos')
@section('content')
    <div class="container mt-4">
        <p class="lead">Listado de todas las entradas y salidas registradas en el sistema</p>
        <div class="card shadow-sm mt-4">
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-sm">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Área</th>
                                <th>Evento</th>
                                <th>Track ID</th>
                                <th>Dwell Time (Segundos)</th>
                            </tr>
                        </thead>
                        <tbody>
                            @forelse ($eventos as $evento)
                                <tr>
                                    <td>{{ \Carbon\Carbon::parse($evento->timestamp)->format('Y-m-d H:i:s') }}</td>
                                    <td><span class="fw-bold">{{ $evento->area->name ?? 'Área Eliminada' }}</span></td>
                                    <td>
                                        <span
                                            class="badge 
                                                                @if($evento->event == 'enter') bg-success @else bg-danger @endif">
                                            {{ strtoupper($evento->event) }}
                                        </span>
                                    </td>
                                    <td>{{ $evento->track_id }}</td>
                                    <td>
                                        @if($evento->event == 'exit')
                                            {{ number_format($evento->dwell, 2) }}
                                        @else
                                            N/A
                                        @endif
                                    </td>
                                </tr>
                            @empty
                                <tr>
                                    <td colspan="5" class="text-center">No se han registrado eventos en el sistema.</td>
                                </tr>
                            @endforelse
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div class="mt-4">
            {{ $eventos->links('pagination::bootstrap-5') }}
        </div>
    </div>
@endsection
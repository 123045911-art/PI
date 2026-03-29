@extends('layouts.app')
@section('title', 'Historial completo de eventos')
@section('content')
    <div class="container mt-4">
        <p class="lead">Listado de todas las entradas y salidas registradas en el sistema</p>

        @if(isset($total))
            <p class="text-muted">Total de registros: <strong>{{ $total }}</strong></p>
        @endif

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
                                                @if(strtoupper($evento->event) == 'ENTER') bg-success @else bg-danger @endif">
                                            {{ strtoupper($evento->event) }}
                                        </span>
                                    </td>
                                    <td>{{ $evento->track_id }}</td>
                                    <td>
                                        @if(strtoupper($evento->event) == 'EXIT')
                                            {{ number_format($evento->dwell ?? 0, 2) }}
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

        {{-- Paginación manual --}}
        @if(isset($totalPages) && $totalPages > 1)
            <nav class="mt-4" aria-label="Paginación de eventos">
                <ul class="pagination justify-content-center">
                    {{-- Botón Anterior --}}
                    <li class="page-item @if($page <= 1) disabled @endif">
                        <a class="page-link" href="{{ url('/eventos?page=' . ($page - 1)) }}">
                            &laquo; Anterior
                        </a>
                    </li>

                    {{-- Números de página (mostrar máximo 5 alrededor de la actual) --}}
                    @php
                        $start = max(1, $page - 2);
                        $end = min($totalPages, $page + 2);
                    @endphp

                    @if($start > 1)
                        <li class="page-item">
                            <a class="page-link" href="{{ url('/eventos?page=1') }}">1</a>
                        </li>
                        @if($start > 2)
                            <li class="page-item disabled"><span class="page-link">...</span></li>
                        @endif
                    @endif

                    @for($i = $start; $i <= $end; $i++)
                        <li class="page-item @if($i == $page) active @endif">
                            <a class="page-link" href="{{ url('/eventos?page=' . $i) }}">{{ $i }}</a>
                        </li>
                    @endfor

                    @if($end < $totalPages)
                        @if($end < $totalPages - 1)
                            <li class="page-item disabled"><span class="page-link">...</span></li>
                        @endif
                        <li class="page-item">
                            <a class="page-link" href="{{ url('/eventos?page=' . $totalPages) }}">{{ $totalPages }}</a>
                        </li>
                    @endif

                    {{-- Botón Siguiente --}}
                    <li class="page-item @if($page >= $totalPages) disabled @endif">
                        <a class="page-link" href="{{ url('/eventos?page=' . ($page + 1)) }}">
                            Siguiente &raquo;
                        </a>
                    </li>
                </ul>
            </nav>
        @endif
    </div>
@endsection
"""Contrato gRPC: el servicio aforo real debe cumplir aforo.proto.

Todos los tests son read-only o net-zero (vender+anular en el mismo test),
sin dejar stock alterado.
"""
import uuid

import aforo_pb2

from conftest import EVENTO_ID


def test_proto_y_pb2_sincronizados():
    """el código generado commiteado debe matches con regenerar desde el .proto"""
    import subprocess, tempfile, pathlib
    proto_dir = pathlib.Path(__file__).parent.parent / "backend" / "aforo"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["python", "-m", "grpc_tools.protoc", "--proto_path=.",
             "--python_out=" + tmp, "--grpc_python_out=" + tmp, "aforo.proto"],
            cwd=proto_dir, check=True,
        )
        for f in ("aforo_pb2.py", "aforo_pb2_grpc.py"):
            assert (pathlib.Path(tmp) / f).read_bytes() == (proto_dir / f).read_bytes(), f"{f} stale vs proto"


def test_list_eventos_contract(stub):
    resp = stub.ListEventos(aforo_pb2.ListEventosRequest(), timeout=5)
    assert len(resp.eventos) >= 1
    for e in resp.eventos:
        assert all([e.evento_id, e.nombre_evento, e.nombre_lugar, e.fecha_evento])
        uuid.UUID(e.evento_id)  # string con formato uuid según contrato


def test_list_secciones_flag(stub):
    """evento válido: secciones + invariantes; evento inexistente: flag False y lista vacía."""
    resp = stub.ListSecciones(aforo_pb2.ListSeccionesRequest(evento_id=EVENTO_ID), timeout=5)
    assert resp.evento_existe is True
    assert len(resp.secciones) >= 1
    for s in resp.secciones:
        assert 0 <= s.cantidad_entradas_disponibles <= s.capacidad_total

    resp2 = stub.ListSecciones(aforo_pb2.ListSeccionesRequest(evento_id=str(uuid.uuid4())), timeout=5)
    assert resp2.evento_existe is False
    assert len(resp2.secciones) == 0


def test_get_seccion_valida_e_inexistente(stub, seccion_con_stock):
    resp = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=seccion_con_stock.seccion_id), timeout=5)
    assert resp.existe is True
    assert resp.evento_id == EVENTO_ID

    resp2 = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=str(uuid.uuid4())), timeout=5)
    assert resp2.existe is False


def test_vender_anular_net_zero(stub, seccion_con_stock):
    sid = seccion_con_stock.seccion_id
    antes = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=sid), timeout=5).cantidad_entradas_disponibles

    v = stub.VenderEntrada(aforo_pb2.VenderEntradaRequest(seccion_id=sid, cantidad=2), timeout=5)
    assert v.exito is True
    assert v.disponibles_restantes == antes - 2

    a = stub.AnularEntrada(aforo_pb2.AnularEntradaRequest(seccion_id=sid, cantidad=2), timeout=5)
    assert a.exito is True
    assert a.disponibles_restantes == antes


def test_vender_sin_stock_no_muta(stub, seccion_con_stock):
    sid = seccion_con_stock.seccion_id
    antes = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=sid), timeout=5).cantidad_entradas_disponibles

    v = stub.VenderEntrada(aforo_pb2.VenderEntradaRequest(seccion_id=sid, cantidad=antes + 1), timeout=5)
    assert v.exito is False
    despues = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=sid), timeout=5).cantidad_entradas_disponibles
    assert despues == antes  # el rechazo no descuenta nada


def test_cantidades_invalidas_rechazadas(stub, seccion_con_stock):
    """cantidad < 1 no puede operar (antes era el xfail: aforo no lo validaba)."""
    sid = seccion_con_stock.seccion_id
    antes = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=sid), timeout=5).cantidad_entradas_disponibles

    for cantidad in (0, -5):
        v = stub.VenderEntrada(aforo_pb2.VenderEntradaRequest(seccion_id=sid, cantidad=cantidad), timeout=5)
        assert v.exito is False, f"VenderEntrada({cantidad}) no debió aceptarse"
        a = stub.AnularEntrada(aforo_pb2.AnularEntradaRequest(seccion_id=sid, cantidad=cantidad), timeout=5)
        assert a.exito is False, f"AnularEntrada({cantidad}) no debió aceptarse"

    despues = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=sid), timeout=5).cantidad_entradas_disponibles
    assert despues == antes


def test_concurrencia_sin_sobreventa(stub, seccion_con_stock):
    """d0 requests simultáneos de 1 entrada sobre stock d0+2:
    solo d0 venden (un solo UPDATE atómico, sin lost updates)."""
    from concurrent.futures import ThreadPoolExecutor
    sid = seccion_con_stock.seccion_id
    d0 = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=sid), timeout=5).cantidad_entradas_disponibles

    def vender_uno(_):
        return stub.VenderEntrada(
            aforo_pb2.VenderEntradaRequest(seccion_id=sid, cantidad=1), timeout=10
        ).exito

    with ThreadPoolExecutor(max_workers=10) as ex:
        resultados = list(ex.map(vender_uno, range(d0 + 2)))

    exitos = sum(resultados)
    try:
        assert exitos == d0, f"sobreventa o venta perdida: {exitos} éxitos con stock {d0}"
        final = stub.GetSeccion(aforo_pb2.GetSeccionRequest(seccion_id=sid), timeout=5)
        assert final.cantidad_entradas_disponibles == 0
        assert final.existe
    finally:
        # net-zero: reintegrar lo descontado
        for _ in range(exitos):
            stub.AnularEntrada(aforo_pb2.AnularEntradaRequest(seccion_id=sid, cantidad=1), timeout=10)

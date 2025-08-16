# api.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from typing import Optional
from uuid import UUID
from decimal import Decimal

from models import (
    ProductoCreate,
    ProductoOut,
    ProductoUpdate,
    ProductosPage,
    _strip_accents,  # función utilitaria del modelo para normalizar texto
)

router = APIRouter(prefix="/api", tags=["productos"])


# ---------------- Repositorio en memoria (demo) ----------------
class RepoProductos:
    def __init__(self):
        # Diccionario por ID y un índice por nombre normalizado
        self._items: dict[UUID, ProductoOut] = {}
        self._name_to_id: dict[str, UUID] = {}

    @staticmethod
    def _norm_name(nombre: str) -> str:
        return nombre.lower()

    async def existe_nombre(self, nombre_norm: str, *, exclude_id: Optional[UUID] = None) -> bool:
        found = self._name_to_id.get(nombre_norm)
        if found is None:
            return False
        if exclude_id and found == exclude_id:
            return False
        return True

    async def crear(self, prod: ProductoCreate) -> ProductoOut:
        item = ProductoOut(**prod.model_dump())
        self._items[item.id] = item
        self._name_to_id[self._norm_name(item.nombre)] = item.id
        return item

    async def obtener(self, id_: UUID) -> Optional[ProductoOut]:
        return self._items.get(id_)

    async def listar(
        self,
        q: Optional[str],
        categoria: Optional[str],
        min_precio: Optional[Decimal],
        max_precio: Optional[Decimal],
        limit: int,
        offset: int,
    ) -> tuple[list[ProductoOut], int]:
        datos = list(self._items.values())

        # Filtro por texto en nombre
        if q:
            qn = _strip_accents(q.strip().lower())
            datos = [p for p in datos if qn in _strip_accents(p.nombre.lower())]

        # Filtro por categoría
        if categoria:
            cat = _strip_accents(categoria.strip().lower())
            datos = [p for p in datos if cat in p.categorias]

        # Filtros de precio (comparación Decimal vs Decimal)
        if min_precio is not None:
            datos = [p for p in datos if p.precio >= min_precio]
        if max_precio is not None:
            datos = [p for p in datos if p.precio <= max_precio]

        total = len(datos)
        # Paginación
        datos = datos[offset: offset + limit]
        return datos, total

    async def actualizar_full(self, id_: UUID, prod: ProductoCreate) -> ProductoOut:
        actual = await self.obtener(id_)
        if not actual:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Unicidad de nombre (excluyendo este ID)
        nombre_norm = self._norm_name(prod.nombre)
        if await self.existe_nombre(nombre_norm, exclude_id=id_):
            raise HTTPException(
                status_code=409,
                detail={"code": "DUPLICATE_NAME", "message": "Ya existe un producto con ese nombre"},
            )

        # Actualizar índices de nombre
        viejo_norm = self._norm_name(actual.nombre)
        if viejo_norm in self._name_to_id:
            del self._name_to_id[viejo_norm]

        nuevo = ProductoOut(id=id_, **prod.model_dump())
        self._items[id_] = nuevo
        self._name_to_id[nombre_norm] = id_
        return nuevo

    async def actualizar_partial(self, id_: UUID, cambios: ProductoUpdate) -> ProductoOut:
        actual = await self.obtener(id_)
        if not actual:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Mezclamos actual + cambios (y validamos con ProductoCreate para reutilizar reglas)
        base = {
            "nombre": actual.nombre,
            "precio": actual.precio,
            "categorias": actual.categorias,
        }
        patch = cambios.model_dump(exclude_unset=True)
        base.update(patch)

        candidato = ProductoCreate(**base)

        # Checar unicidad si cambió el nombre
        if candidato.nombre.lower() != actual.nombre.lower():
            if await self.existe_nombre(self._norm_name(candidato.nombre)):
                raise HTTPException(
                    status_code=409,
                    detail={"code": "DUPLICATE_NAME", "message": "Ya existe un producto con ese nombre"},
                )

        # Reutilizamos la lógica de reemplazo total para persistir
        return await self.actualizar_full(id_, candidato)

    async def borrar(self, id_: UUID) -> None:
        actual = await self.obtener(id_)
        if not actual:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        del self._items[id_]
        norm = self._norm_name(actual.nombre)
        if self._name_to_id.get(norm) == id_:
            del self._name_to_id[norm]


# Instancia única en memoria para la demo
_repo = RepoProductos()
def get_repo() -> RepoProductos:
    return _repo


# ----------------------- Endpoints -----------------------

@router.post("/productos", response_model=ProductoOut, status_code=status.HTTP_201_CREATED)
async def crear_producto(payload: ProductoCreate, repo: RepoProductos = Depends(get_repo)):
    if await repo.existe_nombre(payload.nombre.lower()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_NAME", "message": "Ya existe un producto con ese nombre"},
        )
    return await repo.crear(payload)


@router.get("/productos", response_model=ProductosPage)
async def listar_productos(
    q: Optional[str] = Query(default=None, min_length=1, max_length=80, description="Búsqueda por nombre"),
    categoria: Optional[str] = Query(default=None, description="Filtrar por categoría"),
    min_precio: Optional[Decimal] = Query(default=None, gt=0, description="Precio mínimo"),
    max_precio: Optional[Decimal] = Query(default=None, gt=0, description="Precio máximo"),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repo: RepoProductos = Depends(get_repo),
):
    # Validación de rango lógico de precios (opcional pero útil)
    if min_precio is not None and max_precio is not None and min_precio > max_precio:
        raise HTTPException(status_code=400, detail="min_precio no puede ser mayor que max_precio")

    items, total = await repo.listar(q, categoria, min_precio, max_precio, limit, offset)
    return ProductosPage(total=total, items=items)


@router.get("/productos/{id}", response_model=ProductoOut)
async def obtener_producto(
    id: UUID = Path(..., description="ID del producto"),
    repo: RepoProductos = Depends(get_repo),
):
    prod = await repo.obtener(id)
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return prod


@router.put("/productos/{id}", response_model=ProductoOut)
async def reemplazar_producto(
    id: UUID,
    payload: ProductoCreate,
    repo: RepoProductos = Depends(get_repo),
):
    return await repo.actualizar_full(id, payload)


@router.patch("/productos/{id}", response_model=ProductoOut)
async def actualizar_parcial_producto(
    id: UUID,
    payload: ProductoUpdate,
    repo: RepoProductos = Depends(get_repo),
):
    # Asegura que haya al menos un campo en el body
    if not payload.model_dump(exclude_unset=True):
        raise HTTPException(status_code=400, detail="Debes enviar al menos un campo para actualizar")
    return await repo.actualizar_partial(id, payload)


@router.delete("/productos/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_producto(
    id: UUID,
    repo: RepoProductos = Depends(get_repo),
):
    await repo.borrar(id)
    return None

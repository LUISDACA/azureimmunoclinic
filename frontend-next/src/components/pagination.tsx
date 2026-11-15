"use client";
import { useEffect } from 'react';
import { Button } from './ui/button';
import type { PageResponse } from '@/lib/api/types';
export function Pagination({data,page,onPage,refresh,busy=false}:{data?:Omit<PageResponse<unknown>,'items'>;page:number;onPage:(page:number)=>void;refresh:()=>unknown;busy?:boolean}) {
  const last=data?.total_pages;
  useEffect(()=>{if(last!==undefined && page>Math.max(1,last))onPage(Math.max(1,last));},[last,page,onPage]);
  return <nav aria-label="Paginación" className="grid grid-cols-2 items-center gap-2 sm:flex sm:flex-wrap sm:gap-3">
    <Button className="w-full sm:w-auto" variant="outline" disabled={busy || !data?.has_previous} onClick={()=>onPage(page-1)}>Anterior</Button>
    <Button className="w-full sm:order-3 sm:w-auto" variant="outline" disabled={busy || !data?.has_next} onClick={()=>onPage(page+1)}>Siguiente</Button>
    <span className="col-span-2 text-center text-sm sm:order-2 sm:col-span-1">Página {page} de {data?.total_pages ?? '…'} · {data?.total ?? '…'} registros</span>
    <Button className="col-span-2 w-full sm:order-4 sm:col-span-1 sm:ml-auto sm:w-auto" variant="ghost" disabled={busy} onClick={()=>void refresh()}>Actualizar lista</Button>
  </nav>;
}

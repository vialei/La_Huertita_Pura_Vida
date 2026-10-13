"""Comprobantes de pago - La Huertita Pura Vida.
Python 3.10+, ttkbootstrap 2.2.3, reportlab y PyMuPDF.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
import fitz
from reportlab.pdfgen import canvas

BASE = Path(__file__).resolve().parent
PLANTILLA = BASE / 'plantilla.pdf'
PRODUCTOS = ('Albahaca Maseta M Decorada', 'Albahaca Maseta M sin decorar')


def interpretar_fecha(valor):
    for formato in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(valor.strip(), formato).strftime('%d/%m/%Y')
        except ValueError:
            pass
    raise ValueError('Ingresá una fecha válida (dd/mm/aaaa).')


def interpretar_monto(valor):
    limpio = valor.strip().replace('₡', '').replace(' ', '')
    if not limpio or not re.fullmatch(r'[0-9.,]+', limpio):
        raise ValueError('Ingresá un monto numérico válido.')
    # En Costa Rica se admiten 1800, 1.800 y 1800,50.
    if ',' in limpio:
        limpio = limpio.replace('.', '').replace(',', '.')
    elif '.' in limpio:
        grupos = limpio.split('.')
        if len(grupos) > 1 and all(len(g) == 3 for g in grupos[1:]):
            limpio = ''.join(grupos)
    try:
        monto = Decimal(limpio)
    except InvalidOperation:
        raise ValueError('Ingresá un monto numérico válido.')
    if not monto.is_finite() or monto <= 0:
        raise ValueError('El monto debe ser mayor que cero.')
    return monto


def texto_ajustado(c, texto, x, y, ancho, tam=10, minimo=7, alinear='left'):
    while c.stringWidth(texto, 'Helvetica', tam) > ancho and tam > minimo:
        tam -= 0.5
    if c.stringWidth(texto, 'Helvetica', tam) > ancho:
        raise ValueError('El texto es demasiado largo para la plantilla.')
    c.setFont('Helvetica', tam)
    if alinear == 'right':
        c.drawRightString(x, y, texto)
    else:
        c.drawString(x, y, texto)


def generar_pdf(nombre, fecha, producto, monto, destino):
    """Mantiene el PDF de Canva y sustituye únicamente los textos variables."""
    if not PLANTILLA.is_file():
        raise FileNotFoundError('No se encontró plantilla.pdf junto a main.py.')
    doc = fitz.open(PLANTILLA)
    if len(doc) != 1:
        raise ValueError('La plantilla debe tener una sola página.')
    pagina = doc[0]
    # Rectángulos medidos sobre la plantilla original (coordenadas PDF).
    campos = [
        (fitz.Rect(419, 110, 560, 139), fecha),
        (fitz.Rect(129, 251, 420, 284), nombre),
        (fitz.Rect(59, 368, 360, 398), producto),
        (fitz.Rect(496, 368, 545, 398), f'{monto:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')),
    ]
    for area, _ in campos:
        pagina.add_redact_annot(area, fill=(1, 1, 1))
    # No borrar gráficos ni imágenes del documento Canva.
    pagina.apply_redactions(images=0, graphics=0, text=0)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(pagina.rect.width, pagina.rect.height))
    h = pagina.rect.height
    texto_ajustado(c, fecha, 423, h-130, 125, tam=10)
    texto_ajustado(c, nombre, 132, h-271, 275, tam=10)
    texto_ajustado(c, producto, 62.5, h-389, 310, tam=9)
    importe = campos[3][1]
    texto_ajustado(c, importe, 537, h-389, 95, tam=9, alinear='right')
    c.save()
    buffer.seek(0)
    overlay = fitz.open(stream=buffer.read(), filetype='pdf')
    pagina.show_pdf_page(pagina.rect, overlay, 0)
    doc.save(str(destino), garbage=4, deflate=True)
    overlay.close()
    doc.close()


class Aplicacion(ttk.Window):
    def __init__(self):
        super().__init__(themename='darkly')
        self.title('Comprobante de Pago - La Huertita Pura Vida')
        self.geometry('900x610')
        self.minsize(760, 520)
        self.configure(padx=45, pady=36)

        ttk.Label(self, text='📄 Comprobante De Pago La Huertita Pura Vida',
                  font=('Helvetica', 21), anchor='center').pack(pady=(12, 28), fill='x')

        seccion = ttk.Labelframe(self, text='Sección', padding=24, bootstyle='info')
        seccion.pack(fill='both', expand=True, padx=18)
        seccion.columnconfigure(0, weight=1)
        seccion.columnconfigure(1, weight=1)

        ttk.Label(seccion, text='Fecha de pago').grid(row=0, column=1, sticky='w', pady=(4, 6))
        self.fecha = ttk.Entry(seccion, width=24)
        self.fecha.grid(row=1, column=1, sticky='ew', pady=(0, 35))
        self.fecha.insert(0, datetime.now().strftime('%d/%m/%Y'))

        ttk.Label(seccion, text='Nombre').grid(row=2, column=0, sticky='w', pady=(4, 6), padx=(0, 35))
        self.nombre = ttk.Entry(seccion)
        self.nombre.grid(row=3, column=0, sticky='ew', padx=(0, 35), pady=(0, 26))

        ttk.Label(seccion, text='Producto').grid(row=4, column=0, sticky='w', pady=(0, 6), padx=(0, 35))
        self.producto = ttk.Combobox(seccion, values=PRODUCTOS, state='readonly')
        self.producto.grid(row=5, column=0, sticky='ew', padx=(0, 35), pady=(0, 18))

        ttk.Label(seccion, text='Monto total (₡)').grid(row=4, column=1, sticky='w', pady=(0, 6))
        self.monto = ttk.Entry(seccion)
        self.monto.grid(row=5, column=1, sticky='ew', pady=(0, 18))

        ttk.Button(self, text='Generar Factura', command=self.generar,
                   bootstyle='primary', width=35).pack(pady=(25, 10), ipady=9)

    def generar(self):
        try:
            nombre = self.nombre.get().strip()
            if not nombre:
                raise ValueError('Ingresá el nombre del cliente.')
            if len(nombre) > 100:
                raise ValueError('El nombre es demasiado largo.')
            fecha = interpretar_fecha(self.fecha.get())
            producto = self.producto.get()
            if producto not in PRODUCTOS:
                raise ValueError('Seleccioná un producto.')
            monto = interpretar_monto(self.monto.get())
            nombre_archivo = re.sub(r'[^\w -]', '', nombre, flags=re.UNICODE).strip().replace(' ', '_')
            destino = filedialog.asksaveasfilename(
                title='Guardar comprobante', defaultextension='.pdf',
                filetypes=[('Documento PDF', '*.pdf')],
                initialfile=f'Comprobante_{nombre_archivo}.pdf')
            if not destino:
                return
            generar_pdf(nombre, fecha, producto, monto, destino)
            messagebox.showinfo('Comprobante generado', f'PDF guardado correctamente:\n{destino}')
        except (ValueError, FileNotFoundError, OSError, RuntimeError) as error:
            messagebox.showerror('No se pudo generar el comprobante', str(error))


if __name__ == '__main__':
    Aplicacion().mainloop()

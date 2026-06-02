# Escala Oficial ARCA - Artículo 94 (Enero a Junio 2026)
datos_escala = [
    [0, 2000030.09, 0, 0.05],
    [2000030.09, 4000060.17, 100001.50, 0.09],
    [4000060.17, 6000090.26, 280004.21, 0.12],
    [6000090.26, 9000135.40, 520007.82, 0.15],
    [9000135.40, 18000270.80, 970014.59, 0.19],
    [18000270.80, 27000406.20, 2680040.32, 0.23],
    [27000406.20, 40500609.30, 4750071.46, 0.27],
    [40500609.30, 60750913.96, 8395126.30, 0.31],
    [60750913.96, float('inf'), 14672720.74, 0.35]
]

# Definimos el "Escudo" o Mínimo No Imponible Anual (Valor aproximado base 2026)
MINIMO_NO_IMPONIBLE = 5151800

def calcular_impuesto_ganancias(ingreso_total_anual):
    # Paso 1: Restar el Mínimo No Imponible
    base_imponible = ingreso_total_anual - MINIMO_NO_IMPONIBLE
    
    # Si la resta da cero o negativo, el escudo frenó todo. No se paga nada.
    if base_imponible <= 0:
        return 0, base_imponible # Retornamos 0 impuesto
        
    # Paso 2: Recién ahora metemos la plata sobrante a la tabla
    for escalon in datos_escala:
        limite_inferior = escalon[0]
        limite_superior = escalon[1]
        cuota_fija = escalon[2]
        tasa_marginal = escalon[3]
        
        if limite_inferior < base_imponible <= limite_superior:
            excedente = base_imponible - limite_inferior
            impuesto_variable = excedente * tasa_marginal
            impuesto_total = cuota_fija + impuesto_variable
            
            return impuesto_total, base_imponible

# --- Bloque de Prueba ---
mi_ingreso_total = 10000000 # Probá con 100.000 y después probá con 10.000.000
impuesto_a_pagar, plata_en_tabla = calcular_impuesto_ganancias(mi_ingreso_total)

print(f"Ingresos Totales en el año: ${mi_ingreso_total:,.2f}")
print(f"Monto que superó el escudo: ${max(0, plata_en_tabla):,.2f}")
print(f"Impuesto final a pagar:     ${impuesto_a_pagar:,.2f}")
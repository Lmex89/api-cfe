# API CFE — Consumo de energía eléctrica residencial

Sistema para rastrear el consumo de energía eléctrica de viviendas en México,
calcular costos con tarifas escalonadas de la CFE, y generar dashboards de facturación bimestral.

## Language

**Vivienda**:
Una casa o departamento físico donde hay un medidor de energía eléctrica. Cada vivienda tiene su propio historial de lecturas, tarifas y periodos de facturación.
_Avoid_: Household, punto de consumo, hogar, inmueble

**Lectura**:
Un registro puntual del medidor: los kWh acumulados en una fecha específica. Es un dato atómico, no un cálculo.
_Avoid_: MeterReading, medición, registro

**Consumo**:
La energía usada durante un periodo. Se calcula como la diferencia entre la última y la primera lectura del periodo. No es un dato que se almacene directamente; se deriva de las lecturas.
_Avoid_: gasto, usage, consumo total

**Tarifa**:
Un código de tarifa CFE abstracto (ej: "1C", "1D"). Representa la categoría oficial de servicio eléctrico. No contiene precios directos; estos viven en las versiones.
_Avoid_: plan, tipo de servicio, código tarifario

**Versión de tarifa**:
Una versión temporal de una tarifa con precios y rangos específicos. Las tarifas CFE cambian periódicamente; cada vez que cambian los precios, se crea una nueva versión con un periodo de vigencia (fecha inicio/fin).
_Avoid_: TariffVersion, tabla de precios, esquema tarifario

**Rango**:
Un bracket de consumo dentro de una versión de tarifa. Define un intervalo (mínimo-máximo kWh) y un precio por kWh. Los rangos se aplican de forma escalonada: el consumo llena cada bracket antes de pasar al siguiente, como el ISR.
_Avoid_: TariffRange, tramo, nivel, tier

**Periodo**:
Un bimestre de facturación. Define el intervalo de fechas (inicio/fin) para el cual se calcula el costo. Corresponde al ciclo bimestral típico de la CFE.
_Avoid_: BillingPeriod, ciclo, factura, mes

**Asignación**:
La vinculación temporal entre una vivienda y una tarifa. Indica qué tarifa aplica a qué vivienda durante qué intervalo de fechas. Si la CFE cambia la tarifa de una vivienda, se crea una nueva asignación.
_Avoid_: HouseholdTariff, asociación, vinculación

**Costo base**:
El monto calculado aplicando los rangos escalonados de la tarifa activa al consumo del periodo. No incluye impuestos ni cargos adicionales.
_Avoid_: subtotal, precio, base

**Costo total**:
El monto final a pagar. Es el costo base más IVA (16%) y DAP (5%).
_Avoid_: total, factura, monto a pagar

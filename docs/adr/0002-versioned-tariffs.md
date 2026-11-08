# Tarifas versionadas (Tariff + TariffVersion)

Las tarifas CFE se modelan como dos entidades separadas: `Tariff` (el código abstracto, ej: "1C") y `TariffVersion` (la versión temporal con precios y rangos específicos, vigente entre fechas).

Esto refleja cómo funciona la CFE en la realidad: una tarifa puede tener precios distintos en distintos periodos del año. Separar el concepto abstracto de su implementación temporal permite:

- Historial completo de cambios de precios por tarifa
- Cálculos de costo correctos para periodos bimestrales que caen en diferentes versiones
- Reutilización de la misma tarifa en múltiples viviendas sin duplicar datos

Una alternativa más simple (una sola tabla con precios y fechas) habría creado redundancia y dificultado la auditoría de cambios.

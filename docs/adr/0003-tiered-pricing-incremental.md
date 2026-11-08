# Cálculo de tarifas escalonado (no rango único)

El costo de energía se calcula aplicando los rangos de tarifa de forma escalonada: el consumo llena cada bracket de consumo antes de pasar al siguiente, similar al ISR. No es un sistema de "rango único" donde todo el consumo cae en el bracket que le corresponda por volumen total.

Ejemplo con consumo de 250 kWh y rangos [0-100: $0.10, 100-300: $0.15]:
- Escalonado: 100 × $0.10 + 150 × $0.15 = $10 + $22.50 = $32.50
- Rango único (incorrecto): 250 × $0.15 = $37.50

Esto es así porque refleja el esquema real de la CFE para tarifas residenciales. Cambiar a rango único generaría cálculos incorrectos y facturas erróneas.
